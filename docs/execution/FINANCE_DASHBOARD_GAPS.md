# Finance Dashboard — Gap Report & Fix List

**Purpose:** the WhatsApp-side Finance Module (Slices 0–8, see [FINANCE_MODULE_PLAN.md](FINANCE_MODULE_PLAN.md)) is complete and deliberately shipped with **no dashboard REST surface** — the original plan explicitly deferred all dashboard work to V2. Independently and concurrently, dashboard pages for finance were built anyway, against a REST layer that only covers part of what the UI now assumes. This document is a precise, file-level list of what's broken and what's missing, for another engineer to fix. Written 2026-07-26 by direct inspection of the current code — every claim below was verified by reading the actual file, not inferred from tickets or plans.

**How to use this doc:** each item has a Problem (what's wrong today, with exact file/line), Impact (what a user experiences), and Fix (what needs to change). Items are ordered by priority. After the fixes land, re-verify each "Impact" claim against the running app before closing this out.

---

## P0 — Actively broken / actively misleading

These either error out or lie to the user about what happened. Fix before anything else.

### 1. Creating a money account from the dashboard is broken (wrong enum values)

**Problem:** `apps/dashboard/src/lib/api.ts:450`, `CreateAccountApiPayload.account_type` is typed as `'bank_account' | 'petty_cash' | 'corporate_card' | 'digital_wallet'`. The backend's `money_accounts.account_type` column has a hard `CHECK` constraint (`backend/migrations/versions/0320_finance_add_money_accounts_and_categories.py:71`): `account_type IN ('cash', 'bank', 'employee_advance', 'other')`. None of the dashboard's four values match any of the backend's four values.

The REST endpoint (`backend/src/mesiri/domains/finance/router.py:153` `create_account`) calls `PostgresMoneyAccountRepository.create()` directly with **no validation at all** — it doesn't go through `application/finance/validation.py`'s `_VALID_ACCOUNT_TYPES` check (that module is only wired into the WhatsApp CQRS handler, never the REST path).

**Impact:** every "Create Account" submission from the dashboard sends an INSERT with an invalid `account_type` value, which violates the DB CHECK constraint at the database layer. This surfaces as an unhandled 500 error — account creation from the dashboard does not work at all today.

**Fix:**
- Change `CreateAccountApiPayload.account_type` (and the create-account dialog's dropdown options) to the real values: `'cash' | 'bank' | 'employee_advance' | 'other'`.
- Add either a Pydantic-level `Literal["cash", "bank", "employee_advance", "other"]` on `CreateAccountRequest` (`backend/src/mesiri/domains/finance/router.py:69`) or route account creation through `application/finance/validation.py`'s existing `_VALID_ACCOUNT_TYPES` check so a bad value comes back as a clean 400, not a raw DB error.
- Decide whether "employee_advance" should even be creatable from this generic dialog — per the WhatsApp-side design (`docs/execution/FINANCE_MODULE_PLAN.md`'s account lifecycle section), `employee_advance` accounts are meant to be auto-created only via petty-cash issuance (Slice 5), never manually. Consider excluding it from the dashboard's create dropdown rather than exposing it there.

### 2. "Void Expense" (single row and bulk) does nothing server-side

**Problem:** `apps/dashboard/src/pages/ExpensesPage.tsx:261-266` (`handleBulkVoid`) and `:615-624` (single-row "Void Expense" menu item) both call only `setExpenses((prev) => prev.filter(...))` — pure local React state removal. No API call of any kind. There is no REST endpoint for voiding/reversing an expense anywhere in the backend (`backend/src/mesiri/domains/expenses/router.py` has only `POST /expenses`, `GET /expenses`, `GET /expenses/{id}`, `GET /expenses/categories`).

**Impact:** clicking "Void Expense" removes the row from the table (looks like success) but the expense is still `workflow_status='confirmed'` in the database, still counted in every balance/report, and reappears on next page refresh/reload. This is worse than not having the feature — it actively misleads whoever clicks it into thinking the expense was voided.

**Fix:** the backend capability already exists and is fully built for the WhatsApp side — see `backend/src/mesiri/application/finance/reverse_{commands,validation,resolution,mapper,handler,dispatcher,repository}.py` and `backend/src/mesiri/infrastructure/postgres/repositories/reverse_execution.py` (Finance Module Slice 7). Add a REST endpoint, e.g. `POST /expenses/{expense_id}/reverse`, that:
- Requires `ADMIN`/`FINANCE` role (matches `application/finance/reverse_validation.py`'s `_REVERSAL_ROLES`).
- Builds a `ReverseTransactionCommand(target_kind="expense", expense_id=..., created_by_role=...)` and calls `ReverseTransactionHandler.handle()` directly (bypassing the WhatsApp draft/confirm flow entirely — REST calls are already an explicit user action, no separate confirmation step needed, same reasoning `POST /expenses` already uses).
- Returns enough to let the UI update the row's `workflow_status` to `voided` instead of removing it from the list (voided expenses should stay visible, greyed out or filtered, not vanish — removing history is misleading in its own way).
- Update `ExpensesPage.tsx` to call this endpoint and only update local state after a successful response; show an error toast on failure instead of silently succeeding either way.

### 3. Transfer Money dialog posts to an endpoint that doesn't exist

**Problem:** `apps/dashboard/src/lib/api.ts:479` `transferMoneyApi()` calls `POST /finance/transfers`. This route does not exist anywhere in `backend/src/mesiri/domains/finance/router.py` (only `GET /accounts`, `GET /accounts/{id}`, `POST /accounts`, `GET /accounts/{id}/transactions`, `GET /petty-cash/vouchers` exist).

**Impact:** submitting the "Transfer Money" dialog on the Accounts page gets a 404 — and it's worse than that: `transfer-money-dialog.tsx:87-90` explicitly catches the failure (`console.warn('Backend endpoint unavailable, falling back to instant UI state update:', err)`), swallows it, and its `finally` block calls `onTransferCompleted?.(...)` **unconditionally** — so the dialog closes and the Accounts page shows updated balances via local state (`handleTransferCompleted` in `AccountsPage.tsx:217`) as if the transfer succeeded, even though nothing happened server-side and the real balances are untouched. This exact same "catch it, log a console.warn, fake success in `finally`" pattern is also present in `record-voucher-dialog.tsx:86-89` and `replenish-float-dialog.tsx:92-95` — all three dialogs deliberately paper over the missing endpoints with fake local success, not an accident.

**Fix:** the backend capability is fully built for WhatsApp — see `backend/src/mesiri/application/finance/transfer_{commands,validation,resolution,mapper,handler,dispatcher,repository}.py` and `.../infrastructure/postgres/repositories/transfer_execution.py` (Slice 3). Add `POST /finance/transfers`:
- Requires `ADMIN`/`FINANCE`/`PROJECT_MANAGER` role (`application/finance/transfer_validation.py`'s `_TRANSFER_ROLES`).
- Builds a `TransferMoneyCommand` from the request body and calls `TransferMoneyHandler.handle()` directly.
- Fix `TransferMoneyDialog`/`AccountsPage.tsx` to only update the UI after a real success response.

### 4. Record Voucher / Replenish Float dialogs post to endpoints that don't exist

**Problem:** `apps/dashboard/src/lib/api.ts:495` (`recordVoucherApi` → `POST /finance/petty-cash/vouchers`) and `:507` (`replenishFloatApi` → `POST /finance/petty-cash/replenish`) — neither route exists. `GET /finance/petty-cash/vouchers` (read) does exist, but there is no corresponding POST for either.

**Impact:** both dialogs 404 on submit, and both swallow the error and fake success exactly like the Transfer dialog does — same "catch, `console.warn('Backend endpoint unavailable...')`, then `finally` block fires the completion callback regardless" pattern, confirmed at `record-voucher-dialog.tsx:86-89` and `replenish-float-dialog.tsx:92-95`. This looks like a deliberate temporary shim (the identical wording across three files suggests one person wrote all three the same way while waiting on backend endpoints), not three independent bugs — worth flagging to whoever wrote it in case they already know and were planning to come back to it.

**Fix:** the backend capability is fully built — Slice 5's petty cash is "a transfer to/from an employee_advance account," so both of these should call the **same transfer endpoint from item #3 above**, not a bespoke petty-cash-specific one (per the deliberate design in `FINANCE_MODULE_PLAN.md`'s Slice 5 section — "no new transaction type"). Once `POST /finance/transfers` exists:
- "Record Voucher" (issuing petty cash / recording a spend from the float) = a transfer from the site's operating account to the cash box's `employee_advance` account, or vice versa depending on the actual UX intent — clarify with whoever owns this page which direction "recording a voucher" means before wiring it.
- "Replenish Float" = a transfer from `source_account_id` to `cash_box_id`, both already present in `ReplenishFloatApiPayload`.
- Remove `RecordVoucherApiPayload`'s `category`/`vendor_name` fields if they don't map to anything a transfer actually needs, or reconsider whether "voucher" should really be an expense (with `account_id` set to the cash box) rather than a transfer — see item #6 below, this needs a product decision, not just a wiring fix.

## P1 — Real capabilities missing from the REST surface entirely

These aren't currently presented as working in the UI (no button calls them), but the corresponding WhatsApp capability exists and dashboard parity is presumably wanted eventually.

### 5. Expenses recorded from the dashboard never carry account/vendor/receipt info

**Problem:** `backend/src/mesiri/domains/expenses/router.py:41` `RecordExpenseRequest` only has `project_id, category_id, amount, occurred_date, site_id, currency, description, occurred_time, source, source_message_id, correlation_id`. It's missing `account_id`, `paid_from_own_pocket`, `vendor_id`/`vendor_text`, and `media_object_key` — **all four of these fields already exist on `RecordExpenseCommand`** (`backend/src/mesiri/application/expenses/commands.py:55-59`) and the router already builds a `RecordExpenseCommand` and calls the same `RecordExpenseHandler.handle()` the WhatsApp path uses (`router.py:78-96`) — the fields are simply never read off the request body and passed through.

**Impact:** every expense recorded via the dashboard is always `payment_status='unpaid'` (no ledger write, no balance movement — Slice 0's entire point is bypassed for dashboard-recorded expenses) and always has no vendor.

**Fix:** this is a small, mechanical fix, not new logic:
- Add `account_id: uuid.UUID | None`, `paid_from_own_pocket: bool = False`, `vendor_id: uuid.UUID | None`, `vendor_text: str | None` to `RecordExpenseRequest`.
- Pass them through to `RecordExpenseCommand(...)` in `record_expense()` (`router.py:78-93`).
- `RecordExpenseHandler` already resolves `vendor_text` via `application/vendors/resolution.py` and handles `account_id`/`paid_from_own_pocket` — no backend logic changes needed at all, just plumbing the fields through the REST request → command mapping.
- On the dashboard side, `RecordExpenseDialog` needs an account picker (reuse whatever `fetchAccountsApi()` already returns) and a vendor text input.
- Receipt/media upload (`media_object_key`) is a separate, larger question — see item #7.

### 6. No account rename/deactivate endpoint

**Problem:** `backend/src/mesiri/domains/finance/router.py` has `POST /accounts` (create) and `GET` routes only. There's no `PATCH`/rename or deactivate route. The WhatsApp side has this fully built (`application/finance/{commands,handlers,resolution}.py`'s `ManageMoneyAccountCommand` with `action="rename"|"deactivate"`, dispatched via `AccountAdminExecutionDispatcher`).

**Impact:** an account created (or existing) can never be renamed or deactivated from the dashboard.

**Fix:** add `PATCH /finance/accounts/{account_id}` accepting `{action: "rename", new_name: str}` or `{action: "deactivate"}`, building a `ManageMoneyAccountCommand` with `target_account_id` already known (skip the by-name resolution the WhatsApp path needs, since the dashboard already has the id) and calling `ManageMoneyAccountHandler.handle()` directly.

### 7. No receipt/attachment endpoint at all

**Problem:** `backend/src/mesiri/domains/expenses/router.py` has no route touching `expense_attachments`. `PostgresExpenseAttachmentRepository.list_for_expense()` (`backend/src/mesiri/infrastructure/postgres/repositories/expenses.py`) already exists and works (used by the WhatsApp path to write attachments — Slice 6b). `ExpensesPage.tsx:77` has a `receipt_url?: string` field and a lightbox UI (`:537-542`) wired to it, but since `ExpenseResponse` (`backend/src/mesiri/domains/expenses/responses.py:10-27`) has no attachment/receipt field at all, `receipt_url` is only ever populated on the mock `INITIAL_EXPENSES` fallback rows — real expenses (even ones with a WhatsApp-captured receipt photo) never show one.

**Impact:** the receipt lightbox UI exists but can never show a real receipt image; it's effectively dead for any live data.

**Fix:**
- Add `GET /expenses/{expense_id}/attachments` returning each attachment's `media_object_key`, `attachment_type`, `created_at` — likely needs to resolve `media_object_key` to a real signed/servable URL (check whatever object-storage abstraction the WhatsApp media pipeline uses, `mesiri_contracts.common.storage.ObjectStoragePort`, for how to generate a fetchable URL from an object key — this may need a new signed-URL helper if one doesn't already exist for read access).
- Wire `ExpensesPage.tsx`'s lightbox to fetch this on demand (e.g., when a row is expanded) instead of reading a nonexistent `receipt_url` field.

### 8. Missing-receipt nudge not exposed

**Problem:** `PostgresExpenseRepository.list_confirmed(without_attachment=True)` (Slice 6c) exists and works on the WhatsApp side, but `GET /expenses` (`backend/src/mesiri/domains/expenses/router.py`) has no query parameter to pass it through.

**Impact:** no way to see "expenses missing a receipt" as a dashboard filter/view, even though the underlying query is one parameter away from working.

**Fix:** add a `missing_receipts: bool = False` query param to `GET /expenses`, pass through to `repo.list_confirmed(..., without_attachment=missing_receipts)`. Trivial once item #7's attachment plumbing is in place (a "missing receipt" filter without any way to view/add a receipt is a smaller win).

### 9. Duplicate-detection has no dashboard equivalent

Not a bug — this is purely internal to the WhatsApp LangGraph node (`workflows/expense_capture/nodes.py::check_duplicate`, Slice 8) and was never intended to be REST-exposed. No action needed unless a future decision is made to add the same "looks like a duplicate" warning to the dashboard's Record Expense dialog (would need a new endpoint wrapping `runtime/duplicate_expense_query.py`'s logic, or a backend-side equivalent — currently that service lives in `apps/whatsapp-assistant`, not `backend`, so it would need to move or be duplicated).

---

## Contract mismatches worth fixing regardless of the above

- **Petty cash "voucher" shape** (`apps/dashboard/src/lib/api.ts` around `RecordVoucherApiPayload`/`fetchVouchersApi`): the dashboard models a `voucher_number`/`category`/`vendor_name`/`cash_box_name` entity. The backend has no such entity — `GET /finance/petty-cash/vouchers` returns raw `MoneyTransactionResponse` rows (a ledger transaction: `amount`, `description`, `from_account_id`, `to_account_id`, `source_type`). `PettyCashPage.tsx` currently fabricates `category`/`vendor_name`/`cash_box_name` from whatever text happens to land in `description`. Decide: either build a real petty-cash-specific read model on the backend that joins account names in, or simplify the dashboard UI to show what a `money_transactions` row actually is (amount, direction, description, date) rather than pretending it's a structured voucher.
- **Cash-box account_type filter** (`PettyCashPage.tsx`, `pettyBoxes = data.filter(a => a.account_type === 'petty_cash' || a.account_type === 'cash')`): `'petty_cash'` never matches any real account (backend never uses that string — see item #1), so it's dead code. `'cash'` does match, but that's the *default op-cash account* type, not specifically petty cash — a real `employee_advance` account (the actual petty-cash type per the WhatsApp design) is excluded by this filter, so genuine petty-cash accounts created via WhatsApp (Slice 5's auto-created "Alan — Petty Cash") never show up on this page at all, while the general "Site Cash" operating account incorrectly does. Fix the filter to `account_type === 'employee_advance'` once item #1's enum fix lands.
- **`custodian_name`**: dashboard expects a human-readable name; backend only returns `owner_user_id` (a UUID, `MoneyAccountResponse.owner_user_id`). `AccountsPage.tsx` currently fakes a name by slicing the UUID. Fix: either join `users.full_name` into the account response backend-side, or fetch it separately — don't fabricate a name from an id.

---

## Linear housekeeping

**STA-84** ("Finance Accounts page + Expenses") is stale — its description still says the page "doesn't exist at all right now," but `ExpensesPage.tsx` is real and reads live data today. Update it to reflect: base list/filter/totals view shipped; remaining scope is the items above (receipt attachments particularly, since that was explicitly called out in the original ticket).

---

## Suggested order of work

1. Fix #1 (account_type enum) — quick, isolated, and today it hard-breaks a whole feature.
2. Fix #2 and #3 (Void, Transfer) — these are the "silently does nothing/404s" bugs; either wire them for real or disable the buttons so they stop misleading users, whichever ships faster.
3. Fix #4 (petty cash dialogs) once #3's transfer endpoint exists, since #4 depends on it.
4. Fix #5 (expense account/vendor fields) — small, mechanical, unlocks real money-movement from the dashboard.
5. Fix #6 (rename/deactivate) and #7 (attachments) — larger scope, do when there's time.
6. Fix #8 once #7 lands.
7. Update Linear STA-84.

Every fix above reuses backend logic that's already built and tested for the WhatsApp side (`application/finance/*`, `application/expenses/*`) — none of these need new domain logic, only new/extended REST routes and request/response schemas to expose what already exists.
