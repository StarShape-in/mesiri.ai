# Materials Catalogue, Units-of-Measure & Movement Ledger — Plan

**Status:** In progress — Ilan landed the backend migrations (`0290`/`0300`/`0310`, including follow-up self-heal fixes for real production data gaps), `backend/src/mesiri/domains/materials/posting.py`, the WhatsApp-side `runtime/material_catalog_query.py` wired into `inbound_journey.py`'s resolution gate, and the dashboard's `manage-catalogue-dialog.tsx`, all on 2026-07-12 — same day this plan was written. Verify the full flow end-to-end (backend tests, a live WhatsApp conversation against an ambiguous material, and the dashboard catalogue dialog) before considering this done; the design below may already be slightly ahead of or behind what actually shipped, since it landed concurrently with this doc.
**Author:** Ilan (shared with Alan 2026-07-12).
**Supersedes:** the stopgap unit-alias handling landed in commit `1ad7977` (`_UNIT_ALIASES` dicts in `canonicalization/builder.py` and `runtime/inventory_query.py`) — those are explicitly meant to be retired once this lands, not kept alongside it. Check whether commit `1ad7977`'s two dicts have actually been removed yet as part of cleanup.

Before extending this further (e.g. the unit-conversion question below), re-read this in full and confirm open decisions with the user first (per `AGENTS.md`'s "Explain Before Executing" and "Module Placement Log" rules).

---

## Context

Material inflow/outflow entries accept free-text `material_name`/`unit` today. `materials_catalog` exists but is silently auto-populated (`get_or_create_by_name`), so near-duplicate rows accumulate. There is no units-of-measure table. Stock is computed ad hoc as `SUM(receipts) − SUM(usage)` grouped by raw `(material_name, unit)` strings, with no audit trail of individual stock-affecting events.

Goal: make the materials catalogue and a fixed units-of-measure list the only valid source of truth for what can be entered, across all three write paths (dashboard, WhatsApp, direct API). Unmatched/ambiguous input is rejected and the system asks a clarifying question (reusing the WhatsApp project-picker pattern), never silently guesses or auto-creates. Introduce an immutable `material_movements` ledger as the single source of stock truth, so future procurement/issue workflows can post into the same ledger without redesigning stock.

Ship as **one coordinated release** across backend, WhatsApp assistant, and dashboard — not split across separate deploys.

---

## Verified current state (as of 2026-07-12)

- Alembic head: `0280`. New migrations start at `0290`.
- Idempotency: only the WhatsApp CQRS path has it (`idempotency_keys` table, claim via `INSERT ... ON CONFLICT DO NOTHING`). The REST path (`domains/materials/router.py`) has none.
- No unit-of-work abstraction anywhere. CQRS path opens one transaction in `application/materials/handlers.py`. REST path relies on an ambient per-request connection.
- Only two write paths create `material_receipts`/`material_usage` rows: `router.py` and `material_execution.py`.
- `material_receipts`/`material_usage` already behave as an append-only ledger (migration `0270` adds reversal-by-offsetting-row, never UPDATE/DELETE) — `material_movements` should follow the same convention. **Re-read `0270`'s exact reversal mechanics (sign flip vs opposite type) before implementing movement reversal.**
- Dashboard nav already has a top-level `Materials` entry (`/materials`); no catalogue-admin view exists yet.

---

## Design summary

1. **Three-table split**: `materials_catalog`/`material_receipts`/`material_usage` stay as operational records (one row per reported event). `material_movements` becomes the only source of stock truth — insert-only, corrections via `reversal_of_movement_id` offsetting rows, never UPDATE/DELETE.
2. **`material_movements` schema** (new): `id`, `organization_id`, `project_id`/`site_id` (nullable, mirror current nullability), `material_id` (NOT NULL), `unit_id` (NOT NULL), `movement_type` (`RECEIPT`|`ISSUE`, Python constant tuple not a DB CHECK — matches existing convention), `quantity` (always positive), `occurred_at`, `source_type`/`source_id` (polymorphic pointer, no FK), `recorded_by_user_id`, `reversal_of_movement_id`, `idempotency_key`, `created_at`. No procurement-specific columns.
3. **Canonical posting function**: `backend/src/mesiri/domains/materials/posting.py: post_material_movement(conn, ...)`. Both write paths (REST + CQRS) call it on the same connection already used for the receipt/usage insert, so both inserts are atomic by construction.
4. **Idempotency**: CQRS path already protected. REST path gets a `UNIQUE(source_type, source_id, movement_type)` constraint as the minimum viable guard (V1) — full request-level idempotency for REST is an accepted, explicitly out-of-scope gap for now.
5. **DB-backed units + aliases** (new `units_of_measure` + `unit_aliases` tables): seed from the canonical set already in `1ad7977`'s `_UNIT_ALIASES` (`bags`, `kg`, `tons`, `litres`, `pieces`, `rolls`, `boxes`) plus any additional codes confirmed with the user. No unit *conversion* in the original version of this plan — aliases only resolve spelling variants of the same unit.
6. **One Stock Unit per material (V1)**: `materials_catalog.default_unit_id` becomes NOT NULL and is the material's enforced unit. Mismatches are rejected/clarified, not silently coerced. Changing it after movements exist is blocked at the application layer. No multi-unit-per-material, no conversion — deferred.
7. **WhatsApp resolution flow**: material resolution (0 matches → picker, >1 matches → picker over ambiguous set, e.g. "cement" → OPC vs PPC) → unit validation against the resolved material's Stock Unit (alias-normalize, mismatch → single accept/cancel clarifying question naming the correct unit, never a global unit picker) → existing project gate → confirmation (low-stock warning preserved) → execution (same canonical `post_material_movement`).
8. **Dashboard**: no new top-level nav item — a `Manage Catalogue` action inside the existing `/materials` page, gated to ADMIN role, following the `Projects.tsx`/`project-dialogs.tsx` dialog pattern. Entry-form material field becomes a searchable combobox (new `components/ui/combobox.tsx`, `cmdk` + Radix `Popover`); unit field becomes the existing `Select` wrapper.
9. **Procurement boundary**: documented only (comments on `material_movements`, no code) — future `Goods Receipt`/`Material Issue Document` sources post into the same ledger via the same function with a new `source_type`, no schema change. Materials/Stock must never depend on Procurement.

### Migration order

A (`0290`, units+aliases) → B (`0300`, movements ledger + historical backfill) → C (manual stock-parity verification against staging, not an automatic migration gate) → D (coordinated application changes, all three repos together) → E (cutover: stock queries switch to reading `material_movements`) → F (cleanup: remove the two hardcoded `_UNIT_ALIASES` dicts, the read-time merge, `get_or_create_by_name`) → G (`0310`, enforce NOT NULL + unique constraints).

### Open decisions requiring explicit confirmation before implementation

- `0270`'s exact reversal semantics — must be re-read and confirmed, this plan currently assumes without verifying.
- Full REST-path idempotency (client-supplied key) — deferred by default; confirm if the user wants it in V1 instead.
- Stock-parity verification: manual triage vs. automatic hard-abort — plan recommends manual (avoid blocking deploys on pre-existing bad data); confirm tolerance is acceptable.
- Exact final seed list for `units_of_measure` beyond `bags`/`kg`/`tons`/`litres`/`pieces`/`rolls`/`boxes` (candidates: `cum`, `mt`, `nos`, `sqft`).
- **Unit conversion (raised 2026-07-12, not in Ilan's original scope):** the user separately asked whether the units system should also support converting between units of the *same physical dimension* (e.g. feet ↔ centimetres for length) — store as reported, but answer "how many feet is that?" by calculating from a stored canonical/base unit. See discussion in project memory / chat history 2026-07-12. Recommendation if pursued: add a `dimension` (length/weight/volume/count) and `to_base_factor` column to `units_of_measure`, restricted to same-dimension conversions with a fixed, unambiguous ratio. Do **not** extend this to cross-dimension, material-specific conversions (e.g. "50 kg of cement = how many bags") without an explicit, admin-configured, material-specific factor — that's a different, riskier problem (depends on bag weight, which varies) and should not be bundled into pure unit conversion. Needs to be folded into this plan's schema design (§5/§6 above) before Phase 1 migrations are written, since it changes the `units_of_measure` shape.

---

## Critical files

`backend/migrations/versions/0280_*.py` (current head) · `0270_material_add_reason_notes_reversal.py` (reversal precedent) · `backend/src/mesiri/infrastructure/postgres/repositories/material_execution.py` · `materials.py` (`get_stock_levels`, catalogue repo) · `backend/src/mesiri/domains/materials/router.py` · `backend/src/mesiri/application/materials/{handlers,mapper}.py` · `backend/src/mesiri/domains/materials/posting.py` (new) · `apps/whatsapp-assistant/src/runtime/inbound_journey.py`, `canonicalization/builder.py`, `runtime/inventory_query.py`, `workflows/material/nodes.py` · `apps/whatsapp-assistant/src/interactions/pending_report.py` (pattern to generalize) · `apps/dashboard/src/pages/MaterialsPage.tsx`, `apps/dashboard/src/components/materials/` · `apps/dashboard/src/lib/materials.ts`

## Verification (once implemented)

- Backend: `pytest backend/tests/unit/test_material_*.py backend/tests/contract/test_materials_api_contract.py` plus new movement-ledger/idempotency/parity tests; run migrations against a scratch DB seeded with messy historic data to confirm abort-on-unmapped behavior.
- WhatsApp: existing `inbound_journey`/`canonicalization` suite plus new gate-sequencing and stock-unit-mismatch tests; manually drive a staging conversation against a catalogue with OPC + PPC cement to confirm the picker fires correctly.
- Dashboard: verify `Manage Catalogue` only shows for ADMIN, exercise create/edit including the Stock Unit lock-after-movements behavior, confirm entry forms reject free text.
