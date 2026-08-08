"""Defense-in-depth check that both transfer legs are real, active accounts.

The WhatsApp workflow already resolved from_account_id/to_account_id to real
UUIDs during slot-fill (workflows/transfer/nodes.py), so unlike
resolution.py's account-admin resolver this never resolves a *name* -- it
only re-verifies existence/active-status at confirm time, since an account
could have been deactivated (Slice 6a) in the gap between the draft being
built and the user replying YES.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository

from .transfer_commands import TransferMoneyCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    reasons: list[str]


class TransferAccountResolver(ABC):
    @abstractmethod
    async def resolve(self, conn: AsyncConnection, cmd: TransferMoneyCommand) -> ResolutionResult: ...


class PostgresTransferAccountResolver(TransferAccountResolver):
    async def resolve(self, conn: AsyncConnection, cmd: TransferMoneyCommand) -> ResolutionResult:
        repo = PostgresMoneyAccountRepository(conn)
        organization_id = uuid.UUID(cmd.organization_id)

        from_account = await repo.get_by_id(organization_id, uuid.UUID(cmd.from_account_id))
        to_account = await repo.get_by_id(organization_id, uuid.UUID(cmd.to_account_id))

        reasons: list[str] = []
        if from_account is None or from_account.status != "active":
            reasons.append("the source account is not active")
        if to_account is None or to_account.status != "active":
            reasons.append("the destination account is not active")
        return ResolutionResult(reasons=reasons)
