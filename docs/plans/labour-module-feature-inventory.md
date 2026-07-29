# Labour Module — Complete Feature Inventory

**Date:** 2026-07-29
**Commit audited:** `8c2fd68`
**Purpose:** factual baseline of what exists. No design, no proposals except
in §12 (Missing Features), which lists gaps without solving them.

> Everything below was read from the code at the commit above. Where a claim
> could not be verified, it says so. Nothing is inferred from documentation,
> Linear, or commit messages.

---

## 1. Screens

Six routes under `/labour`, all registered in `App.tsx:112-119` and in the
sidebar (`app-sidebar.tsx:106-115`).

### 1.1 Overview — `/labour/overview`

`LabourOverviewPage.tsx` (490 lines). Command-centre landing page.

| Feature | Backend | Data source | Limitation |
|---|---|---|---|
| 4 KPI cards | 🟡 | Attendance + register | Capped at 100 reports / 200 workers |
| Headcount & cost trend (bar chart) | ✅ | Attendance reports | Only the fetched window |
| Trade distribution (donut) | 🟡 | **Worker register**, not attendance | Shows roster composition, labelled as trade distribution |
| Subcontractor agencies list | 🟡 | **Worker register**, not attendance | Counts registered workers per contractor, not who worked |
| Recent attendance table (5 rows) | ✅ | Attendance reports | — |
| Attendance detail drill-in | ✅ | `GET /labour/attendance/{id}` | — |
| Register Worker dialog | ✅ | `POST /labour/workers` | — |

Fabrications present: hardcoded sparkline `[15,25,35,50,65,85]` (line 205);
`trend="up"` on three cards; `whatsappRate` defaults to **100%** when there
are zero reports (line 111).

### 1.2 Attendance — `/labour/attendance`

`AttendancePage.tsx` (544 lines). The attendance log.

| Feature | Backend | Data source | Limitation |
|---|---|---|---|
| List attendance reports | ✅ | `GET /labour/attendance` | No `limit` passed → backend default **50** |
| Date filter (All/Today/This Week/This Month) | ✅ | Sends `date_from` | Works. "This week" = last 7 days |
| Source filter (WhatsApp/Web) | 🟡 | Client-side over fetched page | Filters only the 50 loaded |
| Search | 🟡 | Client-side | Same |
| Sorting (date/via/lines) | 🟡 | Client-side | Same |
| Pagination | 🟡 | Client-side | Same |
| CSV export | 🟡 | Client-side | Exports only loaded rows |
| Detail sheet | ✅ | `GET /labour/attendance/{id}` | — |
| 4 KPI cards | 🟡 | Attendance | **Totals only the first 50 reports** |

Fabrications: hardcoded sparkline (line 241); `trend="up"` on two cards.

### 1.3 Workers Roster — `/labour/workers`

`WorkersPage.tsx` (614 lines). The register.

| Feature | Backend | Data source | Limitation |
|---|---|---|---|
| List workers | ✅ | `GET /labour/workers` | — |
| Search | ✅ | Server-side (`search` param) | — |
| Status filter (active/inactive) | ✅ | Server-side | — |
| Type filter (permanent/temporary/contractor) | 🟡 | Client-side | Filters loaded page only |
| Sorting (name/trade/type/wage/status) | 🟡 | Client-side | Same |
| Pagination | 🟡 | Client-side | Same |
| Add worker | ✅ | `POST /labour/workers` | — |
| Edit worker | ✅ | `PATCH /labour/workers/{id}` | — |
| Bulk activate/deactivate | ✅ | Repeated `PATCH` calls | No bulk endpoint; N requests |
| Delete worker | 🔴 | — | **Not supported by design** — retire (INACTIVE) instead |
| Worker history columns | 🔴 | — | API exists (Phase 3); no column renders it |

Fabrications: hardcoded sparkline (line 264); `trend="up"` on two cards;
"Average Daily Wage" KPI averages **register baseline wages**, not amounts
actually paid.

### 1.4 Reports — `/labour/reports`

`LabourReportsPage.tsx` (371 lines).

| Feature | Backend | Data source | Limitation |
|---|---|---|---|
| 4 report types | ✅ (backend, Phase 2) | **Screen still calls the old browser code** | Backend endpoint exists and is unused |
| KPI cards | 🔴 | Browser arithmetic | Fabricated |
| Search | 🟡 | Client-side | — |
| Date filter | 🔴 | — | **Decorative** — never passed to any query |
| CSV export | 🟡 | Client-side | Exports the fabricated values |
| Print | ✅ | `window.print()` | — |

**This screen is the largest single source of false information in the
module.** Detail in §5.

### 1.5 WhatsApp Automations — `/labour/whatsapp`

`WhatsAppLabourPage.tsx` (319 lines).

| Feature | Backend | Data source | Limitation |
|---|---|---|---|
| 5 settings toggles | 🟡 | `GET/PATCH /labour/settings` | Save and reload correctly, **change no behaviour** |
| Sandbox simulate dialog | ✅ | `POST /labour/whatsapp/sandbox/simulate` | Dry run, no DB writes |
| 4 KPI cards | 🟡 | Attendance | Hardcoded sparkline (line 164) |

### 1.6 Settings — `/labour/settings`

`LabourSettingsPage.tsx` (271 lines). Same five settings as 1.5, duplicated on
a second screen. Both read and write the same `labour_settings` key.

**No admin/hidden Labour pages exist.** No Analytics screen exists — analytics
widgets live inside Overview (§7).

---

## 2. Attendance Flow

| Stage | Status | Evidence |
|---|---|---|
| **Text attendance** | ✅ | `recorded_via="whatsapp_text"` |
| **Voice attendance** | ✅ | Transcribed upstream; `recorded_via="whatsapp_voice"`; test asserts voice/image/text produce identical structure |
| **Image attendance** | ✅ | `recorded_via="whatsapp_image"`; image-purpose picker has an Attendance row |
| **OCR** | ✅ | Not a separate path — the vision model reads the sheet in the same extraction step |
| **Worker matching** | ✅ (simplified) | Exact name **AND** exact trade, or no match. Asks nothing |
| **Preview before save** | ✅ | `request_confirmation` node |
| **Explicit confirmation** | ✅ | Nothing persists without it |
| **Name corrections pre-confirm** | ✅ | `NAME_CORRECTIONS_FIELD`, several per message |
| **Promotion flow** | ✅ | Post-attendance offer; `all`/`none`/names; duplicate check before creating |
| **Temporary workers** | ✅ | Line with `worker_name`, `worker_id` NULL |
| **Permanent workers** | ✅ | Line carries `worker_id` |
| **Headcount groups** | ✅ | Line with `headcount > 1`, no name |
| **Team photo** | 🟡 | Offered and stored as `attendance_team_photo`; **object storage on `fake` adapter, so links are dead** |
| **Attendance corrections (post-confirm)** | 🔴 | See below |
| **Duplicate handling** | 🔴 | See below |
| **Historical reports** | ✅ | Append-only, immutable |

### 2.1 Duplicate handling and corrections — the significant finding

The schema and the read path both support superseding a report. **Nothing
writes it.**

- `corrects_report_id` exists in migration `0371` and is read by
  `_superseded_report_ids()` to exclude corrected reports from every total.
- The `INSERT` in `labour_execution.py:106-119` **does not include the
  column.** It is always NULL.
- `find_existing_report_for_day()` exists in the repository and is **called by
  nothing** outside it (verified by repo-wide search).

**Consequence:** a supervisor who re-sends a day's attendance creates a second
independent live report. Both count. The "18 workers reading as 34 man-days"
behaviour is still live in production today, because the guard that prevents
it can never trigger.

The read-side exclusion is correct and will work the moment a writer exists.
The writer does not exist.

There is also **no post-confirmation correction path for attendance.** The
generic `runtime.correct()` mechanism operates on *pending drafts*; once
attendance is confirmed there is no supported way to change it.

---

## 3. Worker Register

| Capability | Status | Notes |
|---|---|---|
| Add worker | ✅ | Dashboard and WhatsApp promotion |
| Edit worker | ✅ | Name, trade, type, wage, contractor, status |
| Delete worker | 🔴 | Deliberate — attendance references workers; retire to INACTIVE |
| Permanent / Temporary / Contractor types | ✅ | Three types, validated |
| Active / Inactive status | ✅ | Validated |
| Search | ✅ | Server-side |
| Trade | ✅ | Normalized via `normalize_trade` |
| Contractor | ✅ | Free text |
| Default daily wage | ✅ | Metadata only — never used for reports (correct) |
| **Project assignment** | 🔴 | **No column, no API, no UI.** `workforce_workers` has no `project_id` |
| Duplicate check on promotion | ✅ | Before creating |

---

## 4. Database

| Table | Purpose | Status |
|---|---|---|
| `workforce_workers` | Mutable register | ✅ Live |
| `labour_attendance_reports` | One immutable row per report | ✅ Live |
| `labour_attendance_lines` | Named worker or headcount group | ✅ Live |
| `labour_attendance_attachments` | Sheet/team photos | ✅ Live (storage misconfigured) |
| `labour_attendance` (0120) | Superseded | ⚠️ **Dead** — exists, unused |
| `labour_attendance_entries` (0120) | Superseded | ⚠️ **Dead** — exists, unused |

Migrations: `0120` (dead), `0361` (cascade), `0371` (the real schema), `0454`
(team-photo attachment type).

**Relationships:** reports → organization, project, site; lines → report
(CASCADE), optionally → worker; attachments → report (CASCADE). Attendance
never writes the register in either direction.

**Columns reserved but unused:** `corrects_report_id` (§2.1), `activity` on
lines (written, never read by any feature).

---

## 5. Reports

| Report | Exists | Real data | Fake calc | Backend | Frontend | Export |
|---|---|---|---|---|---|---|
| Trade Summary | ✅ | ✅ backend / 🔴 screen | Screen: `wage or 800 × 10` | ✅ | 🔴 old code | CSV (of fake values) |
| Contractor Summary | ✅ | ✅ backend / 🔴 screen | Same | ✅ | 🔴 old code | Same |
| Daily Attendance | ✅ | ✅ | None | ✅ | 🔴 old code | Same |
| Labour Cost by Worker | ✅ | ✅ backend / 🔴 screen | Screen: `wage or 800 × 30` | ✅ | 🔴 old code | Same |

**The backend engine is built and correct (Phase 2). The screen has not been
switched over (Phase 4).** Until then the page still shows invented figures
under a "Certified Executive Labour Statement • Audit Verified by Mesiri AI
Platform" banner with Prepared-by / Approved-by signoff lines.

PDF export: 🔴 not supported anywhere (print only).

---

## 6. Worker Statistics

All **derived on read** — not stored, not cached. Added Phase 3.

| Statistic | Status | Method |
|---|---|---|
| Days Worked | ✅ | `COUNT(DISTINCT occurred_date)` |
| Attendance Count | ✅ | `COUNT(DISTINCT report_id)` |
| First Seen / Last Seen | ✅ | `MIN`/`MAX(occurred_date)` |
| Total Earnings | ✅ | `SUM(headcount × line wage)` |
| Trade History | ✅ | `array_agg(DISTINCT trade)` |
| Contractor History | ✅ | `array_agg(DISTINCT contractor)` |
| Man-days / priced / unpriced | ✅ | Derived |

**Not surfaced on any screen.** API only.

Known limitation: promotion can split one person's history into two rows
(name-keyed before, id-keyed after), because historical lines keep
`worker_id = NULL`.

---

## 7. Analytics Widgets

| Widget | Screen | Status |
|---|---|---|
| Headcount & cost trend (bar) | Overview | **Real** (windowed) |
| Trade distribution (donut) | Overview | **Real but mislabelled** — register, not attendance |
| Subcontractor agencies | Overview | **Real but mislabelled** — register, not attendance |
| All KPI sparklines (5 pages) | All | **Hardcoded** |
| All `trend="up"` arrows (11 cards) | All | **Hardcoded** |
| WhatsApp automation rate | Overview | **Real, but defaults to 100% at zero data** |
| Average Daily Wage | Workers | **Register baseline, not actual pay** |

No dedicated analytics screen exists.

---

## 8. API Endpoints

All under `/labour`. All enforce organization + project scope except where noted.

| Endpoint | Purpose | Used by | Production ready |
|---|---|---|---|
| `GET /settings` | Read 5 settings | Settings, WhatsApp pages | ✅ (values inert) |
| `PATCH /settings` | Update settings | Same | ✅ (values inert) |
| `GET /workers` | List register | Workers, Overview | ✅ |
| `POST /workers` | Add worker | Add dialog | ✅ |
| `PATCH /workers/{id}` | Edit/retire | Edit sheet, bulk | ✅ |
| `GET /workers/statistics` | All worker history | **Nothing** | 🟡 untested live |
| `GET /workers/{id}/statistics` | One worker's history | **Nothing** | 🟡 untested live |
| `GET /attendance` | List reports | Attendance, Overview | ✅ |
| `GET /attendance/attachments` | Photo gallery | Gallery | 🟡 storage misconfigured |
| `GET /attendance/{id}` | One report + lines | Detail sheet | ✅ |
| `GET /reports/statement` | Aggregated statements | **Nothing** | 🟡 untested live |
| `POST /whatsapp/sandbox/simulate` | Dry-run parse | Sandbox dialog | ✅ |

**No write endpoint for attendance exists by design** — attendance is only
created through a confirmed WhatsApp flow.

Three endpoints are built and wired to nothing (Phase 4 connects two).

---

## 9. Feature Matrix

| Feature | Backend | Frontend | Prod ready | Notes |
|---|---|---|---|---|
| WhatsApp text attendance | ✅ | n/a | 🟡 | Never verified on production |
| Voice attendance | ✅ | n/a | 🟡 | Same |
| Image/OCR attendance | ✅ | n/a | 🟡 | Photo accuracy never tested on real sheets |
| Worker matching | ✅ | n/a | 🟡 | Deliberately simplified |
| Preview + confirmation | ✅ | n/a | ✅ | |
| Name corrections (pre-confirm) | ✅ | n/a | ✅ | |
| Worker promotion | ✅ | n/a | 🟡 | |
| Temporary workers | ✅ | ✅ | ✅ | |
| Team photo | ✅ | ✅ | 🔴 | Storage on `fake` adapter |
| Attendance list/detail | ✅ | ✅ | ✅ | |
| Worker register CRUD | ✅ | ✅ | ✅ | No delete (by design) |
| Report engine | ✅ | 🔴 | 🟡 | Screen not switched over |
| Worker statistics | ✅ | 🔴 | 🟡 | No UI |
| Labour settings | 🟡 | ✅ | 🔴 | Save but do nothing |
| Duplicate/supersede | 🟡 read | 🔴 | 🔴 | **No writer** |
| Post-confirm correction | 🔴 | 🔴 | 🔴 | |
| Project assignment | 🔴 | 🔴 | 🔴 | |
| Excel import | 🔴 | 🔴 | 🔴 | Does not exist |
| PDF export | 🔴 | 🔴 | 🔴 | |

---

## 10. Test Coverage

1764 unit tests pass repo-wide; 13 skipped (all Labour — the retired
"which Ravi?" question machinery). Labour-specific: ~180 unit tests across
matching, canonicalization, workflow nodes, mapper, validation, execution,
supersede, money serialization, reports, statistics.

**19 Labour integration tests exist and have never been executed** — no
Postgres has been reachable in any session. This includes all numeric
verification of Phases 2 and 3.

---

## 11. Production Readiness

**Ready today:** worker register CRUD, attendance list and detail, sandbox
simulate, the confirmation flow.

**Built but unproven:** everything in the WhatsApp capture path (no production
message ever verified), report engine, worker statistics.

**Not ready:** Reports screen, all KPI trend indicators, settings, team
photos, duplicate protection.

---

## 12. Missing Features

Gaps only. No solutions proposed.

### High priority — needed before MVP

1. **Reports screen still shows fabricated money** (Phase 4).
2. **No writer for `corrects_report_id`** — re-sent attendance double-counts.
3. **No duplicate warning** — `find_existing_report_for_day` unused.
4. **Object storage on `fake` adapter** — every photo link dead. Config, not code.
5. **Fabricated KPI trends on 5 screens** (Phase 5).
6. **No production verification** of any WhatsApp path.
7. **Five settings that do nothing** — visible controls with no effect.

### Medium priority

8. Worker statistics have no UI.
9. Promotion splits worker history.
10. Server-side pagination/sort/filter on Workers and Attendance.
11. Attendance KPIs total only the first 50 reports.
12. Trade/contractor analytics read the register, not attendance.
13. No post-confirmation attendance correction.
14. `activity` column written but never read.

### Future (V2+)

15. Excel import (flexible column mapping).
16. Project assignment for workers.
17. PDF export.
18. Bulk worker endpoint.
19. Dead `0120` tables removal.
20. Four separate implementations of "total headcount and cost".

---

## 13. Final Summary

### 13.1 Completeness

| Area | Complete |
|---|---|
| WhatsApp capture (V1 scope) | ~90% |
| Database & data model | ~95% |
| Worker register | ~90% |
| Attendance screens | ~75% |
| Reports | ~50% (backend done, screen not) |
| Worker statistics | ~60% (API done, no UI) |
| Analytics/KPIs | ~30% |
| Settings | ~10% |
| Excel import | 0% |
| **Overall** | **~65%** |

Weighted by code that exists and works, not by user-visible value. By what a
client would *see* working, it is lower — closer to 50%.

### 13.2 Production-ready today

Worker register CRUD, attendance list and detail view, attendance detail
sheet, WhatsApp sandbox. That is the complete list.

### 13.3 Should be finished before 9 August

Items 1–6 in §12. Item 4 is a config change on the server. Item 6 needs a real
phone and cannot be done from a development machine.

### 13.4 Can wait until after MVP

All of Medium and Future priority (items 8–20), except item 9 if promotion is
part of the demo script.

### 13.5 Technical debt to track, not fix now

- Four implementations of the same total (`workforce.py:86`,
  `labour_update/nodes.py:519`, `commands/labour.py:160`,
  `workforce/router.py:600`) — have disagreed in production before.
- Dead `0120` tables.
- Settings duplicated across two screens.
- 13 skipped tests for retired matching machinery.
- Client-side pagination/sort/filter that silently operates on a truncated page.
- `activity` column collected but never surfaced.
