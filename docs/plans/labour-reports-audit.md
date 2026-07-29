# Labour Reports — Fabrication Audit & Backend Design

**Linear:** STA-168
**Phase:** 1 of 6 — audit and design only, no implementation
**Date:** 2026-07-29
**Status:** complete, awaiting approval to begin Phase 2

> **Purpose.** Every fabricated number in the Labour module, located and named,
> before any of it is changed. Plus the backend report structure that replaces
> it. Nothing in this document has been implemented.

---

## 1. The rule being applied

Attendance records are the single source of truth. Every report, worker
statistic and labour cost is derived from:

- `labour_attendance_reports`
- `labour_attendance_lines`
- `workforce_workers` — **metadata only** (name, trade, type, status). Never
  for cost.

If a value cannot be computed from actual attendance, it is not displayed.

---

## 2. Fabrication inventory

Twenty-one findings across five pages, graded by what a viewer would wrongly
believe.

### 2.1 Severity A — invented money and man-days

These produce specific rupee and headcount figures with no basis in recorded
attendance.

| # | Where | What it does |
|---|---|---|
| A1 | `api.ts:1284` `trade_breakdown` | `(w.default_daily_wage \|\| 800) * 10` — assumes ₹800/day when the wage is unknown, and that every worker worked exactly **10 days** |
| A2 | `api.ts:1293` `trade_breakdown` | `headcount: data.count * 10` — man-days invented from the same 10-day assumption |
| A3 | `api.ts:1305` `subcontractor_ledger` | same `\|\| 800` and `* 10` against contractor groupings |
| A4 | `api.ts:1314` `subcontractor_ledger` | same invented man-days |
| A5 | `api.ts:1342` `worker_wages` | `(w.default_daily_wage \|\| 800) * 30` — a full 30-day month asserted for **everyone on the register**, including workers who have never appeared in a single attendance report |
| A6 | `api.ts:1341` `worker_wages` | `avg_daily_wage: w.default_daily_wage \|\| 800` — the ₹800 default again |
| A7 | `api.ts:1274` | `avgWageRate` falls back to `800` when there is no attendance at all |
| A8 | `api.ts:1340` `worker_wages` | `headcount: 1` hardcoded per worker — every person counts as exactly one man-day regardless of attendance |

**Only `daily_attendance` (`api.ts:1321`) reads real recorded attendance.**
Three of the four reports never touch `labour_attendance_lines`.

### 2.2 Severity B — fabricated visual reassurance

Hardcoded rising sparklines and unconditional "up" arrows. Every one of these
is a fixed array; none reflects any data. `KpiCard` (`components/ui/kpi-card.tsx`)
declares both `trend` and `chartData` **optional**, so all of these can simply
be dropped.

| # | Where | What it does |
|---|---|---|
| B1 | `LabourReportsPage.tsx:171` | `chartData={[25, 40, 55, 70, 85, 100]}` |
| B2 | `LabourOverviewPage.tsx:205` | `chartData={[15, 25, 35, 50, 65, 85]}` |
| B3 | `WorkersPage.tsx:264` | `chartData={[10, 20, 30, 45, 60, 80]}` |
| B4 | `AttendancePage.tsx:241` | `chartData={[20, 35, 50, 65, 80, 95]}` |
| B5 | `WhatsAppLabourPage.tsx:164` | `chartData={[15, 20, 35, 40, 60, 75]}` |
| B6 | 5 pages, 11 cards | `trend="up"` hardcoded — a green upward arrow that never once consults a prior period |

### 2.3 Severity C — misleading claims and mislabelled sources

| # | Where | What it does |
|---|---|---|
| C1 | `LabourReportsPage.tsx:359` | "Certified Executive Labour Statement • Audit Verified by Mesiri AI Platform" — printed over invented figures |
| C2 | `LabourReportsPage.tsx:362-364` | "Prepared by: Site Auditor" / "Approved by: CFO / Project Director" — signoff lines for people who signed nothing |
| C3 | `LabourOverviewPage.tsx:111` | `whatsappRate` defaults to **100%** when there are zero reports — an empty system claims perfect automation |
| C4 | `LabourOverviewPage.tsx:116` | "Trade Skill Distribution" donut counts **registered workers**, not attendance — it shows the roster, not who worked |
| C5 | `LabourOverviewPage.tsx:150` | "Subcontractor Agencies" counts register rows per contractor, not attendance |
| C6 | `WorkersPage.tsx:284` | "Average Daily Wage" averages the register's baseline wages, not what was actually paid |

### 2.4 Severity D — silent caps and dead controls

| # | Where | What it does |
|---|---|---|
| D1 | `LabourReportsPage.tsx:52,70` | The date dropdown (`datePreset`) is **decorative** — never passed to the query and absent from `loadStatement`'s dependency array. "Today" and "This Month" change nothing |
| D2 | `api.ts:1265-1266` | Silently caps at 100 reports and 200 workers. Past that, totals are wrong with no warning |
| D3 | `LabourOverviewPage.tsx:82,84` | Same caps on the Overview page |
| D4 | `AttendancePage.tsx:89` | No `limit` passed → backend default of 50. The KPI totals on that page sum **only the first 50 reports** |

---

## 3. What is already correct — do not "fix" these

- **`AttendancePage`'s date filter works** (`AttendancePage.tsx:79-87`) and is
  the reference implementation for Phase 4. Note it sets `date_from` only, and
  its "This Week" means *the last 7 days*, not the current week.
- **`_line_totals`** (`repositories/workforce.py:86`) is Decimal-exact and
  handles missing wages correctly. Its docstring records a real bug: float
  accumulation once produced `12740.720000000001`, rendered as a 17-digit
  number.
- **Superseded-report exclusion** (`repositories/workforce.py:233`) is correct
  and load-bearing. See trap 1 below.
- **The Overview trend chart** (`LabourOverviewPage.tsx:124-145`) uses real
  attendance and already carries a fix for a "Last 7 Days" bug that plotted the
  seven *oldest* days.

---

## 4. Temporary workers — already persisted, no extension needed

The business rule asked whether temporary workers are stored with attendance.
**They are.** `labour_execution.py:131-145` writes `worker_name`, `trade`,
`daily_wage`, `contractor` and `headcount` onto every line regardless of
whether `worker_id` resolved. A temporary worker is a line with
`worker_id = NULL` and a `worker_name` set.

**Consequence for Phase 3:** aggregating worker statistics by `worker_id` alone
would silently drop every temporary worker — 30–60% of construction attendance
per the module plan's principle P3. Statistics must group by
`COALESCE(worker_id::text, lower(trim(worker_name)))` so temporary workers get
history too. Headcount-group lines (`worker_name IS NULL`, `headcount > 1`)
have no identity and are excluded from per-worker statistics while still
counting toward every cost and man-day total.

---

## 5. Excel attendance does not exist

The Phase 6 checklist lists "✓ Excel Attendance" as existing functionality to
regression-test. **There is no Excel import in the codebase** — a repo-wide
search for `xlsx`, `openpyxl`, `spreadsheet` and `.xls` returns nothing in
application code, tests or dependencies. It was researched and never built,
pending a real sample sheet.

Phase 6 will verify the other seven paths and report this one as not-applicable
rather than silently ticking it.

---

## 6. Backend design (for Phase 2 — not implemented)

### 6.1 Reference

`GET /finance/reports/statement` (`domains/finance/router.py:479`) is the
architectural model: one endpoint, a `report_type` switch, aggregation in the
repository, and a page that only renders. Labour mirrors this.

**One divergence, deliberate.** The Finance endpoint scopes by
`organization_id` only. Labour's router already has `_resolve_project_ids` and
`_site_filter_denied` (`domains/workforce/router.py:60`, `:82`) and every other
Labour read uses them. The new endpoint uses them too. Mirroring Finance here
would import a scoping bug.

### 6.2 Shape

```
GET /labour/reports/statement
    ?report_type=trade_breakdown|subcontractor_ledger|daily_attendance|worker_wages
    &project_id= &site_id= &date_from= &date_to=

  router (scope + validation)
      └── PostgresWorkforceReadRepository.aggregate_attendance(group_by=...)
              └── SQL over labour_attendance_lines ⋈ labour_attendance_reports
```

| `report_type` | Grouped by | One row is |
|---|---|---|
| `trade_breakdown` | `lines.trade` | a trade: real man-days, real cost |
| `subcontractor_ledger` | `lines.contractor` | a contractor; NULL → "Direct (no contractor)" |
| `daily_attendance` | `reports.occurred_date` | a day |
| `worker_wages` | `COALESCE(worker_id, worker_name)` | a person **who actually worked** |

Per group: man-days `SUM(headcount)`, cost `SUM(headcount × daily_wage)`,
average daily wage `cost ÷ man-days`, and the percentage each row contributes.

### 6.3 Business rules encoded

- **Days Worked** = count of *distinct* `occurred_date` values on which the
  worker appears. Never 10, never 30, never estimated.
- **Cost** = `headcount × daily_wage` **from the attendance line**, never from
  the worker's current wage. History stays historically accurate.
- **A missing wage skips the line's cost** rather than counting as zero, so a
  partly-priced report understates cost instead of dragging the average to
  nothing — matching `_line_totals`.
- **Both worker types included.** Permanent and temporary, per §4.

### 6.4 Traps

1. **Superseded reports must be excluded.** When a supervisor forgets someone
   and re-sends the day's list, that correctly creates a second immutable row.
   Counting both previously made 18 workers read as 34 man-days with cost
   inflated to match. The rule lives in `list_reports`; the new aggregation
   must apply the same exclusion. **This is the most likely way to get Phase 2
   wrong.**
2. **Decimal, never float.** See `_line_totals`' docstring.
3. **Do not create a fifth implementation of "total".** Four already exist:
   `repositories/workforce.py:86`, `workflows/labour_update/nodes.py:519`,
   `commands/labour.py:160-164`, and `domains/workforce/router.py:600`. They
   have already disagreed with each other in production. Phase 2 aggregates in
   SQL for sets too large to load, and must produce results identical to
   `_line_totals` for any set small enough to check both ways — this is a
   required test.
4. **Do not reintroduce a row cap.**

### 6.5 Phase 3 reuse

`worker_wages` yields days-worked, first-seen, last-seen and attendance-count
per worker as a by-product. Phase 3 consumes the same repository method rather
than adding a second one.

---

## 7. Phase 1 outcome

No production code changed. Findings: **21 fabrications** — 8 inventing money
or man-days, 6 fabricating visual trends, 6 making misleading claims, 4 silent
caps or dead controls (D-items overlap the count where a page has both).

Two findings that change the plan: temporary workers need no schema work
(§4), and Excel attendance cannot be regression-tested because it does not
exist (§5).
