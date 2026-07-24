"""Integration test for admin.router.delete_organization.

Regression coverage for the tenant hard-delete path. The finance refactor
(migrations 0320-0340) renamed finance_accounts -> money_accounts and
finance_account_transactions -> money_transactions, and added
expense_categories / expense_attachments / expense_payments / budgets /
budget_allocations. The delete handler wasn't updated, so deleting any tenant
that had finance data hit a non-existent `finance_account_transactions`
relation (500) and, past that, FK violations from the new child tables.

Migration 0361 fixed this at the schema level instead of by hand-patching the
handler again: every tenant-scoped table now has ON DELETE CASCADE on its
path back to organizations.id, so delete_organization collapses to a single
`DELETE FROM organizations`. See test_organizations_cascade_delete_schema.py
(backend/tests/integration) for the schema-level guard that catches a future
migration forgetting to extend that cascade; this test is the behavioral
counterpart — it seeds a full tenant, calls the handler, and asserts nothing
tenant-scoped survives, against a live Postgres. Requires the docker/CI
database, same convention as the other integration tests here.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from admin import router as admin_router

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    from mesiri.bootstrap.settings import Settings

    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture(autouse=True)
def _use_test_engine(test_engine: AsyncEngine, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(admin_router, "get_engine", lambda: test_engine)


async def _seed_full_tenant(engine: AsyncEngine) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """Insert an org plus one row in each finance/child table the delete
    handler is responsible for clearing, and return the org id."""
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    account_id = uuid.uuid4()
    category_id = uuid.uuid4()
    expense_id = uuid.uuid4()
    budget_id = uuid.uuid4()

    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Delete Me Org', 'local', 'default', "
                "'active', now(), now())"
            ),
            {"id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, created_at, updated_at) VALUES (:id, :org_id, :email, 'x', "
                "'Test', 'admin', 'active', now(), now())"
            ),
            {"id": user_id, "org_id": org_id, "email": f"{user_id}@example.com"},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Delete Me Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        # money_accounts (renamed from finance_accounts in 0320).
        await conn.execute(
            sa.text(
                "INSERT INTO money_accounts (id, organization_id, name, account_type, currency, "
                "opening_balance, opening_balance_date, status, created_by) VALUES (:id, :org_id, "
                "'Petty Cash', 'cash', 'INR', 1000.00, current_date, 'active', :user_id)"
            ),
            {"id": account_id, "org_id": org_id, "user_id": user_id},
        )
        # money_transactions (renamed from finance_account_transactions in 0340);
        # this is the table whose old name produced the 500.
        await conn.execute(
            sa.text(
                "INSERT INTO money_transactions (id, organization_id, to_account_id, amount, "
                "transaction_type, source_type, source_id, occurred_date, created_by) VALUES "
                "(:id, :org_id, :account_id, 500.00, 'fund_received', 'manual', :source_id, "
                "current_date, :user_id)"
            ),
            {
                "id": uuid.uuid4(),
                "org_id": org_id,
                "account_id": account_id,
                "source_id": uuid.uuid4(),
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'petty_cash', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expenses (id, organization_id, project_id, category_id, amount, "
                "currency, occurred_date, workflow_status, payment_status, source, created_by) "
                "VALUES (:id, :org_id, :project_id, :category_id, 250.00, 'INR', current_date, "
                "'confirmed', 'paid', 'whatsapp', :user_id)"
            ),
            {
                "id": expense_id,
                "org_id": org_id,
                "project_id": project_id,
                "category_id": category_id,
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_attachments (id, expense_id, media_object_key, "
                "attachment_type, created_by) VALUES (:id, :expense_id, 'receipts/x.jpg', "
                "'receipt', :user_id)"
            ),
            {"id": uuid.uuid4(), "expense_id": expense_id, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_payments (id, organization_id, expense_id, account_id, "
                "amount, paid_date, status, created_by) VALUES (:id, :org_id, :expense_id, "
                ":account_id, 250.00, current_date, 'confirmed', :user_id)"
            ),
            {
                "id": uuid.uuid4(),
                "org_id": org_id,
                "expense_id": expense_id,
                "account_id": account_id,
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO budgets (id, organization_id, project_id, name, amount, created_by) "
                "VALUES (:id, :org_id, :project_id, 'FY Budget', 100000.00, :user_id)"
            ),
            {"id": budget_id, "org_id": org_id, "project_id": project_id, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO budget_allocations (id, budget_id, category_id, amount, created_by) "
                "VALUES (:id, :budget_id, :category_id, 50000.00, :user_id)"
            ),
            {
                "id": uuid.uuid4(),
                "budget_id": budget_id,
                "category_id": category_id,
                "user_id": user_id,
            },
        )
    return org_id, expense_id, budget_id


async def test_delete_organization_clears_finance_refactor_tables(test_engine: AsyncEngine):
    org_id, expense_id, budget_id = await _seed_full_tenant(test_engine)

    # Must not raise: the old handler 500'd here on a missing
    # finance_account_transactions relation / FK violations.
    await admin_router.delete_organization(org_id, _admin={"sub": "platform-admin"})

    async with test_engine.connect() as conn:
        org_row = (
            await conn.execute(
                sa.text("SELECT id FROM organizations WHERE id = :id"), {"id": org_id}
            )
        ).first()
        assert org_row is None, "organization row should be gone"

        # No tenant-scoped rows may survive in any of the tables the handler
        # is responsible for.
        for table in (
            "users",
            "projects",
            "money_accounts",
            "money_transactions",
            "expense_categories",
            "expenses",
            "expense_payments",
            "budgets",
        ):
            count = (
                await conn.execute(
                    sa.text(
                        f"SELECT count(*) FROM {table} WHERE organization_id = :id"  # noqa: S608
                    ),
                    {"id": org_id},
                )
            ).scalar_one()
            assert count == 0, f"{table} still has rows for the deleted org"

        # expense_attachments and budget_allocations have no organization_id of
        # their own -- they only reach the org through expense_id/budget_id, so
        # they need their own check.
        attachments = (
            await conn.execute(
                sa.text("SELECT count(*) FROM expense_attachments WHERE expense_id = :id"),
                {"id": expense_id},
            )
        ).scalar_one()
        assert attachments == 0, "expense_attachments still has rows for the deleted expense"

        allocations = (
            await conn.execute(
                sa.text("SELECT count(*) FROM budget_allocations WHERE budget_id = :id"),
                {"id": budget_id},
            )
        ).scalar_one()
        assert allocations == 0, "budget_allocations still has rows for the deleted budget"
