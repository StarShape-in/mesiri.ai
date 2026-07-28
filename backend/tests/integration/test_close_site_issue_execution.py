"""Site Issue close-out — integration test against a real Postgres.

Closes the gap flagged alongside Expense's full test suite
(test_expense_execution_money_wiring.py): unit tests cover
mapper/validation/nodes in isolation, but nothing previously exercised the
full confirmed-message -> persisted-status-change path -- a real
ConfirmedActionV2 through ExecuteConfirmedCloseSiteIssueHandler.handle(),
which (unlike RecordExpenseHandler.handle(conn, cmd)) owns its own
transaction via PostgresDatabase and also drives the workflow_instances
phase transition (see application/progress/handlers.py's docstring on why
CloseSiteIssue's re-check lives inline rather than as a separate resolver).

Covers: acknowledge/resolve/wont_fix each moving site_issues.status and
emitting the matching outbox_events row, the current-status re-check
rejecting a stale action (workflow_instances moves to EXECUTION_REJECTED,
not COMPLETED), and idempotent replay not double-applying.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.progress.handlers import ExecuteConfirmedCloseSiteIssueHandler
from mesiri.application.progress.repository import ProgressExecutionRepository
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri.infrastructure.postgres.repositories.progress_execution import (
    PostgresProgressExecutionRepository,
)
from mesiri_contracts.application.results.execution_result import ExecutionStatus
from mesiri_contracts.assistant.draft_action import DraftActionType
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.confirmed_action import ConfirmedActionV2
from mesiri_contracts.assistant.v2.draft_action import DraftActionV2
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def db():
    settings = Settings()
    database = PostgresDatabase(settings.postgres)
    await database.connect()
    yield database
    await database.disconnect()


@pytest.fixture
async def scenario(engine: AsyncEngine):
    """One org/user/project/site and one OPEN site_issues row."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    site_id = uuid.uuid4()
    issue_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Close Issue Test Org', 'local', "
                "'default', 'active', now(), now())"
            ),
            {"id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, access_policy, created_at, updated_at) "
                "VALUES (:id, :org_id, :email, 'x', 'Test', 'admin', 'active', "
                "CAST(:policy AS jsonb), now(), now())"
            ),
            {
                "id": user_id,
                "org_id": org_id,
                "email": f"{user_id}@example.com",
                "policy": '{"mode": "all_projects", "projects": []}',
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Close Issue Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO sites (id, project_id, organization_id, name, status, "
                "created_at, updated_at) "
                "VALUES (:id, :project_id, :org_id, 'Test Site', 'active', now(), now())"
            ),
            {"id": site_id, "project_id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO site_issues (id, organization_id, project_id, site_id, "
                "issue_type, severity, narrative, occurred_at, status, reported_by_user_id) "
                "VALUES (:id, :org_id, :project_id, :site_id, 'MATERIAL_SHORTAGE', 'HIGH', "
                "'Out of cement', now(), 'OPEN', :user_id)"
            ),
            {"id": issue_id, "org_id": org_id, "project_id": project_id, "site_id": site_id, "user_id": user_id},
        )
    data = {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "site_id": site_id,
        "issue_id": issue_id,
        "workflow_instance_ids": [],
    }
    yield data
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM outbox_events WHERE aggregate_id = :id"), {"id": issue_id})
        await conn.execute(sa.text("DELETE FROM workflow_instances WHERE organization_id = :id"), {"id": org_id})
        for workflow_instance_id in data["workflow_instance_ids"]:
            await conn.execute(
                sa.text("DELETE FROM idempotency_keys WHERE key = :key"), {"key": workflow_instance_id}
            )
        await conn.execute(sa.text("DELETE FROM site_issues WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM sites WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM projects WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM users WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def _seed_workflow_instance(
    engine: AsyncEngine, scenario: dict, action: str, resolution_notes: str | None = None
) -> str:
    """A real CONFIRMED workflow_instances row -- the exact durable state
    ExecuteConfirmedCloseSiteIssueHandler._transition() reads/updates on the
    same connection as the domain write."""
    workflow_instance_id = str(uuid.uuid4())
    draft = DraftActionV2(
        draft_id=f"draft-{uuid.uuid4()}",
        correlation_id=f"corr-{uuid.uuid4()}",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.CLOSE_SITE_ISSUE,
        organization_id=str(scenario["org_id"]),
        user_id=str(scenario["user_id"]),
        project_id=str(scenario["project_id"]),
        site_id=str(scenario["site_id"]),
        fields={
            "site_issue_id": str(scenario["issue_id"]),
            "action": action,
            "resolution_notes": resolution_notes,
        },
    )
    state = WorkflowStateV2(
        workflow_instance_id=workflow_instance_id,
        workflow_key=WorkflowKey.SITE_ISSUE_CLOSE,
        correlation_id=draft.correlation_id,
        organization_id=str(scenario["org_id"]),
        user_id=str(scenario["user_id"]),
        project_id=str(scenario["project_id"]),
        site_id=str(scenario["site_id"]),
        phase=WorkflowPhase.CONFIRMED,
        draft_action=draft,
    )
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO workflow_instances (id, organization_id, user_id, workflow_key, "
                "phase, state, correlation_id, status, version) "
                "VALUES (:id, :organization_id, :user_id, :workflow_key, :phase, "
                "CAST(:state AS jsonb), :correlation_id, 'active', 0)"
            ),
            {
                "id": uuid.UUID(workflow_instance_id),
                "organization_id": scenario["org_id"],
                "user_id": scenario["user_id"],
                "workflow_key": state.workflow_key.value,
                "phase": state.phase.value,
                "state": state.model_dump_json(),
                "correlation_id": state.correlation_id,
            },
        )
    scenario["workflow_instance_ids"].append(workflow_instance_id)
    return workflow_instance_id


def _confirmed_action(workflow_instance_id: str, scenario: dict) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id=f"draft-{uuid.uuid4()}",
        correlation_id=f"corr-{workflow_instance_id}",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.CLOSE_SITE_ISSUE,
        organization_id=str(scenario["org_id"]),
        user_id=str(scenario["user_id"]),
        project_id=str(scenario["project_id"]),
        site_id=str(scenario["site_id"]),
        fields={},
    )
    return ConfirmedActionV2(
        confirmed_action_id=f"confirmed-{uuid.uuid4()}",
        workflow_instance_id=workflow_instance_id,
        correlation_id=draft.correlation_id,
        draft_action=draft,
        confirmed_by_user_id=str(scenario["user_id"]),
    )


def _handler(db: PostgresDatabase) -> ExecuteConfirmedCloseSiteIssueHandler:
    repo: ProgressExecutionRepository = PostgresProgressExecutionRepository()
    return ExecuteConfirmedCloseSiteIssueHandler(db, repo)


async def test_confirmed_resolve_moves_status_and_workflow_and_emits_outbox_event(
    engine: AsyncEngine, db: PostgresDatabase, scenario: dict
):
    workflow_instance_id = await _seed_workflow_instance(
        engine, scenario, action="resolve", resolution_notes="Cement delivered"
    )

    handler = _handler(db)
    result = await handler.handle(_confirmed_action(workflow_instance_id, scenario))

    assert result.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        issue_row = (
            await conn.execute(
                sa.text(
                    "SELECT status, resolution_notes, resolved_at FROM site_issues WHERE id = :id"
                ),
                {"id": scenario["issue_id"]},
            )
        ).mappings().one()
        outbox_row = (
            await conn.execute(
                sa.text(
                    "SELECT event_type FROM outbox_events "
                    "WHERE aggregate_type = 'site_issue' AND aggregate_id = :id"
                ),
                {"id": scenario["issue_id"]},
            )
        ).mappings().one()
        workflow_row = (
            await conn.execute(
                sa.text("SELECT phase, status FROM workflow_instances WHERE id = :id"),
                {"id": uuid.UUID(workflow_instance_id)},
            )
        ).mappings().one()

    assert issue_row["status"] == "RESOLVED"
    assert issue_row["resolution_notes"] == "Cement delivered"
    assert issue_row["resolved_at"] is not None
    assert outbox_row["event_type"] == "SiteIssueResolved"
    assert workflow_row["phase"] == "completed"
    assert workflow_row["status"] == "completed"


async def test_confirmed_acknowledge_moves_status_to_acknowledged(
    engine: AsyncEngine, db: PostgresDatabase, scenario: dict
):
    workflow_instance_id = await _seed_workflow_instance(engine, scenario, action="acknowledge")

    handler = _handler(db)
    result = await handler.handle(_confirmed_action(workflow_instance_id, scenario))

    assert result.status == ExecutionStatus.SUCCEEDED
    async with engine.connect() as conn:
        status = (
            await conn.execute(
                sa.text("SELECT status FROM site_issues WHERE id = :id"), {"id": scenario["issue_id"]}
            )
        ).scalar_one()
        event_type = (
            await conn.execute(
                sa.text(
                    "SELECT event_type FROM outbox_events "
                    "WHERE aggregate_type = 'site_issue' AND aggregate_id = :id"
                ),
                {"id": scenario["issue_id"]},
            )
        ).scalar_one()
    assert status == "ACKNOWLEDGED"
    assert event_type == "SiteIssueAcknowledged"


async def test_confirmed_wont_fix_moves_status_and_writes_notes(
    engine: AsyncEngine, db: PostgresDatabase, scenario: dict
):
    workflow_instance_id = await _seed_workflow_instance(
        engine, scenario, action="wont_fix", resolution_notes="Accepted risk"
    )

    handler = _handler(db)
    result = await handler.handle(_confirmed_action(workflow_instance_id, scenario))

    assert result.status == ExecutionStatus.SUCCEEDED
    async with engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text(
                    "SELECT status, resolution_notes FROM site_issues WHERE id = :id"
                ),
                {"id": scenario["issue_id"]},
            )
        ).mappings().one()
    assert row["status"] == "WONT_FIX"
    assert row["resolution_notes"] == "Accepted risk"


async def test_acknowledging_an_already_resolved_issue_is_rejected_and_workflow_execution_rejected(
    engine: AsyncEngine, db: PostgresDatabase, scenario: dict
):
    """The defense-in-depth re-check in persist_close_site_issue_success --
    time passed between draft-build and confirmation, and someone else
    already resolved the issue. Must reject rather than acknowledge a
    resolved issue, and the workflow must land on EXECUTION_REJECTED, not
    COMPLETED (see workflows/registry.py's phase semantics)."""
    async with engine.begin() as conn:
        await conn.execute(
            sa.text("UPDATE site_issues SET status = 'RESOLVED' WHERE id = :id"),
            {"id": scenario["issue_id"]},
        )

    workflow_instance_id = await _seed_workflow_instance(engine, scenario, action="acknowledge")

    handler = _handler(db)
    result = await handler.handle(_confirmed_action(workflow_instance_id, scenario))

    assert result.status == ExecutionStatus.REJECTED
    assert "already resolved" in result.rejection_reasons[0]

    async with engine.connect() as conn:
        status = (
            await conn.execute(
                sa.text("SELECT status FROM site_issues WHERE id = :id"), {"id": scenario["issue_id"]}
            )
        ).scalar_one()
        workflow_row = (
            await conn.execute(
                sa.text("SELECT phase, status FROM workflow_instances WHERE id = :id"),
                {"id": uuid.UUID(workflow_instance_id)},
            )
        ).mappings().one()
    assert status == "RESOLVED"  # untouched -- the rejected action never wrote it
    assert workflow_row["phase"] == "execution_rejected"
    assert workflow_row["status"] == "execution_rejected"


async def test_replayed_confirmation_does_not_double_transition_status(
    engine: AsyncEngine, db: PostgresDatabase, scenario: dict
):
    """Same workflow_instance_id (== idempotency_key, per mapper.py) confirmed
    twice (retry/duplicate webhook) must not re-run the status transition."""
    workflow_instance_id = await _seed_workflow_instance(engine, scenario, action="resolve")
    confirmed = _confirmed_action(workflow_instance_id, scenario)

    handler = _handler(db)
    first = await handler.handle(confirmed)
    second = await handler.handle(confirmed)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED

    async with engine.connect() as conn:
        status = (
            await conn.execute(
                sa.text("SELECT status FROM site_issues WHERE id = :id"), {"id": scenario["issue_id"]}
            )
        ).scalar_one()
        outbox_count = (
            await conn.execute(
                sa.text(
                    "SELECT count(*) FROM outbox_events "
                    "WHERE aggregate_type = 'site_issue' AND aggregate_id = :id"
                ),
                {"id": scenario["issue_id"]},
            )
        ).scalar_one()
    assert status == "RESOLVED"
    assert outbox_count == 1
