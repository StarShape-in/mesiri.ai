"""Unit tests for AdminFinanceSeedingService using mocked AsyncConnection."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from mesiri.domains.finance.seeder import AdminFinanceSeedingService


@pytest.mark.anyio
async def test_seed_organization_empty():
    conn = AsyncMock()

    # Mock execute returns empty rows for initial checks
    mock_empty_result = MagicMock()
    mock_empty_result.first.return_value = None
    mock_empty_result.scalar.return_value = 0

    conn.execute.return_value = mock_empty_result

    seeder = AdminFinanceSeedingService(conn)
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    result = await seeder.seed_organization(
        organization_id=org_id,
        created_by=admin_id,
        include_demo_transactions=True,
    )

    assert result["categories_created"] == 8
    assert result["accounts_created"] == 3
    assert result["vendors_created"] == 4
    assert result["settings_created"] == 3
    assert result["expenses_created"] == 4
    assert result["transactions_created"] == 5
    assert conn.execute.call_count > 10


@pytest.mark.anyio
async def test_seed_organization_already_seeded():
    conn = AsyncMock()

    # Mock execute returns existing row for checks
    mock_existing_row = MagicMock()
    mock_existing_row.id = uuid.uuid4()
    mock_existing_result = MagicMock()
    mock_existing_result.first.return_value = mock_existing_row
    mock_existing_result.scalar.return_value = 10  # existing transactions count

    conn.execute.return_value = mock_existing_result

    seeder = AdminFinanceSeedingService(conn)
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    result = await seeder.seed_organization(
        organization_id=org_id,
        created_by=admin_id,
        include_demo_transactions=True,
    )

    assert result["categories_created"] == 0
    assert result["accounts_created"] == 0
    assert result["vendors_created"] == 0
    assert result["settings_created"] == 0
    assert result["expenses_created"] == 0
    assert result["transactions_created"] == 0


@pytest.mark.anyio
async def test_seed_organization_existing_category_by_name():
    conn = AsyncMock()

    # Simulate existing categories when queried by sa.or_(name == ..., code == ...)
    mock_user_row = MagicMock(id=uuid.uuid4())
    mock_cat_row = MagicMock(id=uuid.uuid4())

    def side_effect(query, *args, **kwargs):
        query_str = str(query)
        res = MagicMock()
        if "users" in query_str:
            res.first.return_value = mock_user_row
            res.scalar_one_or_none.return_value = mock_user_row.id
        elif "expense_categories" in query_str:
            # Simulate pre-existing category for Equipment Rental
            res.first.return_value = mock_cat_row
        else:
            res.first.return_value = None
            res.scalar.return_value = 0
        return res

    conn.execute.side_effect = side_effect

    seeder = AdminFinanceSeedingService(conn)
    org_id = uuid.uuid4()
    admin_id = uuid.uuid4()

    result = await seeder.seed_organization(
        organization_id=org_id,
        created_by=admin_id,
        include_demo_transactions=True,
    )

    # All 8 categories match existing categories, so 0 newly created
    assert result["categories_created"] == 0

