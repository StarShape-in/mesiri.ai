# Mesiri.AI — Agent Guidelines

> **You are an AI coding agent working in this monorepo.**  
> Follow these rules on every task unless a folder-specific `AGENTS.md` overrides them.

---

## The 3 R's of Coding

Apply these in order before writing new code:

### 1. Reduce

- Keep every change as small as possible. Fix the problem — don't expand scope.
- Remove dead code, unused imports, and redundant abstractions when you touch a file.
- Prefer one clear solution over multiple fallbacks for unlikely edge cases.
- Do not add features, refactors, or docs the user did not ask for.

### 2. Reuse

- Read surrounding code before writing. Match naming, types, patterns, and import style.
- Extend existing functions, components, and modules instead of duplicating logic.
- Search the codebase for prior art before introducing a new helper, utility, or pattern.
- When no project convention exists, follow language and framework best practices.

### 3. Refactor

- Improve structure only when it directly supports the current task.
- Refactor incrementally inside the files you are already changing — not as a separate sweep.
- Extract a module or component when a file grows too large or responsibilities diverge.
- Preserve behavior. Refactoring is restructuring, not rewriting from scratch.

---

## File Size Limit

**Do not create or grow source files beyond ~1,000 lines** unless there is a clear, documented reason.

### When a file approaches 1,000 lines

1. Stop adding to it.
2. Split by single responsibility — one module, component, or concern per file.
3. Keep public APIs stable; move internals into focused submodules.

### Acceptable exceptions (must be intentional)

- Generated code (lockfiles, migrations, OpenAPI specs)
- Large static data or fixture files
- Folder-specific constitution docs (e.g. `apps/whatsapp-assistant/AGENTS.md`)
- A monolithic config or registry that is genuinely one cohesive unit and splitting would hurt clarity

When an exception applies, add a brief comment at the top of the file explaining why it stays large.

---

## Explain Before Executing

**Never silently implement a non-trivial change.** Before writing code for anything beyond a one-line fix:

1. Explain what you're about to change and why, in two registers:
   - **Plain language first** — a short analogy or non-jargon description of what the change does, for a non-coder reading along.
   - **Technical detail after** — the actual files, functions, and contracts involved.
2. Use a diagram (flowchart, sequence trace) whenever the change touches more than one module or is easier to see than to describe — don't default to a wall of text for architecture-level changes.
3. Wait for at least implicit go-ahead before writing code. "Sounds good", "yes", or silence-after-a-clear-plan counts; moving straight from explanation to implementation without pausing does not.

This applies to real feature work and bug fixes — not to routine verification (running tests, checking git status) or to work the user has already explicitly and specifically authorized in the same message.

---

## Git Workflow — This Is a Shared, Actively-Developed Repo

Other contributors push to `main` frequently and mid-session. Follow this sequence every time, no exceptions:

1. **Before starting work**: `git fetch origin main` and check divergence (`git rev-list --left-right --count origin/main...HEAD`). Pull if behind.
2. **Before committing**: run the full test suite (see below) and lint — not a subset.
3. **Before pushing**: `git fetch`/pull again. New commits routinely land between when you started and when you're ready to push. If your pull touches a file you've also edited, read the merge result before pushing — don't assume it merged correctly.
4. **Never lose either side's changes.** A conflict or overlap gets resolved by hand, preserving both contributions — never resolved by blindly picking one side.
5. If a partner's push has lint/CI errors unrelated to your own changes, that's on them to fix — don't silently fix someone else's broken commit unless asked to.

### Test suite — run the whole thing, not just `tests/unit`

`apps/whatsapp-assistant` and `backend` each have multiple test directories (`unit/`, `contract/`, `scenario/`, `integration/`) that CI runs together. Running only `tests/unit` has previously let a real regression through that `tests/contract` caught. Before declaring "tests pass" or pushing:

```bash
# from apps/whatsapp-assistant
pytest tests/ --ignore=tests/integration -q

# from backend
pytest tests/ --ignore=tests/integration -q
```

`tests/integration` needs a live database that isn't reachable from every dev environment — excluded here, not skipped silently elsewhere. Also run the `shared/contracts` and `platform/ai` suites when you've touched either package. Lint with `ruff check` across whichever `src/` trees you touched before committing.

---

## Module Placement Log

**Why this exists:** an earlier version of this project was discarded entirely because new code was added ad hoc, with no agreed record of which module owned what — the architecture became too messy to keep building on. Never again. This log is the fix.

**Rule:** before writing code for any new module, feature, or table (not a bug fix inside an existing module) — even at the planning stage, before implementation starts — decide and record here:

1. **Which existing module/folder/layer it belongs to** (or that a genuinely new one is needed, and why — check the layer-ownership table in `docs/architecture/Core-architecture.md` first).
2. **Where the design doc lives**, if there is one (link it).
3. **Status**: `planned` / `in progress` / `done`.

Update the row's status as work progresses. A stale or missing row is worse than none — keep this table honest, not aspirational. If a plan is large enough to need its own document, put that document under `docs/execution/` and link it here rather than pasting the whole plan into this file.

| Feature | Belongs in | Design doc | Status |
|---|---|---|---|
| Materials catalogue + units-of-measure + immutable movement ledger (retires the `_UNIT_ALIASES` stopgap from `1ad7977`) | `backend/domains/materials/` (`posting.py` done), `backend/migrations/` (`0290`/`0300`/`0310` done, including production self-heal fixes), `apps/whatsapp-assistant/src/runtime/material_catalog_query.py` (done, wired into `inbound_journey.py`'s resolution gate), `apps/dashboard/src/components/materials/manage-catalogue-dialog.tsx` (done) | [docs/execution/MATERIALS_CATALOGUE_PLAN.md](docs/execution/MATERIALS_CATALOGUE_PLAN.md) | in progress — backend/WhatsApp/dashboard pieces largely landed by Ilan as of 2026-07-12; verify end-to-end before marking done |
| Unit conversion within the same physical dimension (e.g. feet ↔ cm) — store as reported, calculate on demand when asked in a different unit | **Owned by Ilan** — he confirmed he'll implement this himself, extending `units_of_measure` (`0290`). Do not implement from this side; check the live schema before assuming this is still open if picked up later. | Open decision logged in the materials catalogue plan above | assigned to Ilan |
| Post-confirmation receipt image (WhatsApp) — after any confirmed record (material receipt/usage today, extensible to expense/labour/equipment later), reply with one visual receipt card instead of plain "✅ Recorded" text. Single shared template across all record types, data-driven, never a different image layout per type. | `apps/whatsapp-assistant/src/channel/receipt/` (`data.py`/`template.py`/`render.py`/`builder.py`, done — Jinja2 HTML/CSS re-implementation of the user-supplied `RecordCard` React design, rendered to PNG via Python `playwright`, headless Chromium, in-process, no new service). `interactions/ports.py`'s new `ReceiptBuilder` protocol, wired via `interactions/handler.py`'s `_resume_and_render()`. `WhatsAppSender.send_image()` in `channel/whatsapp/outbound.py`. | None (design notes in commit `f146707`) | done — manually verified by rendering a real PNG and visually checking it; not yet confirmed against a live WhatsApp send |
| Finance module (WhatsApp-first) — wire confirmed expenses to real money movement, then a LangGraph spine for mid-workflow slot-filling ("which account?"), then one workflow per capability (queries, transfers, petty cash, vendor/payee, account admin, receipts, reversal, duplicate detection). Purchases/procurement and the dashboard UI are explicitly out of scope here. | `backend/src/mesiri/{application,infrastructure/postgres/repositories}/{expenses,finance,vendors}/`, `backend/migrations/` (`0367`-`0370`), `apps/whatsapp-assistant/src/{workflows,runtime,interactions,canonicalization,understanding,planner}/`, `shared/contracts/.../{v2/workflow_state,draft_action,planner_decision,canonical_event,enums,candidates}.py`, `platform/ai/src/mesiri_ai/adapters/{gemini,deepseek}/` (extraction prompts) | [docs/execution/FINANCE_MODULE_PLAN.md](docs/execution/FINANCE_MODULE_PLAN.md) (Linear epics [STA-140](https://linear.app/starshape-pvt/issue/STA-140)/[STA-141](https://linear.app/starshape-pvt/issue/STA-141)) | V1 complete (Slices 0–8) as of 2026-07-25 (Slice 6 fully: account-admin, receipt-capture, and missing-receipt-nudge portions, the first two done out of order); V2 (budgets, approvals, reports, analytics, dashboard) not started |
| Finance Transactions Page (Web Dashboard) — company-wide money movement ledger for all financial transactions (transfers, expense payments, petty cash vouchers, client inflows, and reversals). | `backend/src/mesiri/domains/finance/router.py`, `backend/src/mesiri/infrastructure/postgres/repositories/finance.py`, `apps/dashboard/src/pages/TransactionsPage.tsx`, `apps/dashboard/src/lib/api.ts` | None | done — complete with company-wide ledger API, type-safe frontend, real DB connection, unit tests passing, pushed to main |
| Finance Overview Page (Web Dashboard) — CFO executive command center displaying liquidity metrics, spending trends, category distribution, account balances, and recent financial activities. | `backend/src/mesiri/domains/finance/router.py`, `apps/dashboard/src/pages/FinanceOverviewPage.tsx`, `apps/dashboard/src/lib/api.ts` | None | done — complete with executive summary API, recharts visual distribution, real DB connection, unit tests passing, pushed to main |
| Finance Settings Page (Web Dashboard) — organization financial policies, currency preferences, WhatsApp auto-approval limits, low float alert thresholds, and payment methods. | `backend/src/mesiri/domains/finance/router.py`, `apps/dashboard/src/pages/FinanceSettingsPage.tsx`, `apps/dashboard/src/lib/api.ts` | None | done — complete with REST settings endpoints, tabbed UI, real DB connection, unit tests passing, pushed to main |
| Finance Reports Page (Web Dashboard) — executive financial statements generator (P&L, Category Spend, Cash Flow, Vendor Outstandings, Petty Cash Reconciliation) with 1-click CSV export. | `backend/src/mesiri/domains/finance/router.py`, `apps/dashboard/src/pages/FinanceReportsPage.tsx`, `apps/dashboard/src/lib/api.ts` | None | done — complete with REST report statement endpoints, CSV exporter, real DB connection, unit tests passing, pushed to main |
| Control Plane Finance Data Seeder — 1-click provisioning of schema-compliant money accounts, expense categories, vendors, finance settings, and demo transactions for an organization. | `backend/src/mesiri/domains/finance/seeder.py`, `backend/src/mesiri/domains/admin/router.py`, `apps/control-panel/src/OrganizationDetail.tsx` | None | done — complete with idempotent seeder service, FastAPI admin endpoint, control panel UI modal, and 100% passing unit tests |
| Optional Expense Tax Metadata Preservation — generic country-agnostic tax preservation (`tax_rate`, `tax_amount`, `is_tax_inclusive`) stored as nullable columns, exposed in REST API, rendered on Expense Details Page, and included in Finance Reports CSV exports. | `backend/migrations/versions/0380_finance_add_expense_tax.py`, `backend/src/mesiri/infrastructure/postgres/repositories/expenses.py`, `backend/src/mesiri/domains/expenses/responses.py`, `apps/dashboard/src/pages/ExpenseDetailPage.tsx`, `apps/dashboard/src/pages/FinanceReportsPage.tsx` | [docs/execution/FINANCE_MODULE_PLAN.md](docs/execution/FINANCE_MODULE_PLAN.md) | done — migration 0380 added, backend entities/repos updated, typecheck clean, 230 tests passing, pushed to main |
| Sequential Expense Numbers (`EXP-001`, `EXP-002`, ...) — per-project incremental expense numbers generated on PostgreSQL creation, backfill migration 0390, exposed in REST API and rendered across Web Dashboard. | `backend/migrations/versions/0390_finance_sequential_expense_numbers.py`, `backend/src/mesiri/infrastructure/postgres/repositories/expense_execution.py`, `backend/src/mesiri/domains/expenses/router.py`, `apps/dashboard/src/pages/ExpenseDetailPage.tsx` | None | done — migration 0390 added, postgres sequence generator added in expense_execution.py, 230 tests passing, pushed to main |
| Sequential Entity Codes (`ACC-001`, `VND-001`, `CAT-001`) — per-organization incremental entity codes generated on PostgreSQL creation across Money Accounts, Vendors, and Expense Categories, backfill migration 0400, exposed in REST API and rendered across Web Dashboard. | `backend/migrations/versions/0400_finance_sequential_entity_codes.py`, `backend/src/mesiri/infrastructure/postgres/repositories/{finance,vendors,expenses}.py`, `backend/src/mesiri/domains/finance/router.py`, `apps/dashboard/src/lib/api.ts` | None | done — migration 0400 added, entity repository sequence generators added, 233 tests passing, pushed to main |
| WhatsApp Assistant & Automations Page Wiring — persistent automation policies via GET/PATCH /finance/settings, real DB message activity stream in whatsapp-trace-logs.tsx, live custodian phone mapping, and non-polluting dry-run sandbox simulator. | `backend/src/mesiri/domains/finance/router.py`, `apps/dashboard/src/pages/WhatsAppFinancePage.tsx`, `apps/dashboard/src/components/whatsapp/{phone-mapping-table,whatsapp-trace-logs,whatsapp-sandbox-dialog}.tsx` | None | done — complete with persistent settings REST wiring, non-polluting sandbox, message activity audit stream, 265 tests passing, pushed to main |
| Labour & Workforce Module (Web Dashboard) — sidebar navigation category, routes, WhatsApp automations page bound to GET/PATCH /labour/settings, dry-run simulator bound to POST /labour/whatsapp/sandbox/simulate, worker roster, attendance, overview, reports, and settings. | `backend/src/mesiri/domains/workforce/router.py`, `apps/dashboard/src/pages/{WhatsAppLabourPage,WorkersPage,AttendancePage,LabourOverviewPage,LabourReportsPage,LabourSettingsPage}.tsx`, `apps/dashboard/src/components/app-sidebar.tsx`, `apps/dashboard/src/App.tsx`, `apps/dashboard/src/lib/api.ts` | None | done — complete with sidebar category, routes, WhatsApp automations page, dry-run sandbox, worker roster, attendance log, command overview center, executive statements, settings persistence, and 271 passing tests |
| Daily Reporting Module (Mesiri Daily core) — three-layer progress model (Work Package → Activity → append-only Progress Update), issues/blockers, evidence, and the site→project DPR draft/review/approve/freeze pipeline. Fills the existing-but-unused `WorkflowKey.SITE_UPDATE` rail (`workflows/field_update/` is 0 bytes) and the placeholder Operations sidebar category. Locations land in `core` as a shared self-referential tree, **not** inside this module (ADR-D3). Daily Reporting never writes into the materials/labour/equipment/finance ledgers — references only (ADR-D2/P3). | New: `backend/src/mesiri/{domains,application}/progress/` and `.../dpr/`, `backend/migrations/` (`0410` locations in `core`, `0420` work packages, `0430` activities/updates/issues/attachments, `0440` daily reports), `apps/whatsapp-assistant/src/workflows/site_update/` (renamed from the empty `field_update/`, ADR-D7). Extends: `shared/contracts/.../assistant/{enums,canonical_event,planner_decision}.py`, `platform/ai/.../{gemini,deepseek}/adapter.py` (`general_site_update` slots), `apps/dashboard/src/pages/{FieldReportsPage,Overview}.tsx` + new Work Packages / Daily Reports pages under the existing Operations category. Reuses: `channel/receipt/` renderer, `units_of_measure` (`0290`), `expense_attachments` shape, `0260`'s unused `reporting_*` columns. | [docs/execution/DAILY_REPORTING_PLAN.md](docs/execution/DAILY_REPORTING_PLAN.md) | in progress — Phase 0 complete, product spec adopted, WhatsApp workflow decomposition reconciled (plan §1A/§1B are the authority on scope; §3/§5/§6 on architecture). Schema written 2026-07-27: migrations `0410` (`location_nodes`, shared `core` tree), `0420` (`work_packages`), `0430` (`activities`/`progress_updates`/`site_issues`/`progress_attachments`), `0440` (`daily_reports`); domain/application folders scaffolded (`domains/{progress,dpr}/`, `application/{progress,dpr}/`). Chain verified via `alembic history` (head `0440`, no forks) — **not yet applied to a live database**, no DB access from the authoring machine. **Verified finding (partially fixed 2026-07-27):** `activity` aggregate is now registered in `timeline_projector.py`'s `AGGREGATE_TABLES` — every `ActivityCreated`/`ActivityProgressUpdateAdded`/`ActivityEvidenceAttached` outbox row was previously orphaned (marked published, never projected). Finance still never emits to `outbox_events` at all — that half of Phase 6.0 remains open and still blocks a Finance-inclusive DPR. Next: apply migrations, then Phase 1 pure domain model. |
| Event Bus (#14) — multi-consumer outbox fan-out, so #9 Notifications and #17 Search Index can each independently read `outbox_events` without stepping on `timeline_projector.py`'s own `published_at` mechanism or on each other. Cron-invoked drain-to-completion, same convention as `project_timeline_events.py` (this codebase deliberately has no persistent background-worker process). | `backend/src/mesiri/events/bus/{interface,dispatcher,__init__}.py` (done), `backend/migrations/0450_events_consumer_checkpoints.py` (done — new `event_consumer_checkpoints` table, anti-join read pattern, per-row `SAVEPOINT` for failure isolation), `backend/src/mesiri/scripts/run_event_consumers.py` (done — the cron entrypoint; `_registered_consumers()` is empty until the first real consumer is built), `Makefile`'s `event-consumers` target (done). | None | in progress — the bus itself is done and tested (8 integration tests in `backend/tests/integration/test_event_bus_dispatcher.py`, not yet run against a live DB — no DB access from the authoring machine); zero consumers registered yet. Next consumer to land here: #9 Notifications or #17 Search Index, whichever is built first. |
| Capability discovery surface (WhatsApp) — the registry becomes the single source of user-facing workflow copy (`title`/`one_liner`/`examples`/`semantic_hint`), and every discovery surface is generated from it instead of hand-listed: a tiered category menu (7 categories -> 24 pickable workflows, replacing a flat 5-row list that covered 5 of 26 and advertised an unbuilt Equipment graph), a generated `render_unsupported_reply()` (was hardcoded to "I can only record material updates right now"), and the control panel's workflow titles/examples (was 8 titles hand-maintained + examples regex-scraped out of prompt copy). Groundwork for `workflows/ask_mesiri/` (still a 0-byte stub) and for wiring `is_first_message`, which has never been set. | `apps/whatsapp-assistant/src/workflows/registry.py` (copy fields + `iter_menu_categories`/`user_initiable_in`/`definition_by_menu_row_id`), `apps/whatsapp-assistant/src/channel/replies.py` (`_category_rows`, two-level `render_category_prompt`, `_menu_semantic_hints`, `render_unsupported_reply`), `apps/whatsapp-assistant/src/admin/system_graph_router.py` (`_workflow_titles`, `_example_messages_by_workflow`) | None (design notes in this session) | in progress — steps 1-3 done 2026-07-30. (1) Registry copy fields + `allowed_roles` discovery metadata mirroring the entry-point role gates (NOT an enforcement gate — see the field comment). (2) Generated tiered menu + `render_unsupported_reply()` + control-panel titles/examples. (3) Capability help: `runtime/capability_help.py` matches a free-form "how do I ...?" question against the role-filtered registry via `JsonGenerationProvider`, injected onto `PlannerDecisionV2.metadata` (no contract change) and rendered by `render_capability_answer()` as wf_* rows that reuse the existing menu-tap handler. Built in `runtime/`, NOT as a workflow: nodes may not call AI or query anything, so a graph could only format what someone else looked up. The `workflows/ask_mesiri/` stub is therefore obsolete and should be deleted. 2248 passed / ruff clean across assistant+backend+contracts+AI (3 pre-existing `test_webhook.py` DB-setup errors in the combined run, confirmed identical on a clean HEAD worktree). Not yet verified against a live WhatsApp send or a real provider. Remaining: wire `is_first_message` (never set, dead intro copy at `replies.py`), delete `workflows/ask_mesiri/`, retire the now-unsent `MATERIAL_DIRECTION_BUTTONS`. |
| Entity Resolution & Workflow Chaining — one shared answer to "the user named a thing that isn't there", replacing ~8 backend `*resolution.py` copies (a documented copy-chain five deep), 4 assistant gates, and 7 `resume_pending_report_with_*` paths. Three parts: a single resolve outcome (`Resolved`/`Ambiguous`/`Missing`, where Ambiguous is where transliteration fuzziness — ഹൈസം → Hysam/Hisham — gets solved once instead of eight times); registry `provides`/`requires` declarations so "a USER is missing, now what?" is a lookup rather than an if/else; and one hold-and-resume continuation so the original request *finishes* after the missing thing is created. Generalises the behaviour materials already have (`resume_pending_report_with_material_create`) to every entity type. | Planned new: `apps/whatsapp-assistant/src/runtime/entity_resolution/`. Extends: `workflows/registry.py` (`provides`/`requires`), `runtime/inbound_journey/{seeding,process}.py` (gates collapse into one), `interactions/pending_report.py` + `interactions/project_setup_offer.py` (the hold/offer substrate, already ~90% of what's needed). Backend `application/*/resolution.py` stay as REST-path defence in depth (ADR-E2), not deleted. | [docs/execution/ENTITY_RESOLUTION_PLAN.md](docs/execution/ENTITY_RESOLUTION_PLAN.md) | planned — design doc written 2026-07-30, no code. Phase 0 of 4. Triggered by a live Malayalam message ("add Hysam to the hospital project as PM") that hard-rejected after confirmation and could never have succeeded: the user lookup is exact-match only (`repositories/users.py:42`). Phase 3 (migrating MATERIAL) is the deliberate falsification test — if the generic path can't reproduce the material create-and-resume without special-casing, the abstraction is wrong. |

---

## Folder-Specific Rules

Some apps and packages have their own `AGENTS.md` with deeper architectural constraints. **Read and obey the nearest `AGENTS.md` in the folder tree you are editing.**

| Path | Document |
|---|---|
| `apps/whatsapp-assistant/` | [apps/whatsapp-assistant/AGENTS.md](apps/whatsapp-assistant/AGENTS.md) |

---

*Last updated: 2026-07-12 (Module Placement Log added)*
