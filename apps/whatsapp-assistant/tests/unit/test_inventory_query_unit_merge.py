"""Unit tests for MaterialInventoryQueryService's unit-merging logic."""

from __future__ import annotations

from decimal import Decimal

import pytest

from runtime.inventory_query import MaterialInventoryQueryService

ORG = "11111111-1111-4111-8111-111111111111"


class _FakeConn:
    pass


class _FakeTxn:
    async def __aenter__(self):
        return _FakeConn()

    async def __aexit__(self, *exc):
        return False


class _FakeDb:
    def transaction(self):
        return _FakeTxn()


@pytest.mark.anyio
async def test_merges_unit_synonyms_for_the_same_material(monkeypatch):
    rows = [
        {"material_name": "cement", "unit": "sack", "total_received": Decimal("80"), "total_used": Decimal("0"), "current_stock": Decimal("80")},
        {"material_name": "cement", "unit": "bag", "total_received": Decimal("46"), "total_used": Decimal("0"), "current_stock": Decimal("46")},
        {"material_name": "cement", "unit": "bags", "total_received": Decimal("56"), "total_used": Decimal("0"), "current_stock": Decimal("56")},
    ]

    class _FakeRepo:
        def __init__(self, conn):
            pass

        async def get_stock_levels(self, **kwargs):
            return rows

    monkeypatch.setattr(
        "mesiri.infrastructure.postgres.repositories.materials.PostgresMaterialReadRepository",
        _FakeRepo,
    )

    service = MaterialInventoryQueryService(_FakeDb())
    levels = await service.query(
        organization_id=ORG, project_id=None, site_id=None, material_name="cement"
    )

    assert len(levels) == 1
    assert levels[0]["unit"] == "bags"
    assert levels[0]["current_stock"] == 182.0
