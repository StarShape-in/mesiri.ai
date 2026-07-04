# M2 → M3 Integration Gaps

**Status:** OPEN
**Raised by:** Ilan (M3)
**Owner of resolution:** shared (producer = Alan, consumer = Ilan)
**Last Updated:** 2026-07-04

Requirements M3 depends on that are not yet available from M2. Per the parallel
development rule, M3 does **not** modify M2 code to close these — it documents
them, defines the expected interface, and proceeds against fakes/fixtures.

---

## GAP-001 — `NormalizedMessage.v1` not authored in code

- **Missing capability:** `mesiri_contracts.assistant.normalized_message` is an
  empty stub. M0 defined the shape in docs only (`02_ownership_and_boundaries.md`
  §28); there is no importable schema.
- **Why M3 needs it:** M3 must validate inbound messages and its fixtures against
  the authoritative contract.
- **M3 interim solution:** `understanding.inbound.NormalizedMessageRef`, a lenient
  consumer-side reading model, plus fixtures in `scenarios/contracts/m2_to_m3/`.
- **Backward-compatible resolution:** Alan authors `NormalizedMessage.v1`. M3
  replaces the reading model with a direct import; the reading model is lenient,
  so additive M2 fields will not break M3.
- **Blocks M3 integration?** No (foundation). **Blocks INT-001 gate?** Yes — the
  contract must be frozen before the real integration run.
- **Owner:** Alan (author), Ilan (switch consumer import).

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
