# Labour Module — Web Dashboard Plan

**Status:** Documentation only — **no frontend code is to be written from this
document yet.**
**Depends on:** `labour-module-implementation-plan.md` (WhatsApp implementation
must land first)
**Created:** 2026-07-25

> The current objective is the WhatsApp Assistant implementation only. This
> document exists so the dashboard can be built later without re-deriving the
> requirements, and so the WhatsApp-side data model is shaped to support these
> screens rather than needing rework.

---

## 1. Why this is deferred

The WhatsApp flow is where attendance is actually captured on site. The
dashboard reads and reports on that data — it is not the primary input path
for V1. Building it before the data model is proven in real use risks
rebuilding it.

**What the dashboard must not become:** a second, divergent way to *create*
attendance with its own rules. If dashboard entry is added later it must go
through the same domain and application layer as WhatsApp, honouring the same
`Preview → Confirm → Save` pattern (principle P2).

---

## 2. Pages

### 2.1 Labour overview (`/labour`)

The landing page. Answers "what is happening with labour right now?"

**Cards (top row)**
| Card | Value | Notes |
|---|---|---|
| Workers today | count | across all accessible projects |
| Labour cost today | currency | sum of line wages |
| Workers this week | count | distinct workers |
| Labour cost this week | currency | |

**Below:** recent attendance records (most recent first), each showing date,
project, site, headcount, cost, and a thumbnail if an attendance sheet was
photographed.

**Empty state:** explain that attendance is recorded from WhatsApp, with a
short example message — the dashboard is a window onto it, not the entry point.

### 2.2 Attendance list (`/labour/attendance`)

Full history. Append-only, so this is a genuine audit trail.

**Columns:** date · project · site · headcount · trades summary · cost ·
recorded by · attachment indicator

**Row click →** attendance detail.

### 2.3 Attendance detail (`/labour/attendance/:id`)

One recorded attendance.

- Header: date, project, site, recorded by, recorded at
- The attendance sheet image, if present (full size, via the gallery viewer)
- Line items: worker, trade, worker type, wage used, activity
- Notes
- Total cost
- Provenance: which WhatsApp message produced this (link into Assistant Logs)

**Immutability must be visible.** No edit button. If corrections are needed
they are new records — the UI should say so rather than implying editability.

### 2.4 Workforce register (`/labour/workforce`)

The reusable list of workers. **This is not an HR screen.**

**Columns:** name · trade · worker type · default daily wage · contractor ·
status · last seen (most recent attendance)

**Filters:** trade, worker type, contractor, status, project worked on

**Actions:** add worker, edit worker, deactivate worker, promote a temporary
worker into the register

**Deliberately absent:** addresses, ID documents, bank details, next of kin,
salary history. If those are ever wanted, that is an HR module, not this.

### 2.5 Worker detail (`/labour/workforce/:id`)

- Profile: name, trade, type, default wage, contractor, status
- Attendance history for this worker
- Days worked this month
- Total cost attributable to this worker over a period
- Projects and sites they have worked on

### 2.6 Labour cost report (`/labour/costs`)

Operational cost only — **not payroll.**

**Breakdowns:** by site · by trade · by activity · by week
**Controls:** date range, project, site

---

## 3. APIs required

All tenant-scoped and permission-filtered exactly as Material and Expense
endpoints are — a user sees only the projects and sites their access allows
(see `mesiri/authorization/roles.py`).

### Attendance
| Method | Path | Purpose |
|---|---|---|
| `GET` | `/labour/attendance` | list; filters: project, site, date range, worker, trade, activity; paginated |
| `GET` | `/labour/attendance/{id}` | one record with line items and attachments |
| `GET` | `/labour/attendance/summary` | card values: workers/cost for today and this week |

### Workforce
| Method | Path | Purpose |
|---|---|---|
| `GET` | `/labour/workers` | list; filters: trade, type, contractor, status, search |
| `GET` | `/labour/workers/{id}` | one worker |
| `POST` | `/labour/workers` | create |
| `PATCH` | `/labour/workers/{id}` | update |
| `POST` | `/labour/workers/{id}/deactivate` | soft-delete; never hard-delete — attendance history references it |
| `POST` | `/labour/workers/promote` | promote a temporary worker into the register (explicit act — principle P1) |

### Reporting
| Method | Path | Purpose |
|---|---|---|
| `GET` | `/labour/costs` | grouped cost; `group_by=site\|trade\|activity\|week` |
| `GET` | `/labour/trends` | attendance counts over time |

**Not offered:** any endpoint that edits or deletes an attendance record.
Attendance is immutable (principle P5).

---

## 4. Filters and search

- Date range (default: this week)
- Project / site — constrained to what the user may access
- Trade
- Worker type — permanent / temporary / contractor
- Contractor
- Activity / work item
- Free-text worker name search
- "Has attendance photo" toggle — useful for audit

---

## 5. Platform integration

### Timeline
Each confirmed attendance emits a timeline event, so labour appears in the
project feed alongside material and expense activity. Summary line should read
naturally, e.g. *"12 workers recorded at Riverside Tower — Site B"*.

### Image gallery
Attendance photos flow into the existing gallery via the same attachment shape
receipts use (ADR-L3). They should be filterable as an attendance category so
someone can browse attendance sheets specifically.

### Analytics
Expose: workers today, workers this week, labour cost today, labour cost by
trade, labour cost by activity, attendance trends. No advanced analytics in
V1.

### AI context
Attendance must be searchable through the assistant — *"how many workers were
on site yesterday?"* should be answerable. This mirrors the existing material
inventory query workflow and should reuse that pattern rather than inventing a
new one.

---

## 6. Future UX ideas

Not commitments — captured so they are not lost.

- **Activity cost roll-up.** Once `Materials → Activity → Labour → Expenses`
  all link to the same activity, a single screen could show the true cost of
  "slab casting" across all three. This is the main reason attendance carries
  an optional activity link in V1 (principle P7).
- **Attendance calendar** — month view, heat-mapped by headcount.
- **Missing-attendance nudge** — flag sites with no attendance recorded on a
  working day.
- **Contractor view** — labour grouped by contractor, once contractor is a
  proper entity (open question Q2).
- **Photo-to-register assist** — suggest promoting temporary workers who keep
  reappearing, rather than requiring someone to notice.

---

## 7. Dependencies on the WhatsApp implementation

The dashboard cannot begin until these exist:

1. Workforce register and attendance tables (Phase 4)
2. Repository read paths (Phase 5)
3. Attendance actually being recorded end to end (Phase 6) — otherwise every
   screen is empty and unverifiable
4. Attachment/gallery wiring (Phase 7)

**Sequencing note:** build the read APIs (§3) *before* any UI. They are needed
by the assistant's own query workflow anyway, so they are not dashboard-only
work and can land during Phase 7.

---

## 8. Explicitly out of scope for this document

Payroll screens, salary generation, leave management, overtime, PF/ESI,
shift scheduling, GPS or biometric attendance, performance management,
approval workflows.

If any of these are requested later they are separate modules with their own
plans — not extensions of this one.
