"""Unit tests for MaterialInventoryQueryService's passthrough of get_stock_levels.

Previously this module also merged unit spelling variants ("bag"/"bags"/
"sack") at read time, because material_receipts/material_usage stored
whatever free-text unit extraction produced. Migration 0290/0300 replaced
that with a real units_of_measure FK + material_movements ledger — the
repository's get_stock_levels now groups by unit_id and always returns one
canonical unit code per material, so there is nothing left to merge here;
the old alias-merge test (asserting three raw-string rows collapse into one)
no longer reflects anything the repository can produce. This test now only
covers that MaterialInventoryQueryService passes rows through and applies
the material_name filter, which is still this module's job.
"""

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
async def test_passes_through_canonical_rows_and_filters_by_material_name(monkeypatch):
    rows = [
        {
            "material_name": "cement",
            "unit": "bags",
            "total_received": Decimal("182"),
            "total_used": Decimal("0"),
            "current_stock": Decimal("182"),
        },
        {
            "material_name": "sand",
            "unit": "tons",
            "total_received": Decimal("10"),
            "total_used": Decimal("0"),
            "current_stock": Decimal("10"),
        },
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
