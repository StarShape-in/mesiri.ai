"""Resolve a ManageMoneyAccountCommand's target account by name.

Defense-in-depth resolver, mirrors application/expenses/resolution.py. The
WhatsApp deterministic parser only ever supplies a name string (never an
id), so `create` checks for a name collision and `rename`/`deactivate` look
up the existing account by name — both need a DB round trip, hence an
injectable port (Handler unit tests supply a fake instead of hitting
Postgres, see application/finance/fakes.py).

Unlike expense category resolution, there is no AI-guessed-text fallback
here: these are deterministic ADMIN/FINANCE commands, so an unresolved name
is always a hard rejection, never a silent default.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository

from .commands import ManageMoneyAccountCommand

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True, slots=True)
class ResolutionResult:
    target_account_id: uuid.UUID | None
    reasons: list[str]


class AccountLookupResolver(ABC):
    @abstractmethod
    async def resolve(
        self, conn: AsyncConnection, cmd: ManageMoneyAccountCommand
    ) -> ResolutionResult: ...


class PostgresAccountLookupResolver(AccountLookupResolver):
    async def resolve(
        self, conn: AsyncConnection, cmd: ManageMoneyAccountCommand
    ) -> ResolutionResult:
        repo = PostgresMoneyAccountRepository(conn)
        organization_id = uuid.UUID(cmd.organization_id)

        if cmd.action == "create":
            existing = await repo.find_by_name_exact_active(organization_id, cmd.name or "")
            if existing is not None:
                return ResolutionResult(
                    target_account_id=None,
                    reasons=[f"an account named '{cmd.name}' already exists"],
                )
            return ResolutionResult(target_account_id=None, reasons=[])

        # rename / deactivate both need to find the existing target account.
        account = await repo.find_by_name_exact_active(organization_id, cmd.target_name or "")
        if account is None:
            return ResolutionResult(
                target_account_id=None,
                reasons=[f"no active account named '{cmd.target_name}'"],
            )
        return ResolutionResult(target_account_id=account.id, reasons=[])
