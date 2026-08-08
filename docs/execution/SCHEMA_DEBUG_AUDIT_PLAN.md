# Schema Debug Audit — Fix Plan

**Status:** DRAFT  
**Created:** 2026-07-09  
**Migration head:** `0200`  
**Scope:** Fill the schema gaps found in the prod DB audit so every table supports end-to-end debugging and audit trails.

---

## Gap Summary

| # | Gap | Impact | Tables affected |
|---|-----|--------|-----------------|
| G1 | RBAC tables have no timestamps | Can't audit when roles/permissions were granted or revoked | `roles`, `permissions`, `role_permissions`, `membership_roles`, `project_memberships`, `site_memberships` |
| G2 | `external_identities` has no `created_at` | Can't see when a WhatsApp identity was first linked | `external_identities` |
| G3 | `context_*` tables lack `updated_at` | Can't tell when context layer was last mutated | `context_organizations`, `context_users`, `context_projects`, `context_sites` |
| G4 | No raw inbound message log | To debug a message end-to-end you rely on uvicorn stdout; no DB query path | (new table) |
| G5 | No journey/trace log | Can't reconstruct the pipeline stages (understanding → context → planner → workflow) from DB alone | (new table) |

---

## Plan — Migration `0210`

One migration (`0210_schema_add_audit_columns_and_message_log`) covers all five gaps. Keeping it in a single revision avoids 5 tiny migrations and is safe because every change is additive (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`).

### G1 — Add `created_at` to RBAC junction tables

Add `created_at` (timestamptz, NOT NULL, default `now()`) to:
- `roles`
- `permissions`
- `role_permissions`
- `membership_roles`
- `project_memberships`
- `site_memberships`

All existing rows get `now()` via server_default. Future inserts record the grant time.

**Why not `updated_at`:** These are append-only junction tables — rows are inserted or deleted, never updated. `created_at` alone is sufficient.

### G2 — Add `created_at` to `external_identities`

Same pattern: `created_at` timestamptz NOT NULL default `now()`.

### G3 — Add `updated_at` to `context_*` tables

Add `updated_at` (timestamptz, NOT NULL, default `now()`) to:
- `context_organizations`
- `context_users`
- `context_projects`
- `context_sites`

The identity projection (M6.5) already updates these tables when reconciling canonical UUIDs. The new column will let us see the last reconciliation time. We'll add a trigger to keep `updated_at` in sync on any UPDATE.

**Trigger function** (shared, created once):
```sql
CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END;
$$ LANGUAGE plpgsql;
```

Then `CREATE TRIGGER trg_<table>_updated BEFORE UPDATE ON <table> FOR EACH ROW EXECUTE FUNCTION set_updated_at();` for each context table.

### G4 — New table: `inbound_messages`

Captures every raw inbound WhatsApp message for debugging and replay.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `correlation_id` | varchar, indexed | Thread-through key |
| `sender_wa_id` | varchar, indexed | WhatsApp sender |
| `message_type` | varchar | `text` / `voice` / `image` / `interactive` / `reply` |
| `raw_payload` | jsonb | Full Meta webhook payload |
| `normalized_message` | jsonb | The `NormalizedMessage.v1` produced |
| `body_text` | text, nullable | Convenience: extracted text body |
| `media_object_key` | varchar, nullable | S3/storage key if media |
| `dedup_key` | varchar, indexed, unique | WhatsApp message ID for dedup |
| `received_at` | timestamptz, default now() | When webhook hit us |
| `processed_at` | timestamptz, nullable | When pipeline finished |
| `processing_status` | varchar, default `pending` | `pending` / `completed` / `failed` |
| `error_code` | varchar, nullable | If failed |

**Indexes:** correlation_id, sender_wa_id, dedup_key (unique), (received_at).

**Who writes:** The ingress layer / inbound journey — single INSERT on receipt, UPDATE on completion. This is a debug table, not a domain table — writes are best-effort (never block the pipeline on a log insert failure).

### G5 — New table: `journey_traces`

One row per pipeline stage per message. Lets you reconstruct the full journey from DB alone.

| Column | Type | Notes |
|--------|------|-------|
| `id` | uuid PK | |
| `correlation_id` | varchar, indexed | Links to inbound_messages + workflow_instances |
| `stage` | varchar | `understanding` / `context` / `canonicalization` / `planner` / `workflow` |
| `stage_payload` | jsonb | The v2 contract object at that stage |
| `duration_ms` | integer, nullable | Stage latency |
| `succeeded` | boolean, NOT NULL | |
| `error_code` | varchar, nullable | If failed |
| `error_message` | text, nullable | |
| `created_at` | timestamptz, default now() | |

**Indexes:** correlation_id, (correlation_id, stage).

**Who writes:** `inbound_journey.py` after each pipeline stage — a single INSERT per stage. Best-effort like G4.

---

## Code Changes (beyond migration)

### 1. Context projection — update `updated_at`
- `apps/whatsapp-assistant/src/context/identity_projection.py` — no change needed because the DB trigger handles `updated_at` automatically.

### 2. Inbound message logging
- `apps/whatsapp-assistant/src/runtime/inbound_journey.py` — add optional `MessageLogger` port (new `ports.py` interface). Insert on receipt, update on completion.
- `apps/whatsapp-assistant/src/runtime/dependencies.py` — wire a `PostgresMessageLogger` (real) and keep a `FakeMessageLogger` for tests.
- `apps/whatsapp-assistant/src/workflows/fakes.py` — add fake logger.

### 3. Journey trace logging
- Same `MessageLogger` port gets a `log_trace()` method, or a separate `TraceLogger` port.
- `inbound_journey.py` calls `trace_logger.log()` after each stage (understanding, context, canonicalization, planner, workflow).

### 4. New ports file or additions to existing ports
- `apps/whatsapp-assistant/src/runtime/logging_ports.py` — `MessageLogger` + `TraceLogger` protocols.

### 5. Postgres implementations
- `apps/whatsapp-assistant/src/backend/postgres/message_logger.py` — INSERT/UPDATE inbound_messages.
- `apps/whatsapp-assistant/src/backend/postgres/trace_logger.py` — INSERT journey_traces.

### 6. Tests
- `apps/whatsapp-assistant/tests/unit/test_inbound_message_logging.py` — verify logger called with correct fields.
- `apps/whatsapp-assistant/tests/integration/test_journey_trace.py` — verify trace rows created for each stage.
- `backend/tests/integration/test_migration_0210.py` — verify migration applies cleanly, columns exist, trigger fires.

---

## Execution Order

1. Write migration `0210` + test
2. Add `MessageLogger` / `TraceLogger` ports
3. Add postgres implementations
4. Wire into `inbound_journey.py` + `dependencies.py`
5. Add fakes for tests
6. Update existing tests that assert on journey behavior
7. Run full test suite locally
8. Deploy to prod: `alembic upgrade 0210` + restart
9. Verify with a smoke message — check `inbound_messages` + `journey_traces` rows

---

## Risk Assessment

**Low risk:**
- All schema changes are additive (no column drops, no type changes)
- `ADD COLUMN ... DEFAULT now()` on existing tables is instant for small tables (prod has <100 rows everywhere)
- New tables don't affect existing code paths until the logger is wired in
- Loggers are best-effort — if they fail, the pipeline still works

**Medium risk:**
- Trigger on context tables — needs to be tested to ensure it doesn't break the identity projection's UPDATE queries (it shouldn't; triggers are transparent)
- `inbound_messages.raw_payload` JSONB could get large with media messages — add a note to consider TTL/archival strategy later

**Not in scope:**
- RBAC `updated_at` (junction tables are insert/delete only)
- Log retention/TTL policy (future infra task)
- Structured query UI for traces (future tooling)
