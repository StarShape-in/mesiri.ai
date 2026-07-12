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
from mesiri.application.materials.resolution import PostgresMaterialResolver
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
        await conn.execute(sa.text("DELETE FROM material_movements"))
        await conn.execute(sa.text("DELETE FROM material_receipts"))
        await conn.execute(sa.text("DELETE FROM material_usage"))
        await conn.execute(sa.text("DELETE FROM materials_catalog"))
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
async def cement_material(test_engine: AsyncEngine, test_org: uuid.UUID, test_user: uuid.UUID) -> uuid.UUID:
    """_confirmed_action below reports material_name="cement" with no
    material_id -- the CQRS Handler's resolver (application/materials/
    resolution.py) now requires an exact active catalog match by name before
    persist_success can run, so the fixture data must include one."""
    async with test_engine.begin() as conn:
        unit_id = (
            await conn.execute(sa.text("SELECT id FROM units_of_measure WHERE code = 'bags'"))
        ).scalar_one()
        material_id = uuid.uuid4()
        await conn.execute(
            sa.text(
                "INSERT INTO materials_catalog (id, organization_id, name, default_unit_id, "
                "is_active, created_by) VALUES (:id, :org_id, 'cement', :unit_id, true, :user_id)"
            ),
            {"id": material_id, "org_id": test_org, "unit_id": unit_id, "user_id": test_user},
        )
    return material_id


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
    cement_material: uuid.UUID,
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
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    handler = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.SUCCEEDED
    async with test_engine.connect() as conn:
        receipt = (
            (
                await conn.execute(
                    sa.text("SELECT material_name, quantity FROM material_receipts WHERE id = :id"),
                    {"id": uuid.UUID(result.material_row_id)},
                )
            )
            .mappings()
            .first()
        )
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
    handler = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )

    result = await handler.handle(confirmed)

    assert result.status is ExecutionStatus.REJECTED
    async with test_engine.connect() as conn:
        row_count = (
            await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))
        ).scalar_one()
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
    cement_material: uuid.UUID,
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
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    handler_a = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )
    handler_b = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )

    results = await asyncio.gather(handler_a.handle(confirmed), handler_b.handle(confirmed))

    statuses = sorted(r.status for r in results)
    assert statuses == sorted([ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED])
    async with test_engine.connect() as conn:
        row_count = (
            await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))
        ).scalar_one()
        assert row_count == 1


async def test_recovery_replays_crashed_confirmed_instance_and_is_idempotent_on_rerun(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    cement_material: uuid.UUID,
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
    handler = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )

    first_pass = await recover_confirmed_instances(db, handler, MATERIAL_WORKFLOW_KEYS)
    second_pass = await recover_confirmed_instances(db, handler, MATERIAL_WORKFLOW_KEYS)

    assert len(first_pass) == 1
    assert first_pass[0].status is ExecutionStatus.SUCCEEDED
    # Second sweep finds nothing to recover: the instance is no longer CONFIRMED.
    assert second_pass == []
    async with test_engine.connect() as conn:
        row_count = (
            await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))
        ).scalar_one()
        assert row_count == 1
        phase = (
            await conn.execute(
                sa.text("SELECT phase FROM workflow_instances WHERE id = :id"),
                {"id": uuid.UUID(workflow_instance_id)},
            )
        ).scalar_one()
        assert phase == "completed"


async def test_persist_success_posts_exactly_one_ledger_movement_for_receipt(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    cement_material: uuid.UUID,
    db: PostgresDatabase,
):
    """The CQRS write path (material_execution.py's persist_success) must post
    exactly one RECEIPT movement into material_movements, linked back to the
    material_receipts row it just created via source_type/source_id. The
    movement_type is the load-bearing detail -- a receipt must never produce
    an ISSUE, and a bug that omitted the movement (or doubled it) would leave
    stock silently wrong. The existing persist_success test only looked at
    material_receipts/outbox_events; this one looks at the ledger itself."""
    workflow_instance_id = str(uuid.uuid4())
    await _seed_confirmed_workflow_instance(
        test_engine,
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    confirmed = _confirmed_action(
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    handler = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )

    result = await handler.handle(confirmed)
    assert result.status is ExecutionStatus.SUCCEEDED
    receipt_row_id = uuid.UUID(result.material_row_id)

    async with test_engine.connect() as conn:
        movements = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT movement_type, quantity, source_type, source_id, "
                        "material_id, unit_id, reversal_of_movement_id, idempotency_key "
                        "FROM material_movements WHERE source_type = 'material_receipt' "
                        "AND source_id = :id"
                    ),
                    {"id": receipt_row_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(movements) == 1, "a receipt must produce exactly one ledger movement"
        m = movements[0]
        assert m["movement_type"] == "RECEIPT"
        assert m["quantity"] == 20
        assert m["source_type"] == "material_receipt"
        assert m["source_id"] == receipt_row_id
        assert m["material_id"] == cement_material
        assert m["reversal_of_movement_id"] is None
        assert m["idempotency_key"] == workflow_instance_id


async def test_persist_success_posts_exactly_one_ledger_movement_for_usage(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    cement_material: uuid.UUID,
    db: PostgresDatabase,
):
    """Same invariant as the receipt test above, for the usage/ISSUE branch of
    persist_success (material_execution.py:143-171). A usage report must post
    exactly one ISSUE movement linked back to its material_usage row."""
    workflow_instance_id = str(uuid.uuid4())
    project_id_str = str(test_project)
    org_id_str = str(test_org)
    user_id_str = str(test_user)
    draft = DraftActionV2(
        draft_id="draft_usage",
        correlation_id="cor_usage",
        workflow_instance_id=workflow_instance_id,
        action_type=DraftActionType.RECORD_MATERIAL_USAGE,
        organization_id=org_id_str,
        user_id=user_id_str,
        project_id=project_id_str,
        fields={"material_name": "cement", "quantity": 20, "unit": "bags"},
    )
    state = WorkflowStateV2(
        workflow_instance_id=workflow_instance_id,
        workflow_key=WorkflowKey.MATERIAL_USAGE,
        correlation_id="cor_usage",
        organization_id=org_id_str,
        user_id=user_id_str,
        project_id=project_id_str,
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
                "org_id": test_org,
                "user_id": test_user,
                "workflow_key": WorkflowKey.MATERIAL_USAGE.value,
                "state": state.model_dump_json(),
                "correlation_id": "cor_usage",
            },
        )
    confirmed = ConfirmedActionV2(
        confirmed_action_id="conf_usage",
        workflow_instance_id=workflow_instance_id,
        correlation_id="cor_usage",
        draft_action=draft,
        confirmed_by_user_id=user_id_str,
    )
    handler = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )

    result = await handler.handle(confirmed)
    assert result.status is ExecutionStatus.SUCCEEDED
    usage_row_id = uuid.UUID(result.material_row_id)

    async with test_engine.connect() as conn:
        movements = (
            (
                await conn.execute(
                    sa.text(
                        "SELECT movement_type, quantity, source_type, source_id, "
                        "material_id, reversal_of_movement_id "
                        "FROM material_movements WHERE source_type = 'material_usage' "
                        "AND source_id = :id"
                    ),
                    {"id": usage_row_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(movements) == 1, "a usage must produce exactly one ledger movement"
        m = movements[0]
        assert m["movement_type"] == "ISSUE"
        assert m["quantity"] == 20
        assert m["source_type"] == "material_usage"
        assert m["source_id"] == usage_row_id
        assert m["material_id"] == cement_material
        assert m["reversal_of_movement_id"] is None


async def test_movement_posting_failure_rolls_back_receipt_and_outbox(
    test_engine: AsyncEngine,
    clean_db,
    test_org: uuid.UUID,
    test_user: uuid.UUID,
    test_project: uuid.UUID,
    cement_material: uuid.UUID,
    db: PostgresDatabase,
    monkeypatch: pytest.MonkeyPatch,
):
    """posting.py's docstring promises the operational row and the ledger
    movement share one connection/transaction. Prove it: force the movement
    insert to raise after the material_receipts row already exists inside the
    transaction. The whole transaction must roll back -- no receipt row, no
    movement, no outbox event, no idempotency_keys claim. A phantom receipt
    with no matching ledger movement is the worst V2 failure mode (silently
    wrong stock); this test makes it structurally impossible to ship that bug.

    The idempotency_keys claim also rolls back because it ran inside the same
    transaction -- so a retry can proceed cleanly rather than seeing a stale
    'in_progress' claim.
    """
    from mesiri.infrastructure.postgres.repositories.materials import (
        MaterialMovementsRepository,
    )

    workflow_instance_id = str(uuid.uuid4())
    await _seed_confirmed_workflow_instance(
        test_engine,
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )
    confirmed = _confirmed_action(
        workflow_instance_id=workflow_instance_id,
        org=test_org,
        user=test_user,
        project=test_project,
    )

    original_insert = MaterialMovementsRepository.insert

    async def failing_insert(self, **kwargs):
        raise RuntimeError("simulated movement-posting failure")

    monkeypatch.setattr(MaterialMovementsRepository, "insert", failing_insert)

    handler = ExecuteConfirmedMaterialActionHandler(
        db=db, repo=PostgresMaterialExecutionRepository(), resolver=PostgresMaterialResolver()
    )
    with pytest.raises(RuntimeError, match="simulated movement-posting failure"):
        await handler.handle(confirmed)

    monkeypatch.setattr(MaterialMovementsRepository, "insert", original_insert)

    async with test_engine.connect() as conn:
        receipt_count = (
            await conn.execute(sa.text("SELECT COUNT(*) FROM material_receipts"))
        ).scalar_one()
        assert receipt_count == 0, "receipt row must roll back when movement posting fails"

        movement_count = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM material_movements "
                    "WHERE source_type = 'material_receipt'"
                )
            )
        ).scalar_one()
        assert movement_count == 0, "no movement must survive the rolled-back transaction"

        outbox_count = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM outbox_events "
                    "WHERE aggregate_type = 'material_receipt'"
                )
            )
        ).scalar_one()
        assert outbox_count == 0, "outbox event must roll back with the transaction"

        idempotency_count = (
            await conn.execute(
                sa.text(
                    "SELECT COUNT(*) FROM idempotency_keys WHERE key = :key"
                ),
                {"key": workflow_instance_id},
            )
        ).scalar_one()
        assert idempotency_count == 0, (
            "idempotency claim must roll back so a retry can proceed"
        )
