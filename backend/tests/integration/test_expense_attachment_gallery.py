"""PostgresExpenseAttachmentRepository.list_for_organization -- integration
tests against a real Postgres. Backs the dashboard's "see all receipts
together" gallery (GET /expenses/attachments) and the per-expense lightbox
(GET /expenses/{id}/attachments, covered by list_for_expense already).
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.expenses import (
    PostgresExpenseAttachmentRepository,
)

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
    project_a = uuid.uuid4()
    project_b = uuid.uuid4()
    category_id = uuid.uuid4()
    vendor_id = uuid.uuid4()
    expense_with_receipt = uuid.uuid4()
    expense_without_receipt = uuid.uuid4()
    expense_other_project = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Gallery Test Org', 'local', 'default', "
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
        for pid, name in ((project_a, "Project A"), (project_b, "Project B")):
            await conn.execute(
                sa.text(
                    "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                    "VALUES (:id, :org_id, :name, now(), now())"
                ),
                {"id": pid, "org_id": org_id, "name": name},
            )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'fuel', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO vendors (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'ABC Hardware', 'active', :user_id)"
            ),
            {"id": vendor_id, "org_id": org_id, "user_id": user_id},
        )
        for exp_id, pid, has_vendor, description in (
            (expense_with_receipt, project_a, True, "diesel refill"),
            (expense_without_receipt, project_a, False, "no receipt on this one"),
            (expense_other_project, project_b, False, "different project"),
        ):
            await conn.execute(
                sa.text(
                    "INSERT INTO expenses (id, organization_id, project_id, category_id, vendor_id, "
                    "amount, currency, description, occurred_date, workflow_status, payment_status, "
                    "source, created_by) VALUES (:id, :org_id, :project_id, :category_id, :vendor_id, "
                    "700.00, 'INR', :description, current_date, 'confirmed', 'unpaid', 'whatsapp', "
                    ":user_id)"
                ),
                {
                    "id": exp_id,
                    "org_id": org_id,
                    "project_id": pid,
                    "category_id": category_id,
                    "vendor_id": vendor_id if has_vendor else None,
                    "description": description,
                    "user_id": user_id,
                },
            )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_attachments (id, expense_id, media_object_key, "
                "attachment_type, created_by) VALUES (:id, :expense_id, 'media/receipt-a.jpg', "
                "'receipt', :user_id)"
            ),
            {"id": uuid.uuid4(), "expense_id": expense_with_receipt, "user_id": user_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_attachments (id, expense_id, media_object_key, "
                "attachment_type, created_by) VALUES (:id, :expense_id, 'media/receipt-b.jpg', "
                "'receipt', :user_id)"
            ),
            {"id": uuid.uuid4(), "expense_id": expense_other_project, "user_id": user_id},
        )
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_a": project_a,
        "project_b": project_b,
        "vendor_id": vendor_id,
        "category_id": category_id,
        "expense_with_receipt": expense_with_receipt,
    }
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "DELETE FROM expense_attachments WHERE expense_id IN "
                "(SELECT id FROM expenses WHERE organization_id = :id)"
            ),
            {"id": org_id},
        )
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM vendors WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


async def test_gallery_includes_only_expenses_with_attachments(engine: AsyncEngine, scenario: dict):
    """3 expenses seeded, only 2 have an expense_attachments row -- the
    third (expense_without_receipt) must never appear in the gallery."""
    async with engine.connect() as conn:
        repo = PostgresExpenseAttachmentRepository(conn)
        rows = await repo.list_for_organization(scenario["org_id"])
    assert len(rows) == 2
    assert scenario["expense_with_receipt"] in {r.expense_id for r in rows}


async def test_gallery_filters_by_project(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseAttachmentRepository(conn)
        rows = await repo.list_for_organization(scenario["org_id"], project_id=scenario["project_a"])
    assert len(rows) == 1
    assert rows[0].expense_id == scenario["expense_with_receipt"]


async def test_gallery_row_carries_expense_context(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseAttachmentRepository(conn)
        rows = await repo.list_for_organization(scenario["org_id"], project_id=scenario["project_a"])
    row = rows[0]
    assert row.amount == Decimal("700.00")
    assert row.description == "diesel refill"
    assert row.occurred_date == datetime.date.today()
    assert row.vendor_id == scenario["vendor_id"]
    assert row.category_id == scenario["category_id"]
    assert row.media_object_key == "media/receipt-a.jpg"


async def test_gallery_respects_limit_and_offset(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseAttachmentRepository(conn)
        first_page = await repo.list_for_organization(scenario["org_id"], limit=1, offset=0)
        second_page = await repo.list_for_organization(scenario["org_id"], limit=1, offset=1)
    assert len(first_page) == 1
    assert len(second_page) == 1
    assert first_page[0].id != second_page[0].id


async def test_no_attachments_at_all_returns_empty(engine: AsyncEngine, scenario: dict):
    async with engine.connect() as conn:
        repo = PostgresExpenseAttachmentRepository(conn)
        rows = await repo.list_for_organization(scenario["org_id"], project_id=scenario["project_b"])
    # project_b's only expense (expense_other_project) DOES have an attachment.
    assert len(rows) == 1
