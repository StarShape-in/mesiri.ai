"""Account admin execution — integration tests against a real Postgres.

Covers create / rename / deactivate through the full Handler ->
PostgresAccountAdminExecutionRepository path, including idempotent replay
and the duplicate-name / not-found rejection paths via
PostgresAccountLookupResolver. Mirrors test_expense_execution_money_wiring.py.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.finance.commands import ManageMoneyAccountCommand
from mesiri.application.finance.handlers import ManageMoneyAccountHandler
from mesiri.application.finance.resolution import PostgresAccountLookupResolver
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.account_admin_execution import (
    PostgresAccountAdminExecutionRepository,
)
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository
from mesiri_contracts.application.results.execution_result import ExecutionStatus

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def scenario(engine: AsyncEngine):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Account Admin Test Org', 'local', "
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
    yield {"org_id": org_id, "user_id": user_id}
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


def _handler() -> ManageMoneyAccountHandler:
    return ManageMoneyAccountHandler(
        PostgresAccountAdminExecutionRepository(), resolver=PostgresAccountLookupResolver()
    )


def _command(scenario: dict, **overrides) -> ManageMoneyAccountCommand:
    base = dict(
        idempotency_key=f"acct-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        created_by_role="ADMIN",
        action="create",
        name="Site Cash",
    )
    base.update(overrides)
    return ManageMoneyAccountCommand(**base)


async def test_create_account_persists_and_is_active(engine: AsyncEngine, scenario: dict):
    handler = _handler()
    async with engine.begin() as conn:
        result = await handler.handle(conn, _command(scenario))

    assert result.status == ExecutionStatus.SUCCEEDED
    async with engine.connect() as conn:
        repo = PostgresMoneyAccountRepository(conn)
        account = await repo.get_by_id(scenario["org_id"], uuid.UUID(result.material_row_id))
    assert account is not None
    assert account.name == "Site Cash"
    assert account.status == "active"
    assert account.opening_balance == Decimal("0")


async def test_create_with_duplicate_name_is_rejected(engine: AsyncEngine, scenario: dict):
    handler = _handler()
    async with engine.begin() as conn:
        first = await handler.handle(conn, _command(scenario))
    assert first.status == ExecutionStatus.SUCCEEDED

    async with engine.begin() as conn:
        second = await handler.handle(conn, _command(scenario))

    assert second.status == ExecutionStatus.REJECTED
    assert "already exists" in second.rejection_reasons[0]


async def test_rename_changes_the_account_name(engine: AsyncEngine, scenario: dict):
    handler = _handler()
    async with engine.begin() as conn:
        created = await handler.handle(conn, _command(scenario))
    assert created.status == ExecutionStatus.SUCCEEDED

    async with engine.begin() as conn:
        renamed = await handler.handle(
            conn,
            _command(scenario, action="rename", name=None, target_name="Site Cash", new_name="Kochi Cash"),
        )
    assert renamed.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        repo = PostgresMoneyAccountRepository(conn)
        account = await repo.get_by_id(scenario["org_id"], uuid.UUID(created.material_row_id))
    assert account.name == "Kochi Cash"


async def test_rename_unknown_account_is_rejected(engine: AsyncEngine, scenario: dict):
    handler = _handler()
    async with engine.begin() as conn:
        result = await handler.handle(
            conn,
            _command(scenario, action="rename", name=None, target_name="Nonexistent", new_name="X"),
        )
    assert result.status == ExecutionStatus.REJECTED
    assert "no active account named" in result.rejection_reasons[0]


async def test_deactivate_flips_status_and_excludes_from_active_lookup(
    engine: AsyncEngine, scenario: dict
):
    handler = _handler()
    async with engine.begin() as conn:
        created = await handler.handle(conn, _command(scenario))
    assert created.status == ExecutionStatus.SUCCEEDED

    async with engine.begin() as conn:
        deactivated = await handler.handle(
            conn, _command(scenario, action="deactivate", name=None, target_name="Site Cash")
        )
    assert deactivated.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        repo = PostgresMoneyAccountRepository(conn)
        account = await repo.get_by_id(scenario["org_id"], uuid.UUID(created.material_row_id))
        still_findable_active = await repo.find_by_name_exact_active(scenario["org_id"], "Site Cash")
    assert account.status == "inactive"
    assert still_findable_active is None


async def test_replayed_idempotency_key_does_not_create_a_second_account(
    engine: AsyncEngine, scenario: dict
):
    handler = _handler()
    cmd = _command(scenario)
    async with engine.begin() as conn:
        first = await handler.handle(conn, cmd)
    async with engine.begin() as conn:
        second = await handler.handle(conn, cmd)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED
    async with engine.connect() as conn:
        count = (
            await conn.execute(
                sa.text(
                    "SELECT count(*) FROM money_accounts WHERE organization_id = :id AND name = 'Site Cash'"
                ),
                {"id": scenario["org_id"]},
            )
        ).scalar_one()
    assert count == 1
