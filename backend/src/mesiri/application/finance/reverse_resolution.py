"""Defense-in-depth check that the reversal target is still reversible.

runtime/inbound_journey.py's seeding step already found "the most recent
expense/transfer" (or, for `target_kind == "activity"`, the Activity this
conversation just touched) at draft-build time (see
workflows/reverse/nodes.py), so this never resolves a name or a fuzzy
reference -- it only re-verifies the target still exists and hasn't
already been reversed/voided/frozen at confirm time, since time can pass
between the draft being built and the user replying YES (mirrors
application/finance/transfer_resolution.py's re-verify-at-confirm-time
reasoning).

The activity branch additionally re-checks that this activity still
belongs to the same reporter (ADR-D15: "the reporter just created", not
anyone in the org) and is not already part of an APPROVED/PUBLISHED daily
report (P7) -- both real possibilities in the gap between draft and
confirm, and both must reject here rather than let persist_success's own
void_activity discover them after the fact (that method also checks, but
this Handler's shape expects rejections to surface from resolve(), not
from persist_success).
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.expenses import PostgresExpenseRepository
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyTransactionRepository

from .reverse_commands import ReverseTransactionCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    reasons: list[str]


class ReverseTargetResolver(ABC):
    @abstractmethod
    async def resolve(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand
    ) -> ResolutionResult: ...


class PostgresReverseTargetResolver(ReverseTargetResolver):
    async def resolve(
        self, conn: AsyncConnection, cmd: ReverseTransactionCommand
    ) -> ResolutionResult:
        organization_id = uuid.UUID(cmd.organization_id)

        if cmd.target_kind == "expense":
            assert cmd.expense_id is not None
            expenses = PostgresExpenseRepository(conn)
            expense = await expenses.get_by_id(organization_id, uuid.UUID(cmd.expense_id))
            if expense is None:
                return ResolutionResult(reasons=["that expense no longer exists"])
            if expense.workflow_status != "confirmed":
                return ResolutionResult(
                    reasons=[f"that expense is already {expense.workflow_status}"]
                )
            return ResolutionResult(reasons=[])

        if cmd.target_kind == "activity":
            assert cmd.activity_id is not None
            from mesiri.infrastructure.postgres.repositories.dpr import PostgresDprRepository
            from mesiri.infrastructure.postgres.repositories.progress import (
                PostgresProgressReadRepository,
            )

            activity_id = uuid.UUID(cmd.activity_id)
            progress = PostgresProgressReadRepository(conn)
            activity = await progress.get_activity(organization_id, activity_id)
            if activity is None:
                return ResolutionResult(reasons=["that activity no longer exists"])
            if str(activity.get("reported_by_user_id") or "") != str(cmd.created_by):
                return ResolutionResult(
                    reasons=["you can only undo an activity you reported yourself"]
                )
            dpr = PostgresDprRepository(conn)
            report = await dpr.find_site_report(
                organization_id=organization_id,
                project_id=activity["project_id"],
                site_id=activity["site_id"],
                report_date=activity["activity_date"],
            )
            if report is not None and report["status"] in ("APPROVED", "PUBLISHED"):
                return ResolutionResult(
                    reasons=[
                        "this activity is already part of an approved daily report "
                        "and cannot be undone"
                    ]
                )
            return ResolutionResult(reasons=[])

        assert cmd.money_transaction_id is not None
        transactions = PostgresMoneyTransactionRepository(conn)
        transaction_id = uuid.UUID(cmd.money_transaction_id)
        transaction = await transactions.get_by_id(organization_id, transaction_id)
        if transaction is None:
            return ResolutionResult(reasons=["that transfer no longer exists"])
        if transaction.transaction_type != "transfer":
            return ResolutionResult(reasons=["that transaction is not a transfer"])
        if await transactions.is_reversed(organization_id, transaction_id):
            return ResolutionResult(reasons=["that transfer has already been reversed"])
        return ResolutionResult(reasons=[])
