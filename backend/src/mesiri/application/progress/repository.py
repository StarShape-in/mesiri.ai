"""Progress execution repository port (Daily Reporting).

Defines the contract for persisting confirmed Progress commands without
coupling to a specific implementation (PostgreSQL, fake, etc.). Mirrors
application/labour/repository.py and application/materials/repository.py:
every method takes an externally-supplied connection — the repository never
opens an engine and never commits; the Application Handler owns the one
transaction.

Two success-persist methods, not one, matching the two commands this module
has (create vs continue) — see mesiri_contracts.application.commands.progress
for why they are not merged into a single shape. `persist_rejection` is
shared because rejecting either command is the same act: cache the outcome,
transition the workflow, write nothing to the Activity/Progress Update
tables.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from mesiri_contracts.application.commands.progress import (
    AddProgressUpdateCommand,
    AttachEvidenceCommand,
    CloseSiteIssueCommand,
    CorrectActivityQuantityCommand,
    CreateActivityCommand,
    ReportSiteIssueCommand,
)
from mesiri_contracts.application.results.execution_result import ExecutionResult

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


class ProgressExecutionRepository(ABC):
    """Persists Progress command execution outcomes against a supplied connection."""

    @abstractmethod
    async def check_idempotency(self, conn: AsyncConnection, key: str) -> ExecutionResult | None:
        """Return the cached ExecutionResult if `key` was already claimed, else None."""
        ...

    @abstractmethod
    async def persist_create_activity_success(
        self, conn: AsyncConnection, cmd: CreateActivityCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, insert the activity + quantities + outbox
        event, cache SUCCEEDED, and transition the workflow to COMPLETED."""
        ...

    @abstractmethod
    async def persist_add_progress_update_success(
        self, conn: AsyncConnection, cmd: AddProgressUpdateCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, append the progress update + outbox
        event, cache SUCCEEDED, and transition the workflow to COMPLETED.
        Never edits the parent Activity or any prior update (P1)."""
        ...

    @abstractmethod
    async def persist_attach_evidence(
        self, conn: AsyncConnection, cmd: AttachEvidenceCommand
    ) -> list[str]:
        """Insert one progress_attachments row per media_object_key (#2 Batch
        Media). No idempotency claim, no workflow transition -- unlike the
        two methods above, this is never behind a confirmation (see
        AttachEvidenceCommand's docstring). Returns the created attachment
        ids, in the same order as media_object_keys, so the caller can
        report exactly how many landed."""
        ...

    @abstractmethod
    async def persist_report_site_issue_success(
        self, conn: AsyncConnection, cmd: ReportSiteIssueCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, insert the site_issues row (status
        OPEN) + outbox event, cache SUCCEEDED, and transition the workflow
        to COMPLETED. Always a new row -- unlike Progress Updates, a Site
        Issue report never continues a prior one (see
        ReportSiteIssueCommand's docstring)."""
        ...

    @abstractmethod
    async def persist_close_site_issue_success(
        self, conn: AsyncConnection, cmd: CloseSiteIssueCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, transition the existing site_issues
        row's status (acknowledge/resolve/wont_fix) + outbox event, cache
        SUCCEEDED, and transition the workflow to COMPLETED. Re-verifies the
        row's CURRENT status still allows the requested action inside the
        same claimed transaction immediately before the UPDATE (time can
        pass between the draft being built and the user replying YES) --
        rejects via the same idempotency-keys/workflow_instance bookkeeping
        as persist_rejection, without a second _try_claim call, if it no
        longer does."""
        ...

    @abstractmethod
    async def persist_correct_activity_quantity_success(
        self, conn: AsyncConnection, cmd: CorrectActivityQuantityCommand
    ) -> ExecutionResult:
        """Claim the idempotency key, append a new progress_updates row
        superseding `cmd.progress_update_id` + outbox event, cache
        SUCCEEDED, and transition the workflow to COMPLETED. Re-verifies
        the target row still exists and isn't already superseded by a
        newer correction inside the same claimed transaction immediately
        before the INSERT (ADR-D14) -- same "recheck at confirm time"
        reasoning as persist_close_site_issue_success above. Never edits
        or deletes `cmd.progress_update_id` itself (P1)."""
        ...

    @abstractmethod
    async def persist_rejection(
        self,
        conn: AsyncConnection,
        idempotency_key: str,
        command_type: str,
        reasons: list[str],
    ) -> ExecutionResult:
        """Claim the idempotency key, cache REJECTED (no rows written), and
        transition the workflow to EXECUTION_REJECTED."""
        ...
