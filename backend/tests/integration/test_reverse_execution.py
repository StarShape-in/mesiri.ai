"""Reverse execution — integration tests against a real Postgres.

Covers the full Handler -> PostgresReverseExecutionRepository path for both
target kinds (Finance Module Slice 7, Linear STA-149):

- Expense: reversing an expense payment leaves the *original*
  money_transactions row untouched and posts a new opposite-direction row;
  get_balance() nets back to the pre-expense value; the expense itself is
  voided; reversing an already-voided expense is rejected.
- Transfer: reversing a transfer's ledger row nets both accounts' balances
  back to their pre-transfer values; reversing an already-reversed transfer
  is rejected.

Mirrors test_transfer_execution.py / test_expense_execution_money_wiring.py.
"""

from __future__ import annotations

import datetime
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.application.expenses.commands import RecordExpenseCommand
from mesiri.application.expenses.handlers import RecordExpenseHandler
from mesiri.application.finance.reverse_commands import ReverseTransactionCommand
from mesiri.application.finance.reverse_handler import ReverseTransactionHandler
from mesiri.application.finance.reverse_resolution import PostgresReverseTargetResolver
from mesiri.application.finance.transfer_commands import TransferMoneyCommand
from mesiri.application.finance.transfer_handler import TransferMoneyHandler
from mesiri.application.finance.transfer_resolution import PostgresTransferAccountResolver
from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.repositories.expense_execution import (
    PostgresExpenseExecutionRepository,
)
from mesiri.infrastructure.postgres.repositories.finance import PostgresMoneyAccountRepository
from mesiri.infrastructure.postgres.repositories.reverse_execution import (
    PostgresReverseExecutionRepository,
)
from mesiri.infrastructure.postgres.repositories.transfer_execution import (
    PostgresTransferExecutionRepository,
)
from mesiri_contracts.application.results.execution_result import ExecutionStatus

pytestmark = pytest.mark.integration


@pytest.fixture
async def engine():
    settings = Settings()
    eng = create_async_engine(settings.postgres.dsn())
    yield eng
    await eng.dispose()


@pytest.fixture
async def scenario(engine: AsyncEngine):
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    category_id = uuid.uuid4()
    account_a = uuid.uuid4()
    account_b = uuid.uuid4()
    async with engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status, "
                "created_at, updated_at) VALUES (:id, 'Reverse Test Org', 'local', 'default', "
                "'active', now(), now())"
            ),
            {"id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name, "
                "role, status, access_policy, created_at, updated_at) "
                "VALUES (:id, :org_id, :email, 'x', 'Test', 'admin', 'active', "
                "CAST(:policy AS jsonb), now(), now())"
            ),
            {
                "id": user_id,
                "org_id": org_id,
                "email": f"{user_id}@example.com",
                "policy": '{"mode": "all_projects", "projects": []}',
            },
        )
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at) "
                "VALUES (:id, :org_id, 'Reverse Test Project', now(), now())"
            ),
            {"id": project_id, "org_id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO expense_categories (id, organization_id, name, status, created_by) "
                "VALUES (:id, :org_id, 'fuel', 'active', :user_id)"
            ),
            {"id": category_id, "org_id": org_id, "user_id": user_id},
        )
        for acc_id, name in ((account_a, "Site Cash"), (account_b, "Company Bank")):
            await conn.execute(
                sa.text(
                    "INSERT INTO money_accounts (id, organization_id, name, account_type, "
                    "currency, opening_balance, opening_balance_date, status, created_by) "
                    "VALUES (:id, :org_id, :name, 'cash', 'INR', 5000.00, current_date, "
                    "'active', :user_id)"
                ),
                {"id": acc_id, "org_id": org_id, "name": name, "user_id": user_id},
            )
    yield {
        "org_id": org_id,
        "user_id": user_id,
        "project_id": project_id,
        "category_id": category_id,
        "account_a": account_a,
        "account_b": account_b,
    }
    async with engine.begin() as conn:
        await conn.execute(sa.text("DELETE FROM money_transactions WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_payments WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expenses WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM money_accounts WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM expense_categories WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM users WHERE organization_id = :id"), {"id": org_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})


def _reverse_handler() -> ReverseTransactionHandler:
    return ReverseTransactionHandler(
        PostgresReverseExecutionRepository(), resolver=PostgresReverseTargetResolver()
    )


async def test_reversing_an_expense_restores_the_balance_and_leaves_the_original_row_untouched(
    engine: AsyncEngine, scenario: dict
):
    expense_handler = RecordExpenseHandler(PostgresExpenseExecutionRepository())
    expense_cmd = RecordExpenseCommand(
        idempotency_key=f"exp-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        project_id=str(scenario["project_id"]),
        category_id=str(scenario["category_id"]),
        account_id=str(scenario["account_a"]),
        amount=Decimal("1200.00"),
        occurred_date=datetime.date.today(),
        created_by=str(scenario["user_id"]),
    )
    async with engine.begin() as conn:
        expense_result = await expense_handler.handle(conn, expense_cmd)
    assert expense_result.status == ExecutionStatus.SUCCEEDED
    expense_id = uuid.UUID(expense_result.material_row_id)

    async with engine.connect() as conn:
        accounts = PostgresMoneyAccountRepository(conn)
        balance_after_expense = await accounts.get_balance(scenario["org_id"], scenario["account_a"])
        original_ledger_row = (
            await conn.execute(
                sa.text(
                    "SELECT id, amount, from_account_id, to_account_id FROM money_transactions "
                    "WHERE source_type = 'expense_payment' AND source_id IN "
                    "(SELECT id FROM expense_payments WHERE expense_id = :id)"
                ),
                {"id": expense_id},
            )
        ).mappings().one()
    assert balance_after_expense == Decimal("5000.00") - Decimal("1200.00")

    reverse_handler = _reverse_handler()
    reverse_cmd = ReverseTransactionCommand(
        idempotency_key=f"rev-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        created_by_role="ADMIN",
        target_kind="expense",
        expense_id=str(expense_id),
    )
    async with engine.begin() as conn:
        reverse_result = await reverse_handler.handle(conn, reverse_cmd)
    assert reverse_result.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        accounts = PostgresMoneyAccountRepository(conn)
        balance_after_reversal = await accounts.get_balance(scenario["org_id"], scenario["account_a"])
        unchanged_row = (
            await conn.execute(
                sa.text("SELECT amount, from_account_id, to_account_id FROM money_transactions WHERE id = :id"),
                {"id": original_ledger_row["id"]},
            )
        ).mappings().one()
        reversal_row = (
            await conn.execute(
                sa.text(
                    "SELECT amount, from_account_id, to_account_id FROM money_transactions "
                    "WHERE transaction_type = 'reversal' AND organization_id = :org_id"
                ),
                {"org_id": scenario["org_id"]},
            )
        ).mappings().one()
        expense_status = (
            await conn.execute(
                sa.text("SELECT workflow_status FROM expenses WHERE id = :id"), {"id": expense_id}
            )
        ).scalar_one()

    # Original row is byte-for-byte untouched -- the ledger is insert-only.
    assert unchanged_row["amount"] == original_ledger_row["amount"]
    assert unchanged_row["from_account_id"] == original_ledger_row["from_account_id"]
    assert unchanged_row["to_account_id"] == original_ledger_row["to_account_id"]
    # The reversal row swaps the direction of the original.
    assert reversal_row["from_account_id"] == original_ledger_row["to_account_id"]
    assert reversal_row["to_account_id"] == original_ledger_row["from_account_id"]
    assert reversal_row["amount"] == original_ledger_row["amount"]
    # Balance nets back exactly to the pre-expense value.
    assert balance_after_reversal == Decimal("5000.00")
    assert expense_status == "voided"


async def test_reversing_an_already_voided_expense_is_rejected(engine: AsyncEngine, scenario: dict):
    expense_handler = RecordExpenseHandler(PostgresExpenseExecutionRepository())
    expense_cmd = RecordExpenseCommand(
        idempotency_key=f"exp-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        project_id=str(scenario["project_id"]),
        category_id=str(scenario["category_id"]),
        account_id=str(scenario["account_a"]),
        amount=Decimal("500.00"),
        occurred_date=datetime.date.today(),
        created_by=str(scenario["user_id"]),
    )
    async with engine.begin() as conn:
        expense_result = await expense_handler.handle(conn, expense_cmd)
    expense_id = uuid.UUID(expense_result.material_row_id)

    reverse_handler = _reverse_handler()

    def _reverse_cmd() -> ReverseTransactionCommand:
        return ReverseTransactionCommand(
            idempotency_key=f"rev-{uuid.uuid4()}",
            organization_id=str(scenario["org_id"]),
            created_by=str(scenario["user_id"]),
            created_by_role="ADMIN",
            target_kind="expense",
            expense_id=str(expense_id),
        )

    async with engine.begin() as conn:
        first = await reverse_handler.handle(conn, _reverse_cmd())
    assert first.status == ExecutionStatus.SUCCEEDED

    async with engine.begin() as conn:
        second = await reverse_handler.handle(conn, _reverse_cmd())
    assert second.status == ExecutionStatus.REJECTED
    assert "already voided" in second.rejection_reasons[0]


async def test_reversing_a_transfer_restores_both_balances(engine: AsyncEngine, scenario: dict):
    transfer_handler = TransferMoneyHandler(
        PostgresTransferExecutionRepository(), resolver=PostgresTransferAccountResolver()
    )
    transfer_cmd = TransferMoneyCommand(
        idempotency_key=f"xfer-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        created_by_role="ADMIN",
        from_account_id=str(scenario["account_a"]),
        to_account_id=str(scenario["account_b"]),
        amount=Decimal("1500.00"),
        occurred_date=datetime.date.today(),
    )
    async with engine.begin() as conn:
        transfer_result = await transfer_handler.handle(conn, transfer_cmd)
    assert transfer_result.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        transaction_id = (
            await conn.execute(
                sa.text(
                    "SELECT id FROM money_transactions WHERE transaction_type = 'transfer' "
                    "AND organization_id = :org_id"
                ),
                {"org_id": scenario["org_id"]},
            )
        ).scalar_one()

    reverse_handler = _reverse_handler()
    reverse_cmd = ReverseTransactionCommand(
        idempotency_key=f"rev-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        created_by_role="FINANCE",
        target_kind="transfer",
        money_transaction_id=str(transaction_id),
    )
    async with engine.begin() as conn:
        reverse_result = await reverse_handler.handle(conn, reverse_cmd)
    assert reverse_result.status == ExecutionStatus.SUCCEEDED

    async with engine.connect() as conn:
        accounts = PostgresMoneyAccountRepository(conn)
        from_balance = await accounts.get_balance(scenario["org_id"], scenario["account_a"])
        to_balance = await accounts.get_balance(scenario["org_id"], scenario["account_b"])
    assert from_balance == Decimal("5000.00")
    assert to_balance == Decimal("5000.00")

    # Reversing the same transfer again is rejected.
    async with engine.begin() as conn:
        second = await reverse_handler.handle(
            conn,
            ReverseTransactionCommand(
                idempotency_key=f"rev-{uuid.uuid4()}",
                organization_id=str(scenario["org_id"]),
                created_by=str(scenario["user_id"]),
                created_by_role="FINANCE",
                target_kind="transfer",
                money_transaction_id=str(transaction_id),
            ),
        )
    assert second.status == ExecutionStatus.REJECTED
    assert "already been reversed" in second.rejection_reasons[0]


async def test_disallowed_role_cannot_reverse_an_expense(engine: AsyncEngine, scenario: dict):
    expense_handler = RecordExpenseHandler(PostgresExpenseExecutionRepository())
    expense_cmd = RecordExpenseCommand(
        idempotency_key=f"exp-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        project_id=str(scenario["project_id"]),
        category_id=str(scenario["category_id"]),
        account_id=str(scenario["account_a"]),
        amount=Decimal("300.00"),
        occurred_date=datetime.date.today(),
        created_by=str(scenario["user_id"]),
    )
    async with engine.begin() as conn:
        expense_result = await expense_handler.handle(conn, expense_cmd)
    expense_id = uuid.UUID(expense_result.material_row_id)

    reverse_handler = _reverse_handler()
    reverse_cmd = ReverseTransactionCommand(
        idempotency_key=f"rev-{uuid.uuid4()}",
        organization_id=str(scenario["org_id"]),
        created_by=str(scenario["user_id"]),
        created_by_role="PROJECT_MANAGER",
        target_kind="expense",
        expense_id=str(expense_id),
    )
    async with engine.begin() as conn:
        result = await reverse_handler.handle(conn, reverse_cmd)
    assert result.status == ExecutionStatus.REJECTED
    assert "only an admin or finance user can reverse a transaction" in result.rejection_reasons
