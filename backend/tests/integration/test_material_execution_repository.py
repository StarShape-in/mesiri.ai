"""Integration tests for PostgresMaterialExecutionRepository + the M8 Handler.

Tests against a live PostgreSQL database. Covers what a fakes-only unit test
cannot: real transaction rollback, real concurrent-duplicate-execution
(Postgres's own row lock on the idempotency_keys INSERT), and crash/retry
recovery against the real workflow_instances/material_receipts tables.
"""

from __future__ import annotations

import asyncio
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.materials.handlers import ExecuteConfirmedMaterialActionHandler
from mesiri.application.materials.recovery import (
    MATERIAL_WORKFLOW_KEYS,
    recover_confirmed_instances,
)
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.database import PostgresDatabase
from mesiri.infrastructure.postgres.repositories.material_execution import (
    PostgresMaterialExecutionRepository,
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
async def test_engine():
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def clean_db(test_engine: AsyncEngine):
    async with test_engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM idempotency_keys"))
        await conn.execute(sa.text("DELETE FROM outbox_events"))
        await conn.execute(sa.text("DELETE FROM material_receipts"))
        await conn.execute(sa.text("DELETE FROM material_usage"))
        await conn.execute(sa.text("DELETE FROM workflow_instances"))
        await conn.execute(sa.text("DELETE FROM sites"))
        await conn.execute(sa.text("DELETE FROM projects"))
        await conn.execute(sa.text("DELETE FROM users"))
        await conn.execute(sa.text("DELETE FROM organizations"))
    yield


@pytest.fixture
async def test_org(test_engine: AsyncEngine) -> uuid.UUID:
    org_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, created_at, updated_at) "
                "VALUES (:id, :name, :deployment_type, :db_route, :status, now(), now())"
            ),
            {
                "id": org_id,
                "name": "Test Organization",
                "deployment_type": "local",
                "db_route": "default",
                "status": "active",
            },
        )
    return org_id


@pytest.fixture
async def test_user(test_engine: AsyncEngine, test_org: uuid.UUID) -> uuid.UUID:
    user_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, role, "
                "created_at, updated_at) "
                "VALUES (:id, :org_id, :email, 'x', 'Test User', 'admin', now(), now())"
            ),
            {"id": user_id, "org_id": test_org, "email": f"{user_id}@example.com"},
        )
    return user_id


@pytest.fixture
async def test_project(test_engine: AsyncEngine, test_org: uuid.UUID) -> uuid.UUID:
    project_id = uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": test_org},
        )
    return project_id


@pytest.fixture
async def db(test_engine: AsyncEngine):
    settings = Settings()
    database = PostgresDatabase(settings.postgres)
    await database.connect()
    yield database
    await database.disconnect()


def _confirmed_action(
    *, workflow_instance_id: str, org: uuid.UUID, user: uuid.UUID, project: uuid.UUID
) -> ConfirmedActionV2:
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=str(org),
        user_id=str(user),
        project_id=str(project),
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    return ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id=workflow_instance_id,
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=str(user),
    )


async def _seed_confirmed_workflow_instance(
    test_engine: AsyncEngine,
    *,
    workflow_instance_id: str,
    org: uuid.UUID,
    user: uuid.UUID,
    project: uuid.UUID | None,
    workflow_key: WorkflowKey = WorkflowKey.MATERIAL_RECEIPT,
) -> None:
    """Simulate the durable state left behind by M7's resume() committing
    CONFIRMED, as if the process then crashed before M8's Handler ran."""
    project_id = str(project) if project is not None else None
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=str(org),
        user_id=str(user),
        project_id=project_id,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    state = WorkflowStateV2(
        workflow_instance_id=workflow_instance_id,
        workflow_key=workflow_key,
        correlation_id="cor_1",
        organization_id=str(org),
        user_id=str(user),
        project_id=project_id,
        phase=WorkflowPhase.CONFIRMED,
        draft_action=draft,
    )
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO workflow_instances "
                "(id, organization_id, user_id, workflow_key, phase, state, correlation_id, status, version) "
                "VALUES (:id, :org_id, :user_id, :workflow_key, 'confirmed', CAST(:state AS jsonb), "
                ":correlation_id, 'active', 1)"
            ),
            {
                "id": uuid.UUID(workflow_instance_id),
                "org_id": org,
                "user_id": user,
                "workflow_key": workflow_key.value,
                "state": state.model_dump_json(),
                "correlation_id": "cor_1",
            },
        )


async def test_persist_success_writes_row_outbox_and_completes_workflow(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    db: PostgresDatabase,
):
    workflow_instance_id = str(uuid.uuid4())
    await _seed_confirmed_workflow_instance(
        test_engine,
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    confirmed = _confirmed_action(
        workflow_instance_id=workflow_instance_id, org=test_org, user=test_user, project=test_project
    )
    handler = ExecuteConfirmedMaterialActionHandler(db=db, repo=PostgresMaterialExecutionRepository())

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.SUCCEEDED
    async with test_engine.connect() as conn:
        receipt = (
            await conn.execute(
                sa.text("SELECT material_name, quantity FROM material_receipts WHERE id = :id"),
                {"id": uuid.UUID(result.material_row_id)},
            )
        ).mappings().first()
        assert receipt is not None
        assert receipt["material_name"] == "cement"

        outbox_count = (
            await conn.execute(
                sa.text("SELECT COUNT(*) FROM outbox_events WHERE aggregate_id = :id"),
                {"id": uuid.UUID(result.material_row_id)},
            )
        ).scalar_one()
        assert outbox_count == 1

        phase = (
            await conn.execute(
                sa.text("SELECT phase FROM workflow_instances WHERE id = :id"),
                {"id": uuid.UUID(workflow_instance_id)},
            )
        ).scalar_one()
        assert phase == "completed"


async def test_validation_rejection_rolls_back_no_domain_row_and_transitions_execution_rejected(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    db: PostgresDatabase,
):
    workflow_instance_id = str(uuid.uuid4())
    await _seed_confirmed_workflow_instance(
        test_engine,
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=None,  # unresolved project -> validation rejection
    )
    draft = DraftActionV2(
        draft_id="draft_1",
        correlation_id="cor_1",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_RECEIPT,
        organization_id=str(test_org),
        user_id=str(test_user),
        project_id=None,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    confirmed = ConfirmedActionV2(
        confirmed_action_id="conf_1",
        workflow_instance_id=workflow_instance_id,
        correlation_id="cor_1",
        draft_action=draft,
        confirmed_by_user_id=str(test_user),
    )
    handler = ExecuteConfirmedMaterialActionHandler(db=db, repo=PostgresMaterialExecutionRepository())

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.REJECTED
    async with test_engine.connect() as conn:
        row_count = (await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))).scalar_one()
        assert row_count == 0

        phase = (
            await conn.execute(
                sa.text("SELECT phase FROM workflow_instances WHERE id = :id"),
                {"id": uuid.UUID(workflow_instance_id)},
            )
        ).scalar_one()
        assert phase == "execution_rejected"


async def test_concurrent_duplicate_execution_writes_exactly_one_row(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    db: PostgresDatabase,
):
    """Two concurrent handler.handle() calls for the same workflow_instance_id
    (simulating a duplicate WhatsApp confirmation delivery racing with itself)
    must produce exactly one material_receipts row -- Postgres's row lock on
    the idempotency_keys INSERT is the only guarantee relied on, no app-level
    locking."""
    workflow_instance_id = str(uuid.uuid4())
    await _seed_confirmed_workflow_instance(
        test_engine,
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    confirmed = _confirmed_action(
        workflow_instance_id=workflow_instance_id, org=test_org, user=test_user, project=test_project
    )
    handler_a = ExecuteConfirmedMaterialActionHandler(db=db, repo=PostgresMaterialExecutionRepository())
    handler_b = ExecuteConfirmedMaterialActionHandler(db=db, repo=PostgresMaterialExecutionRepository())

    results = await asyncio.gather(handler_a.handle(confirmed), handler_b.handle(confirmed))

    statuses = sorted(r.status for r in results)
    assert statuses == sorted([ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED])
    async with test_engine.connect() as conn:
        row_count = (await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))).scalar_one()
        assert row_count == 1


async def test_recovery_replays_crashed_confirmed_instance_and_is_idempotent_on_rerun(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    db: PostgresDatabase,
):
    """Simulates the real crash window: M7 committed CONFIRMED, the process
    died before M8's Handler ever ran. A recovery sweep must discover and
    replay it exactly once, and running the sweep again must be a no-op."""
    workflow_instance_id = str(uuid.uuid4())
    await _seed_confirmed_workflow_instance(
        test_engine,
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    handler = ExecuteConfirmedMaterialActionHandler(db=db, repo=PostgresMaterialExecutionRepository())

    first_pass = await recover_confirmed_instances(db, handler, MATERIAL_WORKFLOW_KEYS)
    second_pass = await recover_confirmed_instances(db, handler, MATERIAL_WORKFLOW_KEYS)

    assert len(first_pass) == 1
    assert first_pass[0].status is ExecutionStatus.SUCCEEDED
    # Second sweep finds nothing to recover: the instance is no longer CONFIRMED.
    assert second_pass == []
    async with test_engine.connect() as conn:
        row_count = (await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))).scalar_one()
        assert row_count == 1
        phase = (
            await conn.execute(
                sa.text("SELECT phase FROM workflow_instances WHERE id = :id"),
                {"id": uuid.UUID(workflow_instance_id)},
            )
        ).scalar_one()
        assert phase == "completed"
