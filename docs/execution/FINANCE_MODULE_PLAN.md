# Finance Module — Domain Design & LangGraph Workflow Roadmap

**Status:** In progress. Slice 0 (money wiring) and Slice 1 (LangGraph slot-filling spine) done as of 2026-07-25. Slices 2–8 remain (V1); Slices 9–12 + dashboard are V2, explicitly deferred.
**Author:** Written and approved 2026-07-25 (Linear epics [STA-140](https://linear.app/starshape-pvt/issue/STA-140) / [STA-141](https://linear.app/starshape-pvt/issue/STA-141), sub-issues STA-142..154). Re-read before extending — the design below reflects what actually shipped in Slices 0–1; verify against the live code before assuming later slices are still exactly as described.
**Scope: WhatsApp assistant + the backend it writes through. No web dashboard work in this plan** — the dashboard Finance section is deferred (needs REST endpoints this plan deliberately skips; tracked separately as [STA-84](https://linear.app/starshape-pvt/issue/STA-84)).
**Scope exclusion:** Purchases/procurement are out of scope — expense must never touch stock. Multi-currency is deferred (schema carries `currency`, no conversion).
**Ship rule:** one slice at a time, each independently shippable and verifiable end-to-end.

---

## Context

The finance conversation proposed separating Accounts / Transactions / Expenses / Purchases into distinct domains and listed ~17 workflows. **That separation already existed in this codebase** (migrations `0320`–`0340`, `backend/src/mesiri/domains/{finance,expenses}/`). The real work was:

1. Correcting three places the proposed model would have duplicated existing design (petty cash and opening balance are not new transaction types; "expense conversation" is a read, not a new store).
2. Closing the hole that made the module non-functional: confirming an expense never moved money.
3. Giving LangGraph the ability to ask a clarifying question mid-workflow ("which account?"), so every later capability is a small, uniform slice on top of one spine.

---

## Roles & permissions (V1, WhatsApp)

Real drift, not designed here: `backend/src/mesiri/infrastructure/postgres/models/user.py`'s `UserRole` enum (`admin|manager|user|site_manager|worker`) differs from the dashboard's `apps/dashboard/src/lib/permissions.ts` role set (`ADMIN|PROJECT_MANAGER|SITE_ENGINEER|FINANCE`), and `AuthorizationContext.role` is a bare `str`. Finance code checks role by the dashboard's string values (matching `MaterialsPage.tsx`'s existing `me.role !== 'FINANCE'` pattern) since that's what's actually issued in JWTs today. The enum drift itself is a separate cleanup, not fixed here.

| Action | Who |
|---|---|
| Record an expense against an account they have access to | Any authenticated WhatsApp user |
| Choose "my own pocket" (reimbursable) | Any authenticated user |
| Query balances/expenses scoped to their own project/site | Any authenticated user, existing project/site scope |
| Query balances org-wide | `ADMIN`, `FINANCE` only |
| Transfer money, issue/return petty cash | `ADMIN`, `FINANCE`, `PROJECT_MANAGER` within project scope — never `SITE_ENGINEER` |
| Reverse/void a transaction | `ADMIN`, `FINANCE` only |
| Create/deactivate a money account | `ADMIN`, `FINANCE` only |

## UX principles (binding on every slice)

1. Never ask what can be inferred (auto-fill on 0/1 real candidates; own-pocket is always a second option).
2. Every write is confirmed before it commits.
3. Numbered-list replies are the fast path; free text/voice is always accepted as a fallback.
4. Every successful write gets the existing receipt-card treatment (`channel/receipt/`).
5. Rejections/failures are worded as recoverable.

## Finance account lifecycle

- **Creation**: lazy default-account bootstrap (Slice 0, one `cash` account per org on first use) or explicit `ADMIN`/`FINANCE` creation via WhatsApp (Slice 6).
- **Employee-advance accounts** (petty cash, Slice 5) are created implicitly on first issuance to a recipient without one.
- **Deactivation, never deletion** — `status → 'inactive'`, historical `money_transactions` rows stay queryable and keep counting in `get_balance()`.
- No account merge/rename-that-changes-identity in V1.
- Balance is always derived, never stored.

## V1 / V2 boundary

**V1 (Slices 0–8)**: record an expense against an account or own pocket, transfer money (incl. petty cash), query balances/spend, attach a receipt, reverse a mistake.

**V2 (Slices 9–12 + dashboard, [STA-141](https://linear.app/starshape-pvt/issue/STA-141)), explicitly deferred:** budgets, approvals + expense limits (needs a second actor in the confirmation loop — the largest slice by far), reports/exports/end-of-day summary, AI analytics/narrative, dashboard Finance UI.

---

## Slice 0 — Wire confirmed expenses to actual money movement ([STA-142](https://linear.app/starshape-pvt/issue/STA-142)) — DONE

`RecordExpenseCommand` gained `account_id`/`paid_from_own_pocket` (mutually exclusive, enforced in `validation.py`). `PostgresExpenseExecutionRepository.persist_success()` now composes the **already-existing** `PostgresExpensePaymentRepository.record_payment()` (which itself writes `expense_payments` + `money_transactions` + recomputes `payment_status`) instead of duplicating that logic. Three outcomes: account named → `paid` + payment + ledger row; own pocket → `reimbursable`, no ledger row; neither → `unpaid` (unchanged prior behavior).

Migration `0367_finance_money_transaction_idempotency.py` (renumbered from a stale `0370` after a rebase) adds `UNIQUE(source_type, source_id, transaction_type)` on `money_transactions`, forward-looking defense for Slices 3/5/7's future writers (current writers already sit behind an outer idempotency claim or a payment-status transition).

`apps/whatsapp-assistant/src/runtime/money_account_query.py` (new): read-service + lazy default-account bootstrap (`get_or_create`-style, mirrors `PostgresExpenseCategoryRepository.get_or_create_default`), same shape as `runtime/expense_category_query.py`.

Considered and **dropped**: a proposed `get_balance()` tenant-filter fix — on inspection, `get_by_id()` already validates the account belongs to the org before the balance sums run, so there was no exploitable gap.

## Slice 1 — LangGraph mid-workflow slot-filling ([STA-143](https://linear.app/starshape-pvt/issue/STA-143)) — DONE

The architectural spine every later slice reuses.

- `WorkflowStateV2` (shared contract) and `WorkflowGraphState` (LangGraph working state) both gained `awaiting_slot: str | None`.
- `workflows/slots.py` (new, domain-agnostic, pure): `resolve_single_choice_slot()` (0 candidates → unset, 1 → auto-fill, N → ask numbered) and `match_slot_answer()` (numbered or free-text/substring match).
- `expense_capture/nodes.py` gained `resolve_account`: seeds real accounts from `collected_fields['account_candidates']`, always appends an "own pocket" sentinel choice (so the slot always has ≥2 options whenever any account exists — a single real account still asks), and consumes `_slot_answer_text` on resume to match against the same candidate list. `build_draft` excludes the `account_candidates` plumbing key from what the user sees.
- `expense_capture/graph.py`: `START → resolve_account → (ask_slot → END | build_draft → request_confirmation → END)` via `add_conditional_edges`.
- `WorkflowRuntime.start()`: when a node sets `awaiting_slot`, persists `WorkflowPhase.COLLECTING_FIELDS` (pre-existing, previously-unused enum member) instead of `AWAITING_CONFIRMATION`, returns a new `WorkflowRunStatus.AWAITING_INPUT`. The single-active pre-check now also blocks on an existing `COLLECTING_FIELDS` instance.
- `WorkflowRuntime.provide_input()` (new): generalizes `correct()`'s merge-fields → re-invoke → transition mechanic. Matching the answer happens **inside the node**, not in the runtime (architecture rule: runtime never does domain-rule matching) — the runtime only merges the raw answer text into `collected_fields['_slot_answer_text']`, re-invokes, and persists whatever the graph decided (still ambiguous → `COLLECTING_FIELDS` again with a "didn't catch that" prompt; resolved → `AWAITING_CONFIRMATION` with the built draft).
- `workflows/ports.py` gained `get_awaiting_input()`, implemented in both `PostgresWorkflowInstanceRepository` and `FakeWorkflowInstanceRepository`.
- **Real bug found and fixed in the same file**: `backend/postgres/workflow_instance.py`'s `transition_on_connection()` was setting the `status` column to the literal phase string for *every* transition, not just the five genuinely terminal ones. Since `get_awaiting_confirmation()`/`get_awaiting_input()` both filter on `status='active'`, this meant `correct()` (pre-existing) — and would have meant `provide_input()` (new) — silently broke the *next* confirm/slot-answer lookup after any correction or slot resolution. Fixed to only mark status non-active for the five documented terminal phases (`confirmed→completed`, `rejected`, `cancelled`, `completed`, `execution_rejected`); everything else keeps `status='active'`.
- `interactions/handler.py` gained `handle_slot_answer()` (text/interactive only, same reasoning as `handle_whoami_trigger` re: voice), wired into `runtime/dependencies.py` right after the confirmation fast path, same priority.
- `runtime/inbound_journey.py` gained one small seeding function, `_seed_account_candidates()` (mirrors `_inject_inventory_context`'s existing pattern) — feeds real accounts into `event.fields['account_candidates']` before `workflow_runtime.start()`, only for `WorkflowKey.EXPENSE_SUBMIT`. No new branches added to the file's main control flow.

Tests: `test_workflow_slots.py`, `test_expense_capture_nodes.py` (resolve_account), `test_workflow_runtime.py` (awaiting_input persistence, blocking, provide_input resolve/no-match/wrong-phase), `test_interaction_handler.py` (handle_slot_answer), `test_expense_capture_graph.py` (real LangGraph, no DB — zero-account auto-fill, one-account-still-asks, full ask→answer→confirm round trip).

## Slices 2–8 (V1, not yet started)

See Linear [STA-144](https://linear.app/starshape-pvt/issue/STA-144)–[STA-150](https://linear.app/starshape-pvt/issue/STA-150) for full detail: expense/balance queries, transfers, vendor/payee (fixes a real schema drift — `expenses.vendor_id` has no backing migration), petty cash (a transfer convenience shape, no new transaction type), receipt/attachment capture + account admin, edit/cancel/reverse, duplicate detection.

## Slices 9–12 + dashboard (V2, deferred)

See [STA-151](https://linear.app/starshape-pvt/issue/STA-151)–[STA-154](https://linear.app/starshape-pvt/issue/STA-154) and [STA-84](https://linear.app/starshape-pvt/issue/STA-84).

---

## Critical files

**Slice 0:** `backend/src/mesiri/application/expenses/{commands,mapper,validation}.py` · `.../infrastructure/postgres/repositories/expense_execution.py` · `backend/migrations/versions/0367_finance_money_transaction_idempotency.py` · `apps/whatsapp-assistant/src/runtime/money_account_query.py`.

**Slice 1:** `shared/contracts/src/mesiri_contracts/assistant/v2/workflow_state.py` · `apps/whatsapp-assistant/src/workflows/{state,slots,ports,fakes,runtime}.py` · `.../workflows/expense_capture/{nodes,graph}.py` · `.../backend/postgres/workflow_instance.py` · `.../interactions/{handler,response_handler}.py` · `.../runtime/{inbound_journey,dependencies}.py`.

## Verification

Every slice: full non-integration suites in `backend/`, `apps/whatsapp-assistant/`, and `shared/contracts/` (a contract field changed in Slice 1) must pass, plus `ruff check`. Slice-specific test names are listed above per slice.
