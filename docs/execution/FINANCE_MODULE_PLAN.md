# Finance Module — Domain Design & LangGraph Workflow Roadmap

**Status:** In progress. Slice 0 (money wiring), Slice 1 (LangGraph slot-filling spine), Slice 2 (expense & balance queries), Slice 3 (transfers), Slice 4 (vendor/payee), Slice 5 (petty cash), the account-admin portion of Slice 6 (create/rename/deactivate accounts), and the receipt-capture portion of Slice 6 (image-purpose picker + expense attachment write, done out of order — see notes below) are done as of 2026-07-25. Only Slice 6's missing-receipt-nudge portion remains (V1); Slices 9–12 + dashboard are V2, explicitly deferred.

**Out-of-order note:** Slice 6 as originally ticketed ([STA-148](https://linear.app/starshape-pvt/issue/STA-148)) bundled two unrelated things — account admin, and receipt/attachment capture + missing-receipt nudges. Only account admin was built now, jumping ahead of Slices 2–5, because it was blocking realistic multi-account testing (every org only ever had the one auto-bootstrapped "Site Cash" account otherwise). STA-148 was split: account admin is done; the receipt/attachment portion is tracked as a new follow-up ticket, not yet started.
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

## Slice 6 (account-admin portion only) — DONE, done out of order

Built ahead of Slices 2–5 because every org otherwise only ever had the single auto-bootstrapped "Site Cash" account (Slice 0), making multi-account scenarios (the interesting "which of three accounts?" slot-fill case) untestable. The receipt/attachment-capture + missing-receipt-nudge half of the original Slice 6 ticket is **not** built — split into its own follow-up, unstarted.

**Deliberately deterministic, not AI-routed:** "create account X" / "rename X to Y" / "deactivate X" are recognized by a regex parser (`runtime/account_admin_parser.py`), not the extraction/canonicalization pipeline — these are ADMIN/FINANCE-only, low-volume commands where a predictable syntax beats an LLM guess for something that mutates the chart of accounts. A new `CanonicalEventType.ACCOUNT_ADMIN_REQUESTED` and `WorkflowKey.ACCOUNT_ADMIN` exist (routing table entry included) purely so `PlannerDecisionV2.reason`/telemetry stay accurate — `runtime/account_admin_journey.py` constructs the `CanonicalEventV2`/`PlannerDecisionV2` directly and calls `WorkflowRuntime.start()`, bypassing `planner.decide()` and the understanding pipeline entirely (there is nothing for the AI to extract; the regex parser already has every field).

**Every write is still confirmed before it commits** (architecture rule #4) — `workflows/account_admin/` is a plain 2-node graph (`build_draft → request_confirmation`, no slot-filling needed since the parser front-loads all fields), producing a `DraftActionType.MANAGE_MONEY_ACCOUNT` draft that sits `AWAITING_CONFIRMATION` exactly like an expense draft. **No new confirm-path code was needed**: `InteractionHandler.handle_fast_path`'s existing `ActionTypeRoutingDispatcher` routing is already generic on `DraftActionType`, so registering `MANAGE_MONEY_ACCOUNT → AccountAdminExecutionDispatcher` in `runtime/dependencies.py` was the only wiring required for the "YES" reply to actually execute.

Role gate: `ADMIN`/`FINANCE` only (matches the plan's permission table), checked against `ActorIdentity.role` using the same normalization idiom as `mesiri.authorization.roles.role_is_org_wide` (`str(role or "").strip().upper()`) — confirmed empirically that `users.role` is stored uppercase (`'ADMIN'`), not the lowercase `UserRole` SQLAlchemy enum in `infrastructure/postgres/models/user.py`, which is unused by any real query path.

Backend: new `application/finance/` package (`commands`, `validation`, `resolution`, `handlers`, `mapper`, `dispatcher`, `fakes`) mirroring `application/expenses/`'s shape exactly, plus `infrastructure/postgres/repositories/account_admin_execution.py` (idempotency-claim pattern identical to `expense_execution.py`). `PostgresMoneyAccountRepository` gained `find_by_name_exact_active`, `rename`, `deactivate` (deactivate is a status flip only, never a hard delete, per the account lifecycle above). No new migration — all three operations use columns `money_accounts` already had.

Tests: `test_account_admin_parser.py`, `test_account_admin_nodes.py`, `test_account_admin_journey.py` (role gate, voice-ignored, unrecognized-text), `test_account_admin_graph.py` (real LangGraph, no DB), backend `test_account_admin_{validation,mapper,handler}.py` (fakes), `test_account_admin_execution.py` (real DB — create/rename/deactivate, duplicate-name rejection, not-found rejection, idempotent replay).

## Slice 2 — Expense & balance queries ([STA-144](https://linear.app/starshape-pvt/issue/STA-144)) — DONE

Covers "how much cash do I have?", "balance of Site Cash", "show my expenses today", "how much did we spend on diesel?". Informational (no draft, no confirmation) — mirrors `workflows/material_inventory_query/`'s shape exactly: a single-node graph reading data already seeded into `collected_fields`.

**Real AI classification, not a deterministic bypass** (unlike Slice 6a's account admin) — "how much cash do I have" genuinely needs NLU to recognize the intent and extract `account_name`/`category_name`/`date_range`. Added one new `SemanticType.FINANCE_QUERY` (not two), which splits into two `CanonicalEventType`s by an extracted `query_kind` field ("balance"|"expenses"), the same pattern `MATERIAL_UPDATE` already uses to split by `direction` — kept the AI-facing surface to one new concept rather than two. Both Gemini and DeepSeek extraction prompts updated with the new semantic type and its field schema (the two providers implementing `StructuredExtractionProvider`); `FinanceQueryCandidate` added to the shared candidate registry.

Two new `WorkflowKey`s (`finance.account_query`, `expense.query`), both added to `_INFORMATIONAL_WORKFLOW_KEYS` — exempt from the single-active confirmation gate, same as `WHO_AM_I`/`MATERIAL_INVENTORY_QUERY`.

**Data seeding** (a node must never query a repository itself): `runtime/inbound_journey.py` gained `_seed_finance_query_context()`, mirroring `_inject_inventory_context`'s existing pattern — one new function, no new branches in the file's main control flow. For a balance query it resolves `account_name` against the org's accounts (reusing `workflows.slots.match_slot_answer` — one matching rule for the whole finance module, not a second one invented here) and fetches each match's balance. For an expense query it resolves the `date_range` bucket ("today"/"this_week"/"this_month", default "this_month") to concrete dates and queries confirmed expenses, optionally filtered by category name — **a named-but-unresolvable category returns zero results, not "ignore the filter and show everything."**

Backend: `PostgresExpenseRepository` gained `list_confirmed()` (project/site/date-range/category filters, additive AND). No new migration — all filtering is on columns `expenses` already had. `MoneyAccountQueryService` (from Slice 0) gained `find_matching_accounts()`/`get_balances()`.

**Scope cut, deliberate**: queries are always scoped to the user's currently-resolved project (no org-wide "all projects" variant yet, even for ADMIN/FINANCE) — parsing "across all projects" from free text was judged unnecessary complexity for this pass. Revisit if it turns out to matter in practice.

Tests: `test_expense_query_service.py` (date-range buckets, total — pure), `test_account_balance_query_workflow.py` / `test_expense_query_workflow.py` (node formatting), `test_canonicalization.py` (FINANCE_QUERY → the two event types, plus the existing all-semantic-types parametrized test), `test_finance_query_graphs.py` (real LangGraph, no DB), backend `test_finance_query_services.py` (real DB — account matching, balances, `list_confirmed` filters).

## Slice 3 — Transfers between accounts ([STA-145](https://linear.app/starshape-pvt/issue/STA-145)) — DONE

"Transfer ₹50,000 from Company Account to Site Cash" now posts **one** `money_transactions` row (`transaction_type='transfer'`, both `from_account_id`/`to_account_id` set) via the existing `PostgresMoneyTransactionRepository.record()` (Slice 0) — `get_balance()`'s derived-balance formula needed no changes to reflect both legs correctly.

**Two-slot fill, reusing Slice 1's `workflows/slots.py` twice** — `resolve_from_account` then `resolve_to_account`, each trying the AI-extracted account name first (`match_slot_answer` against the org's real accounts) and asking only if it doesn't resolve. `resolve_to_account` excludes whichever account `resolve_from_account` already picked from its own candidate list, so the two slots can never resolve to the same account through the ask-a-question path.

**Real bug found and fixed building this**: the graph's per-slot conditional edges initially checked `state.get("awaiting_slot")` truthily (any slot) rather than checking for *that specific slot*. A stale `awaiting_slot="to_account_id"` left over from the previous round (the from-slot already resolved, now answering the to-slot) made the edge *after* `resolve_from_account` misfire and end the graph early, since any truthy value looked like "still asking." Fixed to check the exact slot name per edge (`_route_after_from`/`_route_after_to`) — caught by the real-LangGraph three-round integration test, not the unit tests (which never round-trip through two full re-invocations).

**One new `SemanticType.TRANSFER`** (not split, unlike `FINANCE_QUERY` — transfer is a single, single-purpose intent), both extraction prompts updated with the field schema (`amount`, `from_account_name`, `to_account_name`, `description`).

**Role enforcement, a deliberate placement choice**: `ADMIN`/`FINANCE`/`PROJECT_MANAGER` only, never `SITE_ENGINEER` — enforced in `application/finance/transfer_validation.py` at **confirm time**, not before slot-filling starts. There is no existing precedent in this codebase for a WhatsApp-CQRS-path role gate before a draft is built (account admin's early gate only works because it bypasses the AI pipeline entirely, see Slice 6a) — building one here would mean threading `ActorIdentity` through the `ExecutionDispatcher` protocol for every domain. Instead `created_by_role` travels through the draft the same way `amount`/`from_account_id`/`to_account_id` already do (seeded in `_seed_account_candidates`, now extended to also fire for `WorkflowKey.TRANSFER`). Trade-off, stated plainly: a disallowed role can complete both slot-fills before being told no, rather than being stopped immediately.

Backend: new `application/finance/transfer_{commands,validation,resolution,mapper,handler,dispatcher,repository,fakes}.py` + `infrastructure/postgres/repositories/transfer_execution.py`, mirroring the account-admin (Slice 6a) file shape exactly. `PostgresTransferAccountResolver` re-verifies both accounts are still active at confirm time (defense-in-depth — an account could have been deactivated, Slice 6a, in the gap between draft and confirmation). No new migration.

Tests: `test_transfer_nodes.py` (both-names-resolve, ask-and-answer, excludes-already-picked-account), `test_canonicalization.py` (TRANSFER → TRANSFER_REQUESTED), `test_transfer_graph.py` (real LangGraph — the full two-round ask/answer/ask/answer/confirm path, this is what caught the routing bug above), backend `test_transfer_{validation,mapper,handler}.py` (fakes), `test_transfer_execution.py` (real DB — one ledger row, both balances move, inactive-account rejection, idempotent replay).

## Slice 6 (receipt-capture portion, via a new image-purpose picker) — DONE, done out of order

Built ahead of Slices 4–5 because a real gap surfaced during use: sending a photo relied entirely on two independent, chained AI guesses (Gemini vision's `document_classification` → discarded, never forwarded → a second, unrelated extraction call re-guessing the semantic type from the vision description text alone) to decide "this is an expense." A WhatsApp caption sent alongside a photo was (and structurally still is, for anything other than this new gate) completely ignored — `understanding/pipeline.py`'s `_handle_image()` never reads `message.text`.

**Replaced the guess with an explicit picker, generalized beyond expenses.** Every genuinely new image (not a tap answering this picker) is now held and asked "📷 What is this photo for?" (`channel/replies.py`'s `IMAGE_PURPOSE_ROWS`) before understanding ever runs — mirrors the existing category-menu-tap pattern (`CATEGORY_ROWS`/`CategoryHintStore`) but has to hold the image itself, not just a hint, since nothing about the message has been understood yet. New `interactions/pending_media.py::PendingMediaStore` (Redis-backed, pop-once, same shape as `PendingReportStore`) holds the full `NormalizedMessage`; `interactions/image_purpose.py::try_hold_new_image_for_purpose_picker` is the hold-and-ask gate, wired into `runtime/dependencies.py` right before the terminal `process_inbound_message` call (the last fast-path check before the normal AI journey). Tapping a choice pops the held image and re-invokes `process_inbound_message` with that choice as a `semantic_hint` — same nudge-not-authority mechanism the category menu already uses, deliberately kept consistent rather than making the image-purpose choice authoritative.

**Deliberately narrow for now**: only two rows, `Expense` and `Site Update`. Site Update replies "coming soon" (`render_image_purpose_coming_soon`) rather than silently failing — `WorkflowKey.SITE_UPDATE` has no compiled LangGraph graph at all today (a pre-existing gap, confirmed by reading `workflows/registry.py`; typing a general site update message hits the same `NO_GRAPH` outcome already, independent of images). Building that workflow is separate, unrelated follow-up work, not an image-handling gap. More purposes (attendance, etc.) get their own row later, not a different mechanism.

**The other real gap — receipt images were never saved.** `PostgresExpenseAttachmentRepository` had `list_for_expense` but no write method at all; `DraftActionV2.fields`/`RecordExpenseCommand` had no media carrier. Fixed generically, not expense-specifically: `canonicalization/builder.py` now copies `UnderstandingResult.original_content_reference` (already computed at pipeline entry, previously unused downstream) onto every event's `fields["media_object_key"]` when present — any future domain that wants the source media gets this for free. `RecordExpenseCommand` gained `media_object_key`; `expense_capture/nodes.py`'s `build_draft` keeps it (unlike the `account_candidates` plumbing field, which is stripped) but `request_confirmation` hides the raw key from the confirmation text, showing "📎 Receipt attached" instead. `PostgresExpenseAttachmentRepository.create()` (new) is called from `expense_execution.py`'s `persist_success()` — same connection, same transaction, same reasoning as the payment write, `attachment_type='receipt'`.

Tests: `test_pending_media.py`/`test_image_purpose.py` (hold-and-pop, modality gating), `test_replies.py`/`test_interaction_handler.py` (picker rows, tap detection, coming-soon), `test_canonicalization.py` (media_object_key carry-through, generic across event types), `test_expense_capture_nodes.py` (kept in draft.fields, hidden from display), backend `test_expense_command_mapper.py` + `test_expense_execution_money_wiring.py` (real DB — attachment row written with/without an image). Full non-integration suites green (935 tests: backend + whatsapp-assistant + shared contracts + platform/ai).

## Slice 4 — Vendor/payee ([STA-146](https://linear.app/starshape-pvt/issue/STA-146)) — DONE

Fixed a real schema drift, not new design: `Expense.vendor_id` and `domains/vendors/` already existed, but no migration ever created a `vendors` table or `expenses.vendor_id` column — the entity field was silently always `None`. Migration `0370` creates `vendors` (org-scoped, mirrors `expense_categories`'s shape from `0320` exactly — same unique-name/index/status-check conventions, `ON DELETE CASCADE` from `organizations` per migration `0361`'s rule for every new tenant-scoped table) and adds `expenses.vendor_id` (nullable FK).

**Deliberately soft, unlike category resolution.** `application/vendors/resolution.py`'s `PostgresVendorResolver` never blocks and never rejects: `vendor_text` absent leaves `vendor_id` null (an expense genuinely may have no vendor), and an unmatched `vendor_text` gets a **brand-new vendor row** (`PostgresVendorRepository.create`, ON CONFLICT DO NOTHING for the first-use race) rather than falling into a shared "Uncategorized"-style default bucket — every distinct vendor name is itself worth keeping. No new workflow graph node or slot: `vendor` was already one of the extraction prompt's expense fields (Gemini/DeepSeek already ask for it), so `mapper.py` just reads `fields.get("vendor")` into `vendor_text` and the resolver runs at persist time, the same place category resolution already runs — this mirrors category's exact-match-then-fallback shape (`application/expenses/resolution.py`) closely enough that reuse, not a new mechanism, was the right call.

Tests: `test_postgres_vendor_resolver.py` (real DB — exact match, create-on-first-use, no-vendor stays null, idempotent concurrent-ish create), `test_expense_execution_handler.py` (fakes — resolver only consulted when `vendor_id` absent), `test_expense_command_mapper.py` (`vendor` field maps to `vendor_text`), `test_expense_execution_money_wiring.py` (real DB — `vendor_id` actually lands on the `expenses` row).

## Slice 5 — Petty cash issue/return ([STA-147](https://linear.app/starshape-pvt/issue/STA-147)) — DONE

Built exactly as a convenience shape over Slice 3's transfer, per the plan and Linear ticket: **no new transaction type.** `workflows/petty_cash/nodes.py`'s `build_draft` emits the identical `DraftActionType.TRANSFER_MONEY` transfer's own `build_draft` emits, so the entire existing backend chain (`transfer_{mapper,validation,resolution,handler,dispatcher}.py`) needed **zero** changes — `interactions/execution_router.py` dispatches by `DraftActionType`, not by workflow, so the already-registered transfer dispatcher picks it up unchanged.

**The one new piece: resolving a recipient's name into their employee-advance account.** "Give ₹20,000 petty cash to Alan" needs to know which `money_accounts` row is "Alan's petty cash," auto-created on first issuance (`account_type='employee_advance'`, `owner_user_id` set, name defaulted to `"{full_name} — Petty Cash"` — the one case in V1 where a non-admin action, a PROJECT_MANAGER issuing petty cash rather than ADMIN/FINANCE creating an account, can create an account, because the account is for the recipient). This needed a genuinely new lookup that didn't exist anywhere in the codebase: `infrastructure/postgres/repositories/users.py` (new, minimal — just `find_by_full_name_active`, not a general users repository) plus `application/finance/petty_cash_resolution.py`'s `PostgresPettyCashRecipientResolver`, wrapped for the WhatsApp side by `runtime/petty_cash_query.py` (mirrors `money_account_query.py`'s shape). An unrecognized name is never defaulted or rejected here either — it resolves to `None`, leaving that leg of the transfer unset; the existing `transfer_validation.py` rejects a draft missing either account.

**New `SemanticType.PETTY_CASH`, splitting by `direction` ("issue"/"return") into two `CanonicalEventType`s**, the same pattern `MATERIAL_UPDATE`/`FINANCE_QUERY` already use (`canonicalization/mapping.py`) — both map to one new `WorkflowKey.PETTY_CASH` (`planner/routing.py`), since the graph itself branches on `direction` rather than needing two separate graphs. `workflows/petty_cash/nodes.py::resolve_other_account` is a single-slot resolution (mirrors `expense_capture`'s `resolve_account`, not transfer's two-slot chain) since only one leg of the transfer is ever ambiguous — the recipient's leg is already resolved by the seeding step before the graph runs (`runtime/inbound_journey.py::_seed_petty_cash_recipient`, called the same principled way `_seed_account_candidates` already is: **a node must never query a repository itself**). `_seed_account_candidates` itself was extended to also fire for `WorkflowKey.PETTY_CASH` (seeding both the org's normal accounts and `created_by_role`, since petty cash is gated by the same `ADMIN`/`FINANCE`/`PROJECT_MANAGER`-only role check transfer already enforces — issuing petty cash is still a transfer, so the same permission table entry applies unchanged).

Tests: `test_petty_cash_nodes.py` (prefill-and-ask for both directions, unresolved-recipient still lets the other leg resolve, build_draft strips plumbing fields including `direction`), `test_petty_cash_graph.py` (real LangGraph — one-candidate auto-fill and multi-candidate ask/answer/confirm, for both issue and return), `test_canonicalization.py` (issue/return event-type split, missing-amount/missing-recipient clarification, missing-direction unrecognized), `test_petty_cash_recipient_resolver.py` (real DB — auto-creates exactly once, second issuance reuses it, unrecognized name resolves to `None`).

## Slice 6 (missing-receipt-nudge portion) and Slices 7–8 (V1, not yet started)

Missing-receipt nudge ("you have 3 expenses without receipts", [STA-159](https://linear.app/starshape-pvt/issue/STA-159), narrowed now that receipt capture itself is done — see above), edit/cancel/reverse ([STA-149](https://linear.app/starshape-pvt/issue/STA-149)), duplicate detection ([STA-150](https://linear.app/starshape-pvt/issue/STA-150)).

## Slices 9–12 + dashboard (V2, deferred)

See [STA-151](https://linear.app/starshape-pvt/issue/STA-151)–[STA-154](https://linear.app/starshape-pvt/issue/STA-154) and [STA-84](https://linear.app/starshape-pvt/issue/STA-84).

---

## Critical files

**Slice 0:** `backend/src/mesiri/application/expenses/{commands,mapper,validation}.py` · `.../infrastructure/postgres/repositories/expense_execution.py` · `backend/migrations/versions/0367_finance_money_transaction_idempotency.py` · `apps/whatsapp-assistant/src/runtime/money_account_query.py`.

**Slice 1:** `shared/contracts/src/mesiri_contracts/assistant/v2/workflow_state.py` · `apps/whatsapp-assistant/src/workflows/{state,slots,ports,fakes,runtime}.py` · `.../workflows/expense_capture/{nodes,graph}.py` · `.../backend/postgres/workflow_instance.py` · `.../interactions/{handler,response_handler}.py` · `.../runtime/{inbound_journey,dependencies}.py`.

**Slice 6 (account-admin portion):** `shared/contracts/src/mesiri_contracts/assistant/{draft_action,planner_decision,canonical_event}.py` · `backend/src/mesiri/application/finance/` (new package) · `.../infrastructure/postgres/repositories/{finance,account_admin_execution}.py` · `apps/whatsapp-assistant/src/workflows/account_admin/` (new package) · `.../workflows/registry.py` · `.../planner/routing.py` · `.../runtime/{account_admin_parser,account_admin_journey,dependencies}.py`.

**Slice 2:** `shared/contracts/src/mesiri_contracts/assistant/{enums,canonical_event,planner_decision,candidates}.py` · `platform/ai/src/mesiri_ai/adapters/{gemini,deepseek}/adapter.py` (extraction prompts) · `backend/src/mesiri/infrastructure/postgres/repositories/expenses.py` (`list_confirmed`) · `apps/whatsapp-assistant/src/canonicalization/mapping.py` · `.../understanding/pipeline.py` · `.../workflows/{runtime,registry}.py` · `.../workflows/{account_balance_query,expense_query}/` (new packages) · `.../planner/routing.py` · `.../runtime/{money_account_query,expense_query_service,inbound_journey,dependencies}.py`.

**Slice 3:** `shared/contracts/src/mesiri_contracts/assistant/{enums,canonical_event,planner_decision,draft_action,candidates}.py` · `platform/ai/src/mesiri_ai/adapters/{gemini,deepseek}/adapter.py` · `backend/src/mesiri/application/finance/transfer_*.py` (new files) · `.../infrastructure/postgres/repositories/transfer_execution.py` (new) · `apps/whatsapp-assistant/src/workflows/transfer/` (new package) · `.../workflows/registry.py` · `.../canonicalization/mapping.py` · `.../understanding/pipeline.py` · `.../planner/routing.py` · `.../runtime/{inbound_journey,dependencies}.py`.

**Slice 6 (receipt-capture portion):** `apps/whatsapp-assistant/src/interactions/{pending_media,image_purpose}.py` (new) · `.../interactions/handler.py` · `.../channel/replies.py` · `.../canonicalization/builder.py` · `.../workflows/expense_capture/nodes.py` · `.../runtime/dependencies.py` · `backend/src/mesiri/application/expenses/{commands,mapper}.py` · `.../infrastructure/postgres/repositories/{expenses,expense_execution}.py`.

**Slice 4 (vendor/payee):** `backend/migrations/versions/0370_finance_add_vendors.py` (new) · `backend/src/mesiri/domains/vendors/entities.py` (new) · `.../infrastructure/postgres/repositories/vendors.py` (new) · `.../application/vendors/resolution.py` (new) · `.../application/expenses/{commands,mapper,handlers,fakes}.py` · `.../infrastructure/postgres/repositories/{expense_execution,expenses}.py` · `apps/whatsapp-assistant/src/runtime/dependencies.py`.

**Slice 5 (petty cash):** `shared/contracts/src/mesiri_contracts/assistant/{enums,canonical_event,planner_decision,candidates}.py` · `platform/ai/src/mesiri_ai/adapters/{gemini,deepseek}/adapter.py` · `backend/src/mesiri/infrastructure/postgres/repositories/users.py` (new) · `.../application/finance/petty_cash_resolution.py` (new) · `apps/whatsapp-assistant/src/workflows/petty_cash/` (new package) · `.../workflows/registry.py` · `.../canonicalization/mapping.py` · `.../understanding/pipeline.py` · `.../planner/routing.py` · `.../runtime/{petty_cash_query,inbound_journey,dependencies}.py`. No new migration and no changes to `application/finance/transfer_*.py` — reuses the existing transfer backend unchanged.

## Verification

Every slice: full non-integration suites in `backend/`, `apps/whatsapp-assistant/`, and `shared/contracts/` (a contract field changed in Slice 1) must pass, plus `ruff check`. Slice-specific test names are listed above per slice.
