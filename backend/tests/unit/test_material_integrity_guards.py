"""Unit tests for the Phase A integrity guards (no database required).

The DB-level halves of these guards -- migration 0459's partial unique index
and the advisory lock -- are covered by the integration tests in
tests/contract/test_materials_api_contract.py. What is tested here is the
application behaviour around them: that the pre-check refuses a second
correction with a useful message, and that losing the race to the index still
reads as "already corrected" rather than a 500.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from mesiri.domains.materials.router import (
    _assert_not_already_reversed,
    _reversal_race_as_conflict,
)


class _StubReadRepo:
    """Only the one method the guard calls."""

    def __init__(self, existing: dict | None):
        self._existing = existing
        self.calls: list[tuple[uuid.UUID, uuid.UUID]] = []

    async def find_reversal_of(self, organization_id, original_id):
        self.calls.append((organization_id, original_id))
        return self._existing


@pytest.mark.asyncio
async def test_first_correction_is_allowed():
    repo = _StubReadRepo(existing=None)
    org, original = uuid.uuid4(), uuid.uuid4()

    await _assert_not_already_reversed(repo, org, original)

    assert repo.calls == [(org, original)]


@pytest.mark.asyncio
async def test_second_correction_is_refused_with_conflict():
    """The defect this phase exists for: correcting twice does not undo twice,
    it posts a second offsetting movement and leaves stock wrong by double."""
    repo = _StubReadRepo(
        existing={
            "id": uuid.uuid4(),
            "occurred_date": datetime.date(2026, 7, 12),
            "created_at": None,
            "created_by": None,
        }
    )

    with pytest.raises(HTTPException) as exc:
        await _assert_not_already_reversed(repo, uuid.uuid4(), uuid.uuid4())

    assert exc.value.status_code == 409
    assert "already corrected" in exc.value.detail
    # The date matters: "already corrected" alone leaves the user hunting for
    # which correction, and whether it was theirs.
    assert "2026-07-12" in exc.value.detail


@pytest.mark.asyncio
async def test_conflict_message_survives_a_missing_date():
    repo = _StubReadRepo(existing={"id": uuid.uuid4(), "occurred_date": None})

    with pytest.raises(HTTPException) as exc:
        await _assert_not_already_reversed(repo, uuid.uuid4(), uuid.uuid4())

    assert exc.value.status_code == 409
    assert "already corrected" in exc.value.detail


def _integrity_error(message: str) -> IntegrityError:
    return IntegrityError("INSERT ...", {}, Exception(message))


def test_losing_the_reversal_race_reads_as_conflict_not_500():
    """Two people tapping Correct at the same moment both pass the pre-check
    (each reads before the other writes). 0459's index stops the second one --
    that loss must not surface as an unhandled 500."""
    with pytest.raises(HTTPException) as exc:  # noqa: PT012 - context manager under test
        with _reversal_race_as_conflict():
            raise _integrity_error(
                'duplicate key value violates unique constraint '
                '"uq_material_usage_reverses_movement_id"'
            )

    assert exc.value.status_code == 409
    assert "already corrected" in exc.value.detail


def test_unrelated_integrity_errors_are_not_swallowed():
    """Mapping every IntegrityError to 409 would hide real bugs -- a broken FK
    would silently read to the user as 'already corrected'."""
    with pytest.raises(IntegrityError):  # noqa: PT012 - context manager under test
        with _reversal_race_as_conflict():
            raise _integrity_error(
                'insert or update on table "material_usage" violates foreign key '
                'constraint "material_usage_material_id_fkey"'
            )


def test_guard_passes_through_when_nothing_raises():
    with _reversal_race_as_conflict():
        result = "committed"
    assert result == "committed"
