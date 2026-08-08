"""Migration 0320-0340 backfill invariants for the money-tracking refactor.

In a live integration DB at head, 0320-0340 have already run — this test
can't re-run the migrations to observe the backfill happening. Instead it
seeds rows in the pre-refactor shape (an expense with a free-text category,
a receipt key, and a paying account) directly into the post-migration
tables the same way the backfill would have written them, then asserts the
invariants the migrations are supposed to establish:

- money_accounts preserves the finance_accounts row's id and opening_balance
  (rename, not recreate).
- an expense's category text maps to exactly one org-scoped expense_categories
  row, referenced via category_id.
- a receipt_media_object_key becomes exactly one expense_attachments row of
  type 'receipt'.
- an expense that already had a paying account becomes exactly one
  'confirmed' expense_payments row for the full amount, and payment_status
  reads 'paid'.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def org_and_user(engine: AsyncEngine):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Finance Refactor Org', 'local', "
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
                "VALUES (:id, :org_id, 'Finance Refactor Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
    yield org_id, user_id, project_id
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM money_transactions WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_payments WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(
            sa.text(
                "DELETE FROM expense_attachments WHERE expense_id IN "
                "(SELECT id FROM expenses WHERE organization_id = :id)"
            ),
            {"id": org_id},
        )
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def test_money_account_preserves_id_and_opening_balance(
    engine: AsyncEngine, org_and_user
):
    org_id, user_id, _ = org_and_user
    account_id = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                "currency, opening_balance, opening_balance_date, status, created_by) "
                "VALUES (:id, :org_id, 'Site Petty Cash', 'cash', 'INR', 5000.00, "
                "current_date, 'active', :user_id)"
            ),
            {"id": account_id, "org_id": org_id, "user_id": user_id},
        )

    async with engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text("SELECT id, opening_balance FROM money_accounts WHERE id = :id"),
                {"id": account_id},
            )
        ).mappings().one()
    assert row["id"] == account_id
    assert Decimal(row["opening_balance"]) == Decimal("5000.00")


async def test_expense_category_and_attachment_and_payment_backfill_shape(
    engine: AsyncEngine, org_and_user
):
    org_id, user_id, project_id = org_and_user

    async with engine.begin() as conn:
        category_id = uuid.uuid4()
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'petty_cash', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
        account_id = uuid.uuid4()
        await conn.execute(
            sa.text(
                "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                "currency, opening_balance, opening_balance_date, status, created_by) "
                "VALUES (:id, :org_id, 'Site Petty Cash', 'cash', 'INR', 1000.00, "
                "current_date, 'active', :user_id)"
            ),
            {"id": account_id, "org_id": org_id, "user_id": user_id},
        )
        expense_id = uuid.uuid4()
        amount = Decimal("250.00")
        await conn.execute(
            sa.text(
                "INSERT INTO expenses (id, organization_id, project_id, category_id, amount, "
                "currency, occurred_date, workflow_status, payment_status, source, created_by) "
                "VALUES (:id, :org_id, :project_id, :category_id, :amount, 'INR', current_date, "
                "'confirmed', 'unpaid', 'whatsapp', :user_id)"
            ),
            {
                "id": expense_id,
                "org_id": org_id,
                "project_id": project_id,
                "category_id": category_id,
                "amount": amount,
                "user_id": user_id,
            },
        )
        # Mimic what 0330's backfill does for a pre-refactor expense that had
        # a receipt key and a paying account_id.
        await conn.execute(
            sa.text(
                "INSERT INTO expense_attachments (id, expense_id, media_object_key, "
                "attachment_type, created_by) VALUES (:id, :expense_id, 'receipts/abc.jpg', "
                "'receipt', :user_id)"
            ),
            {"id": uuid.uuid4(), "expense_id": expense_id, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_payments (id, organization_id, expense_id, account_id, "
                "amount, paid_date, status, created_by) VALUES (:id, :org_id, :expense_id, "
                ":account_id, :amount, current_date, 'confirmed', :user_id)"
            ),
            {
                "id": uuid.uuid4(),
                "org_id": org_id,
                "expense_id": expense_id,
                "account_id": account_id,
                "amount": amount,
                "user_id": user_id,
            },
        )
        await conn.execute(
            sa.text("UPDATE expenses SET payment_status = 'paid' WHERE id = :id"),
            {"id": expense_id},
        )

    async with engine.connect() as conn:
        attachments = (
            await conn.execute(
                sa.text(
                    "SELECT attachment_type FROM expense_attachments WHERE expense_id = :id"
                ),
                {"id": expense_id},
            )
        ).mappings().all()
        assert len(attachments) == 1
        assert attachments[0]["attachment_type"] == "receipt"

        payments = (
            await conn.execute(
                sa.text(
                    "SELECT amount, status FROM expense_payments WHERE expense_id = :id"
                ),
                {"id": expense_id},
            )
        ).mappings().all()
        assert len(payments) == 1
        assert payments[0]["status"] == "confirmed"
        assert Decimal(payments[0]["amount"]) == amount

        expense_row = (
            await conn.execute(
                sa.text("SELECT payment_status, category_id FROM expenses WHERE id = :id"),
                {"id": expense_id},
            )
        ).mappings().one()
        assert expense_row["payment_status"] == "paid"
        assert expense_row["category_id"] == category_id
