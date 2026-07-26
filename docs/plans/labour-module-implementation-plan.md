# Labour Module — Master Implementation Plan

**Status:** In progress · Phase 0 complete (reconnaissance + design)
**Owner:** Alan Raj
**Started:** 2026-07-25
**Linear:** _(issue to be created at first code commit)_

> **Purpose of this document.** It is the durable memory for this module. If a
> future session — human or AI — loses all conversational context, this file
> alone should explain what exists, what is being built, what remains, why each
> decision was made, and what to do next. Keep it updated as work proceeds;
> a stale plan is worse than none.

---

## 1. What the Labour module is

Record **who worked, where, in what trade, and at what cost.**

It is deliberately *not* a Workforce Management System or an HRMS. V1 has
exactly one operational action: **Record Attendance**.

Explicitly out of scope for V1: payroll, salary generation, leave, overtime,
union/bonus calculation, PF/ESI, shift scheduling, GPS attendance, face
recognition, biometrics, HR management, approval workflows, performance
management.

---

## 2. Reconnaissance findings (2026-07-25)

Read before assuming anything about the current state.

### 2.1 The routing rails already exist

Labour was anticipated when the platform was laid out. These are **already
present and require no invention**:

| Thing | Where | Value |
|---|---|---|
| `WorkflowKey.LABOUR_ATTENDANCE` | `shared/contracts/.../planner_decision.py` | `"labour.attendance"` |
| `CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED` | `shared/contracts/.../canonical_event.py` | `"LabourAttendanceRequested"` |
| `SemanticType.LABOUR_UPDATE` | `shared/contracts/.../enums.py` | `"labour_update"` |
| AI extraction slot | `platform/ai/src/mesiri_ai/adapters/gemini/adapter.py` | `labour_update: headcount, trade, hours, contractor, project_name` |
| Empty workflow package | `apps/whatsapp-assistant/src/workflows/labour_update/` | `__init__.py` only, 0 bytes |
| Empty domain package | `backend/src/mesiri/domains/workforce/` | `__init__.py` only, 0 bytes |

`workflows/state.py`'s own docstring says *"Every v1 graph (material, and later
expense/equipment/labour)"* — the shape was designed with Labour in mind.

### 2.2 Existing labour tables are unusable for this product

Migration **0120** (2026-07-08) created `labour_attendance` and
`labour_attendance_entries`.

**They are unused.** A repo-wide search found only two references, neither
functional:
- `apps/whatsapp-assistant/src/admin/router.py` — a tenant-delete cascade list
- `backend/tests/integration/test_organizations_cascade_delete_schema.py`

No code reads or writes them.

Two hard incompatibilities with the V1 product:

1. **`UniqueConstraint("site_id", "occurred_date")`** — one attendance row per
   site per day. The product requires attendance to be *append-only immutable
   history*. A second report for the same site and day cannot be stored under
   this constraint without overwriting the first.
2. **`labour_attendance_entries.worker_name` is free text** — no link to any
   worker record. The product requires a reusable **workforce register** and
   matching that never relies on name alone.

The 0120 migration's own docstring anticipated this:

> *"Full Workforce (shifts, wages, contracts) is a later module and will very
> likely supersede this table rather than extend it — do not over-build here."*

**Decision:** supersede, do not extend. See ADR-L1.

### 2.3 Canonical reference modules

- **Material** — the most complete operational module; the primary reference.
- **Expense** — newer, partially complete; good reference for images
  (`expense_attachments`), slot-filling (`workflows/expense_capture`), and the
  finance-style domain layer, but **not complete**, so do not assume its
  every pattern is settled.

Where they disagree, prefer Material, and note the divergence here.

**Known divergences observed:**

| Concern | Material | Expense |
|---|---|---|
| Command contract location | `shared/contracts/.../application/commands/material.py` | `backend/.../application/expenses/commands.py` |
| Domain layer shape | thin (`validation.py`, `posting.py`, `router.py`) | rich DDD (`entities.py`, `value_objects.py`, `policies.py`, `events.py`) |
| Handler entry method | `handle()` | `handle_confirmed()` |

---

## 3. Architectural principles (non-negotiable)

These are binding constraints on the implementation, not preferences.

### P1 — Attendance ≠ Workforce

They are separate concepts and must never be conflated in code.

```
Attendance ──references──> Workforce
```

or, for someone not yet in the register:

```
Attendance ──> Temporary Worker ──optionally promoted──> Workforce
```

**There must never be code that assumes "attendance creates workers."**
Recording attendance never silently mutates the workforce register. Promotion
into the register is always an explicit, separately-confirmed act.

Rationale: attendance is immutable historical fact; the workforce register is
current mutable reference data. Letting one write the other makes history
depend on the present, and pollutes the register with one-off names.

### P2 — Universal interaction pattern

Every operational workflow in Mesiri follows:

```
AI Extraction → Structured Preview → User Confirmation → Persistence
```

The Labour workflow **must never bypass this**. Nothing is persisted before an
explicit confirmation. This is the same rhythm a user already knows from
Material and Expense, and consistency across modules is the point.

### P3 — Temporary workers are first-class

Temporary workers are expected to be **30–60% of construction attendance**,
not an edge case. They are modelled as a proper worker type with full support
throughout matching, preview and persistence — never as a degraded or
special-cased path.

### P4 — Workers are never matched by name alone

Matching produces a **confidence score** from multiple signals:

```
name + trade + contractor + previous attendance + project + site → confidence
```

Low confidence → **ask the user**. Never guess, never auto-merge.

`Ravi (Mason)` and `Ravi (Painter)` are different people.

### P5 — Attendance is immutable

Never overwrite a previous attendance record. Corrections are new records, not
mutations. This is why 0120's one-row-per-site-per-day constraint is
disqualifying.

### P6 — Reuse, don't duplicate

Images reuse the existing object-storage + attachments pattern exactly as
receipts do. No special-case image pipeline. Where Material/Expense already
share a shape, extract it rather than writing a third copy (see §7).

### P7 — Extensible without over-building

Attendance optionally links to **activity / work item / construction stage**
even though V1's UI does not expose all of it — because
`Materials → Activity → Labour → Expenses` becomes highly valuable later.
Model the relationship now; do not build the features on top of it now.

---

## 4. Implementation order

**Deliberately not database-first.** Mesiri is architected around the
assistant, so the workflow defines what the database needs — not the reverse.

```
Business Model
   ↓
Domain Model
   ↓
Contracts
   ↓
Workflow
   ↓
Persistence
   ↓
Repositories
   ↓
Application Layer
   ↓
WhatsApp Flow
   ↓
Tests
```

Tests are listed last as a phase, but each layer ships with its own tests as
it is written; the final phase is end-to-end coverage.

---

## 5. Architecture decisions (ADRs)

### ADR-L1 — Supersede the 0120 labour tables rather than extend them

**Status:** Accepted
**Context:** 0120's tables cannot express append-only history or a workforce
register (see §2.2). They are unused by any code.
**Decision:** Leave 0120's tables in place (preserving migration history; no
destructive drop) and create the real Labour schema alongside. Do not alter
0120's tables.
**Consequences:** Two unused tables remain in the schema. Accepted as the cost
of preserving migration history and avoiding any risk to environments whose
contents were not inspected. A later cleanup migration may drop them once
production is confirmed empty.
**Rejected alternatives:**
- *Extend 0120* — the aggregate-headcount shape fights the named-worker model
  at every layer, and dropping a uniqueness constraint on a live table is
  riskier than never needing one.
- *Drop and replace* — destructive; production contents were not verified from
  this machine (no DB access), so deletion cannot be justified.

### ADR-L2 — Workforce register is its own domain concept

**Status:** Accepted
**Decision:** The workforce register lives in `domains/workforce/` (the empty
package already reserved for it), separate from attendance recording.
**Consequences:** Enforces P1 structurally — the register can be read by
attendance, but attendance code has no write path into it except an explicit
promotion command.

### ADR-L3 — Attendance images reuse the attachment pattern

**Status:** Accepted
**Context:** `expense_attachments` stores `media_object_key` + `attachment_type`
against the parent record; the object itself lives in existing object storage.
**Decision:** Labour uses the identical shape for attendance sheet photos.
**Consequences:** Timeline and Image Gallery integration come for free, since
they consume the same attachment shape.

### ADR-L4 — _(reserved: shared operational abstraction — see §7, pending approval)_

---

## 6. Data model (design — not yet implemented)

> Driven by the workflow, per §4. Recorded here after the workflow design so
> the reasoning is traceable; implemented in Phase 4.

### 6.1 Workforce register

Operational fields only. **Not an HR record.**

| Field | Notes |
|---|---|
| `name` | |
| `trade` | mason, painter, helper, … |
| `worker_type` | `permanent` \| `temporary` \| `contractor` |
| `default_daily_wage` | nullable |
| `contractor` | nullable; free text or FK — see open question Q2 |
| `status` | active / inactive |

Nothing beyond operational requirements. No address, no ID documents, no
next-of-kin, no bank details.

### 6.2 Attendance

Append-only. One record per report, **not** per site-day.

| Field | Notes |
|---|---|
| `date` | the day worked |
| `project`, `site` | scope |
| `attendance_image` | optional but strongly recommended; via attachments |
| `workers` | line items — see 6.3 |
| `notes` | |
| `recorded_by`, `timestamp` | provenance |
| `activity` / `work_item` / `stage` | optional; P7 |

### 6.3 Attendance line items

Each links to **either** a registered worker **or** a temporary worker
captured inline. Carries trade and daily wage *as recorded at the time* — a
historical record must not change when the register is later edited.

---

## 7. Proposed shared abstraction — **awaiting approval before implementation**

Reconnaissance found that Material and Expense already duplicate the same
execution scaffolding almost exactly. Adding Labour would create a third copy.

**Evidence of duplication:**

| File | Material | Expense | Difference |
|---|---|---|---|
| `dispatcher.py` | `MaterialExecutionDispatcher` | `ExpenseExecutionDispatcher` | class name, log prefix, and the handler's method name (`handle` vs `handle_confirmed`) |
| `recovery.py` | `recover_confirmed_instances` | same, "mirrors materials/recovery.py exactly" per its own docstring | workflow-key set |
| `repository.py` | `MaterialExecutionRepository` | `ExpenseExecutionRepository` | command type only; identical three abstract methods |
| `resolution.py` | `ResolutionResult` + `MaterialResolver` | `ResolutionResult` + `ExpenseCategoryResolver` | `ResolutionResult` is **defined twice, identically** |

**Proposal:** extract a small `application/_operational/` package providing:
- a generic `ExecutionDispatcher[TCommand]` wrapping any handler
- a generic `ExecutionRepository[TCommand]` port (the three abstract methods)
- one shared `ResolutionResult`
- one shared `recover_confirmed_instances(db, handler, workflow_keys)`

and normalise the handler entry point to a single method name.

**Benefit:** Labour adds no new scaffolding; Material and Expense each shed a
file's worth of near-duplicate code; the `handle`/`handle_confirmed`
inconsistency disappears.

**Risk:** touches two working modules. Mitigated by their existing test
coverage, and by doing it as a separate, isolated commit *before* Labour is
built on top.

**Status:** ⏸ Proposed, not implemented. Per instruction, shared abstractions
are proposed before implementing. Requires explicit approval.

---

## 8. Phase checklist

Update as work proceeds. `[x]` = done and pushed.

### Phase 0 — Reconnaissance & design
- [x] Reverse-engineer Material module end to end
- [x] Reverse-engineer Expense module end to end
- [x] Identify existing Labour foundations
- [x] Identify 0120 incompatibilities
- [x] Identify shared-abstraction opportunities (§7)
- [x] Master implementation plan (this document)
- [ ] Dashboard plan document (`labour-dashboard-plan.md`)
- [ ] Shared-abstraction proposal approved / rejected

### Phase 1 — Business & domain model
- [ ] Worker types, trades, statuses as domain enums
- [ ] Workforce entity + invariants
- [ ] Attendance entity + line items + invariants
- [ ] Worker-matching confidence model (P4)
- [ ] Domain validation rules
- [ ] Unit tests

### Phase 2 — Contracts
- [ ] `DraftActionType.RECORD_LABOUR_ATTENDANCE`
- [ ] `RecordLabourAttendanceCommand`
- [ ] Contract tests

### Phase 3 — Workflow
- [ ] `workflows/labour_update/` graph + nodes
- [ ] Worker-matching node (asks on low confidence — P4)
- [ ] Temporary-worker handling (P3)
- [ ] Preview / confirmation node (P2)
- [ ] Register in `workflows/registry.py`
- [ ] Unit tests

### Phase 4 — Persistence
- [ ] Migration: workforce register
- [ ] Migration: attendance + line items + attachments
- [ ] Duplicate-image detection support
- [ ] Cascade-delete wiring (mirror 0361)

### Phase 5 — Repositories & application layer
- [ ] Repository port + Postgres implementation
- [ ] Mapper, handler, dispatcher, recovery
- [ ] Idempotency
- [ ] Fakes for testing
- [ ] Tests

### Phase 6 — WhatsApp flow
- [ ] Canonicalization mapping + required fields
- [ ] Planner routing
- [ ] Extraction prompt: named workers, not just headcount
- [ ] Image attachment path
- [ ] Runtime wiring (`dependencies.py`)
- [ ] End-to-end tests

### Phase 7 — Platform integration
- [ ] Timeline events
- [ ] Image Gallery
- [ ] AI context / searchability
- [ ] Analytics data exposure

### Deferred (documented, not built)
- [ ] Web Dashboard — see `labour-dashboard-plan.md`
- [ ] Control Panel UI, Mobile UI, Analytics UI, Timeline UI, Gallery UI
- [ ] CSV / Excel import

---

## 9. Open questions

| # | Question | Status |
|---|---|---|
| Q1 | Should the AI extract named workers from a photographed attendance sheet, or is headcount + trade sufficient for V1? The spec implies named workers, which is the least predictable part of this build. **Recommend testing with a real site attendance sheet early.** | Open |
| Q2 | Is `contractor` free text or a proper entity? Free text ships faster; an entity is needed if contractor-level cost reporting is wanted later. | Open |
| Q3 | Should duplicate-image detection be exact-hash only (cheap, reliable) or perceptual/near-duplicate (catches re-photographs, more false positives)? Spec says "nearly identical", implying perceptual. | Open |
| Q4 | Is a daily wage recorded per attendance line, or always inherited from the register? Recording it per line preserves history correctly (P5) but allows drift. **Recommend: inherit as default, store the value used.** | Open |

---

## 10. Known risks

| Risk | Impact | Mitigation |
|---|---|---|
| AI extraction of named workers from photos is unreliable | High — it is the primary input path | Test early with real sheets; fall back to headcount + manual naming if accuracy is poor |
| Worker matching produces false merges | High — corrupts historical records | P4 confidence model; never auto-merge on low confidence |
| Scope: this module is ≈ Material + Expense combined | Schedule risk against 9 Aug MVP | Phased delivery; Phases 1–6 give a usable WhatsApp flow; dashboard deferred by design |
| Shared-abstraction refactor destabilises Material/Expense | Medium | Isolated commit, before Labour; rely on existing test coverage |
| Temporary workers pollute the register | Medium | P1 — promotion is explicit and separately confirmed |

---

## 11. Change log

| Date | Change |
|---|---|
| 2026-07-25 | Document created. Phase 0 complete: reconnaissance, ADR-L1 to L3, principles P1–P7, shared-abstraction proposal (§7) pending approval. |
