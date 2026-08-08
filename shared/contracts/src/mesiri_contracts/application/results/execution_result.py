"""ExecutionResult.v1 — the typed outcome of executing a confirmed Application Command (M8).

A discriminated result, invariants enforced per status — mirrors
WorkflowRunResult/WorkflowResumeResult (workflows/runtime.py). FAILED is never
constructed by a repository: it is what the Handler reports if the whole
execution raises (an unhandled exception rolls back the transaction and
leaves the workflow at CONFIRMED, recoverable — see the M8 plan's recovery
section). REJECTED, by contrast, is a deliberate, committed, terminal
business outcome.

Ownership: SHARED ARCHITECTURE — part of the M0 contract surface. Version: v1.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

CONTRACT_VERSION = "v1"


class ExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    ALREADY_EXECUTED = "already_executed"
    REJECTED = "rejected"
    FAILED = "failed"


class ExecutionResult(BaseModel):
    version: str = CONTRACT_VERSION

    status: ExecutionStatus
    idempotency_key: str
    material_row_id: str | None = None
    rejection_reasons: list[str] = Field(default_factory=list)
    # Conflict Resolution (#12): set only on a SUCCEEDED/ALREADY_EXECUTED
    # result whose write partially yielded to a genuine concurrent conflict
    # -- e.g. two engineers reporting different Activity status transitions
    # at once. The write that COULD safely proceed (an append-only Progress
    # Update) still did; the part that would have silently overwritten
    # someone else's already-applied change (the status mutation) did not.
    # None is the overwhelmingly common case: nothing to say. This is
    # deliberately NOT a REJECTED outcome -- the confirmed action was not
    # refused, it succeeded with one narrower side effect held back, and the
    # user needs to know that, not be told their report failed.
    conflict_note: str | None = None

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _invariants(self) -> ExecutionResult:
        if self.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED):
            if self.material_row_id is None:
                raise ValueError(f"{self.status.value} requires material_row_id")
            if self.rejection_reasons:
                raise ValueError(f"{self.status.value} must not carry rejection_reasons")
        elif self.status is ExecutionStatus.REJECTED:
            if not self.rejection_reasons:
                raise ValueError("REJECTED requires rejection_reasons")
            if self.material_row_id is not None:
                raise ValueError("REJECTED must not carry material_row_id")
            if self.conflict_note is not None:
                raise ValueError("REJECTED must not carry conflict_note")
        else:  # FAILED
            if self.material_row_id is not None or self.rejection_reasons:
                raise ValueError("FAILED must not carry material_row_id or rejection_reasons")
            if self.conflict_note is not None:
                raise ValueError("FAILED must not carry conflict_note")
        return self


def as_replay(result: ExecutionResult) -> ExecutionResult:
    """Remap a cached SUCCEEDED result to ALREADY_EXECUTED for a caller that
    did not itself perform the write (an idempotent replay — either a
    sequential re-check finding prior work already done, or the losing side
    of a genuine concurrent race). REJECTED is returned unchanged: a repeat
    rejection is still accurately described as REJECTED, and ALREADY_EXECUTED
    requires a material_row_id a rejection never has."""
    if result.status is ExecutionStatus.SUCCEEDED:
        return result.model_copy(update={"status": ExecutionStatus.ALREADY_EXECUTED})
    return result
