"""Finance Module Slice 0: MoneyAccountQueryService.list_accounts must
bootstrap a default account for an org with zero money_accounts, and must
never bootstrap a second one -- a slot-fill candidate list (Slice 1) must
never be handed an empty list nor accumulate duplicate default accounts.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.database import PostgresDatabase
from runtime.money_account_query import MoneyAccountQueryService

pytestmark = pytest.mark.integration


@pytest.fixture
async def db():
    settings = Settings()
    database = PostgresDatabase(settings.postgres)
    await database.connect()
    yield database
    await database.disconnect()


@pytest.fixture
async def org(db: PostgresDatabase):
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn())
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Bootstrap Test Org', 'local', 'default', "
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
    yield {"org_id": org_id, "user_id": user_id}
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
    await engine.dispose()


async def test_bootstraps_one_default_account_for_a_zero_account_org(
    db: PostgresDatabase, org: dict
):
    service = MoneyAccountQueryService(db)

    accounts = await service.list_accounts(
        organization_id=str(org["org_id"]), created_by=str(org["user_id"])
    )

    assert len(accounts) == 1
    assert accounts[0].name == "Site Cash"
    assert accounts[0].account_type == "cash"
    assert accounts[0].organization_id == org["org_id"]


async def test_second_call_does_not_create_a_second_default_account(
    db: PostgresDatabase, org: dict
):
    service = MoneyAccountQueryService(db)

    first = await service.list_accounts(
        organization_id=str(org["org_id"]), created_by=str(org["user_id"])
    )
    second = await service.list_accounts(
        organization_id=str(org["org_id"]), created_by=str(org["user_id"])
    )

    assert len(second) == 1
    assert second[0].id == first[0].id


async def test_existing_accounts_are_returned_without_bootstrapping(
    db: PostgresDatabase, org: dict
):
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn())
    manual_account_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                "currency, opening_balance, opening_balance_date, status, created_by) "
                "VALUES (:id, :org_id, 'Company Bank', 'bank', 'INR', 100000.00, "
                "current_date, 'active', :user_id)"
            ),
            {"id": manual_account_id, "org_id": org["org_id"], "user_id": org["user_id"]},
        )
    await engine.dispose()

    service = MoneyAccountQueryService(db)
    accounts = await service.list_accounts(
        organization_id=str(org["org_id"]), created_by=str(org["user_id"])
    )

    assert len(accounts) == 1
    assert accounts[0].id == manual_account_id
    assert accounts[0].name == "Company Bank"
