"""ExpenseExecutionResult — the typed outcome of executing a RecordExpense command.

Mirrors mesiri_contracts.application.results.execution_result.ExecutionResult's
shape/invariants, kept local (see commands.py's docstring for why) with
`expense_id` in place of `material_row_id`.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator


class ExecutionStatus(str, Enum):
    SUCCEEDED = "succeeded"
    ALREADY_EXECUTED = "already_executed"
    REJECTED = "rejected"


class ExpenseExecutionResult(BaseModel):
    status: ExecutionStatus
    idempotency_key: str
    expense_id: str | None = None
    rejection_reasons: list[str] = Field(default_factory=list)

    model_config = {"extra": "forbid"}

    @model_validator(mode="after")
    def _invariants(self) -> ExpenseExecutionResult:
        if self.status in (ExecutionStatus.SUCCEEDED, ExecutionStatus.ALREADY_EXECUTED):
            if self.expense_id is None:
                raise ValueError(f"{self.status.value} requires expense_id")
            if self.rejection_reasons:
                raise ValueError(f"{self.status.value} must not carry rejection_reasons")
        else:  # REJECTED
            if not self.rejection_reasons:
                raise ValueError("REJECTED requires rejection_reasons")
            if self.expense_id is not None:
                raise ValueError("REJECTED must not carry expense_id")
        return self


def as_replay(result: ExpenseExecutionResult) -> ExpenseExecutionResult:
    """Remap a cached SUCCEEDED result to ALREADY_EXECUTED for a caller that did
    not itself perform the write — a repeat REJECTED is returned unchanged."""
    if result.status is ExecutionStatus.SUCCEEDED:
        return result.model_copy(update={"status": ExecutionStatus.ALREADY_EXECUTED})
    return result
