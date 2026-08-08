# M2 → M3 Integration Gaps

**Status:** OPEN
**Raised by:** Ilan (M3)
**Owner of resolution:** shared (producer = Alan, consumer = Ilan)
**Last Updated:** 2026-07-04

Requirements M3 depends on that are not yet available from M2. Per the parallel
development rule, M3 does **not** modify M2 code to close these — it documents
them, defines the expected interface, and proceeds against fakes/fixtures.

---

## GAP-001 — `NormalizedMessage.v1` authored, but SHAPE DIVERGES from M3 expectations ⚠️ RESOLVED→REOPENED

- **Update (post-merge of M2 `c576134`):** Alan has authored
  `mesiri_contracts.assistant.NormalizedMessage`. GAP-001 (missing schema) is
  closed, but the concrete shape does **not** match what M3 assumed. My tests
  still pass because M3 consumes the lenient `NormalizedMessageRef`, not Alan's
  model directly — so this is a **contract-reconciliation** item for INT-001, not
  a code break. Field-by-field deltas (M2 field → M3 expectation):

  | M2 `NormalizedMessage` | M3 `NormalizedMessageRef` | Issue |
  |---|---|---|
  | *(none)* | `correlation_id` (**required**) | **No `correlation_id` on M2 output** — breaks end-to-end traceability + `UnderstandingResult.correlation_id`. Possibly intended in `metadata`? Must be a first-class field. |
  | `content` | `text` | field rename |
  | `message_type` (enum TEXT/IMAGE/VOICE) | `modality` (`InputModality`) | two enums; M2 has no `document`/`interactive`/`unknown` |
  | `media.file_path` + `media_id` | `media.object_key` | **Media handoff mismatch** — M2 exposes a local file path; M3/Object-Storage Boundary expects an object-storage key resolved via `ObjectStoragePort`. See GAP-002. |
  | `reply_to` (str) | `reply_context` (obj) | shape difference |
  | `sender`, `channel`, `metadata`, `timestamp: datetime` | (ignored / partial) | additive — fine (reading model is lenient) |

- **Backward-compatible resolution (needs Contract Change Request, both owners):**
  add `correlation_id` to `NormalizedMessage`; agree media as an object-storage
  key (GAP-002); align enum/field names OR keep an explicit, reviewed mapping in
  M3's reading model (not silent glue).
- **Blocks M3 foundation?** No. **Blocks INT-001 gate?** **Yes.**
- **Owner:** shared (Alan = producer contract, Ilan = consumer).

## GAP-001b — Workspace Python baseline + test layout (resolved during merge)

- **Found on merge:** M2 requires Python **3.11** (`datetime.UTC`); my workspace
  was pinned to 3.10. M2 tests also import `from tests.conftest ...` (authored to
  run from the app dir).
- **Resolution applied:** root `requires-python`/ruff/mypy bumped to 3.11; venv
  recreated on 3.11; `apps/whatsapp-assistant` added to the root pytest
  `pythonpath` so the whole monorepo suite runs in one pass. **77 tests pass.**
- No M2 files were edited.

---

## GAP-002 — Real media ingestion / object-key contract

- **Missing capability:** M2 media ingestion (download from WhatsApp → store →
  produce `media.object_key`) is not yet available. M3 reads media via the M0
  `ObjectStoragePort` using that key.
- **Why M3 needs it:** voice/image paths fetch bytes by `object_key`.
- **M3 interim solution:** fixtures reference synthetic `object_key`s; the harness
  pre-populates the fake object store. Provider outputs use deterministic fixtures.
- **Backward-compatible resolution:** agree the `object_key` naming/lifetime
  contract; M2 writes media through the same `ObjectStoragePort`. No M3 change
  expected beyond removing test pre-population.
- **Blocks M3 integration?** No (foundation). **Blocks INT-001 gate?** Yes — the
  live voice/image proof needs real media.
- **Owner:** Alan (ingestion), shared (object-key contract).

---

## GAP-003 — SDK surface for Sarvam / Gemini unverified

- **Missing capability:** no provider SDK was pinned in the repo, so the adapter
  method/field names in `mesiri_ai.adapters.{sarvam,gemini}` are **assumed**.
- **Why it matters:** live provider calls may need adjustment to the installed
  SDK versions.
- **M3 interim solution:** SDKs imported lazily; all tests use fakes; adapters are
  structurally isolated so only the adapter files change when the SDK is pinned.
- **Resolution:** pin `sarvamai` / `google-genai`, run provider-marked tests
  against sandbox keys, adjust the two adapter files if needed.
- **Blocks M3 integration?** No. **Blocks M3 live-evaluation gate?** Yes.
- **Owner:** Ilan.
