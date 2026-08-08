"""ExecutionResult.conflict_note (#12 Conflict Resolution) -- invariants.

Additive field: must be usable on SUCCEEDED/ALREADY_EXECUTED, and forbidden
on REJECTED/FAILED (a genuinely-refused or crashed execution has nothing
partial to note -- conflict_note describes a write that DID happen, with one
narrower side effect held back).
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from mesiri_contracts.application.results.execution_result import (
    ExecutionResult,
    ExecutionStatus,
    as_replay,
)


def test_conflict_note_defaults_to_none():
    result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED, idempotency_key="k1", material_row_id="row_1"
    )
    assert result.conflict_note is None


def test_conflict_note_allowed_on_succeeded():
    result = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED,
        idempotency_key="k1",
        material_row_id="row_1",
        conflict_note="status held back",
    )
    assert result.conflict_note == "status held back"


def test_conflict_note_allowed_on_already_executed():
    result = ExecutionResult(
        status=ExecutionStatus.ALREADY_EXECUTED,
        idempotency_key="k1",
        material_row_id="row_1",
        conflict_note="status held back",
    )
    assert result.conflict_note == "status held back"


def test_conflict_note_forbidden_on_rejected():
    with pytest.raises(ValidationError):
        ExecutionResult(
            status=ExecutionStatus.REJECTED,
            idempotency_key="k1",
            rejection_reasons=["bad"],
            conflict_note="should not be allowed",
        )


def test_conflict_note_forbidden_on_failed():
    with pytest.raises(ValidationError):
        ExecutionResult(
            status=ExecutionStatus.FAILED, idempotency_key="k1", conflict_note="should not be allowed"
        )


def test_as_replay_preserves_conflict_note():
    original = ExecutionResult(
        status=ExecutionStatus.SUCCEEDED,
        idempotency_key="k1",
        material_row_id="row_1",
        conflict_note="status held back",
    )
    replay = as_replay(original)
    assert replay.status is ExecutionStatus.ALREADY_EXECUTED
    assert replay.conflict_note == "status held back"
