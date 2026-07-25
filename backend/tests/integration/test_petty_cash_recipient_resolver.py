"""Integration tests for PostgresPettyCashRecipientResolver: resolves a
recipient's name to their employee-advance account, auto-creating it on
first issuance (exactly once -- a second issuance reuses it), and leaves an
unrecognized name unresolved (Finance Module Slice 5, Linear STA-147)."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.finance.petty_cash_resolution import PostgresPettyCashRecipientResolver
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository

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
    admin_id = uuid.uuid4()
    alan_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Petty Cash Org', 'local', 'default', "
                "'active', now(), now())"
            ),
            {"id": org_id},
        )
        for user_id, name in ((admin_id, "Admin"), (alan_id, "Alan")):
            await conn.execute(
                sa.text(
                    "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                    "role, status, access_policy, created_at, updated_at) "
                    "VALUES (:id, :org_id, :email, 'x', :name, 'admin', 'active', "
                    "CAST(:policy AS jsonb), now(), now())"
                ),
                {
                    "id": user_id,
                    "org_id": org_id,
                    "email": f"{user_id}@example.com",
                    "name": name,
                    "policy": '{"mode": "all_projects", "projects": []}',
                },
            )
    yield {"org_id": org_id, "admin_id": admin_id, "alan_id": alan_id}
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def test_first_issuance_auto_creates_the_advance_account(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        resolver = PostgresPettyCashRecipientResolver()
        account = await resolver.resolve_or_create_advance_account(
            conn, scenario["org_id"], "alan", created_by=scenario["admin_id"]  # case-insensitive
        )
    assert account is not None
    assert account.account_type == "employee_advance"
    assert account.owner_user_id == scenario["alan_id"]
    assert account.name == "Alan — Petty Cash"
    assert account.opening_balance == Decimal("0")


async def test_second_issuance_reuses_the_same_account(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        resolver = PostgresPettyCashRecipientResolver()
        first = await resolver.resolve_or_create_advance_account(
            conn, scenario["org_id"], "Alan", created_by=scenario["admin_id"]
        )
        second = await resolver.resolve_or_create_advance_account(
            conn, scenario["org_id"], "Alan", created_by=scenario["admin_id"]
        )
    assert first.id == second.id

    async with engine.connect() as conn:
        accounts = PostgresMoneyAccountRepository(conn)
        all_advances = await accounts.list_accounts(
            scenario["org_id"], account_type="employee_advance"
        )
    assert len(all_advances) == 1


async def test_unrecognized_recipient_name_resolves_to_none(engine: AsyncEngine, scenario: dict):
    async with engine.begin() as conn:
        resolver = PostgresPettyCashRecipientResolver()
        account = await resolver.resolve_or_create_advance_account(
            conn, scenario["org_id"], "Someone Who Does Not Exist", created_by=scenario["admin_id"]
        )
    assert account is None
