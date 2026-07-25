"""Transfer execution — integration tests against a real Postgres.

Covers the full Handler -> PostgresTransferExecutionRepository path: exactly
one money_transactions row per transfer, both accounts' balances move
correctly (one down, one up, by the same amount), inactive-account
rejection via PostgresTransferAccountResolver, and idempotent replay.
Mirrors test_expense_execution_money_wiring.py / test_account_admin_execution.py.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.finance.transfer_commands import TransferMoneyCommand
from mesiri.application.finance.transfer_handler import TransferMoneyHandler
from mesiri.application.finance.transfer_resolution import PostgresTransferAccountResolver
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository
from mesiri.infrastructure.postgres.repositories.transfer_execution import (
    PostgresTransferExecutionRepository,
)
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
    account_a = uuid.uuid4()
    account_b = uuid.uuid4()
    inactive_account = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Transfer Test Org', 'local', 'default', "
                "'active', now(), now())"
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
        for acc_id, name, status in (
            (account_a, "Company Bank", "active"),
            (account_b, "Site Cash", "active"),
            (inactive_account, "Closed Account", "inactive"),
        ):
            await conn.execute(
                sa.text(
                    "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                    "currency, opening_balance, opening_balance_date, status, created_by) "
                    "VALUES (:id, :org_id, :name, 'cash', 'INR', 10000.00, current_date, "
                    ":status, :user_id)"
                ),
                {"id": acc_id, "org_id": org_id, "name": name, "status": status, "user_id": user_id},
            )
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "account_a": account_a,
        "account_b": account_b,
        "inactive_account": inactive_account,
    }
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM money_transactions WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM users WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM idempotency_keys WHERE command_type = 'transfer_money'"))
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


def _handler() -> TransferMoneyHandler:
    return TransferMoneyHandler(
        PostgresTransferExecutionRepository(), resolver=PostgresTransferAccountResolver()
    )


def _command(scenario: dict, **overrides) -> TransferMoneyCommand:
    import datetime

    base = dict(
        idempotency_key=f"xfer-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        created_by_role="ADMIN",
        from_account_id=str(scenario["account_a"]),
        to_account_id=str(scenario["account_b"]),
        amount=Decimal("1500.00"),
        occurred_date=datetime.date.today(),
    )
    base.update(overrides)
    return TransferMoneyCommand(**base)


async def test_transfer_creates_one_ledger_row_and_moves_both_balances(
    engine: AsyncEngine, scenario: dict
):
    handler = _handler()
    async with engine.begin() as conn:
        result = await handler.handle(conn, _command(scenario))

    assert result.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        ledger_count = (
            await conn.execute(
                sa.text(
                    "SELECT count(*) FROM money_transactions "
                    "WHERE transaction_type = 'transfer' AND organization_id = :org_id"
                ),
                {"org_id": scenario["org_id"]},
            )
        ).scalar_one()
        accounts = PostgresMoneyAccountRepository(conn)
        from_balance = await accounts.get_balance(scenario["org_id"], scenario["account_a"])
        to_balance = await accounts.get_balance(scenario["org_id"], scenario["account_b"])

    assert ledger_count == 1
    assert from_balance == Decimal("10000.00") - Decimal("1500.00")
    assert to_balance == Decimal("10000.00") + Decimal("1500.00")


async def test_transfer_from_inactive_account_is_rejected(engine: AsyncEngine, scenario: dict):
    handler = _handler()
    async with engine.begin() as conn:
        result = await handler.handle(
            conn, _command(scenario, from_account_id=str(scenario["inactive_account"]))
        )

    assert result.status == ExecutionStatus.REJECTED
    assert "the source account is not active" in result.rejection_reasons

    async with engine.connect() as conn:
        ledger_count = (
            await conn.execute(
                sa.text("SELECT count(*) FROM money_transactions WHERE organization_id = :org_id"),
                {"org_id": scenario["org_id"]},
            )
        ).scalar_one()
    assert ledger_count == 0


async def test_replayed_idempotency_key_does_not_double_post(engine: AsyncEngine, scenario: dict):
    handler = _handler()
    cmd = _command(scenario)
    async with engine.begin() as conn:
        first = await handler.handle(conn, cmd)
    async with engine.begin() as conn:
        second = await handler.handle(conn, cmd)

    assert first.status == ExecutionStatus.SUCCEEDED
    assert second.status == ExecutionStatus.ALREADY_EXECUTED

    async with engine.connect() as conn:
        accounts = PostgresMoneyAccountRepository(conn)
        from_balance = await accounts.get_balance(scenario["org_id"], scenario["account_a"])
    assert from_balance == Decimal("10000.00") - Decimal("1500.00")
