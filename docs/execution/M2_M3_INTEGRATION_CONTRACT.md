# M2 → M3 Integration Contract

**Status:** DRAFT (M3 consumer view)
**Producer:** Alan (M2) — owns `NormalizedMessage.v1`
**Consumer:** Ilan (M3) — owns `UnderstandingResult.v1`
**Last Updated:** 2026-07-04

This document records exactly what M3 (Understanding) requires from M2's
`NormalizedMessage` output. It is written from the consumer side against the M0
shape documented in `02_ownership_and_boundaries.md` §28. The authoritative
schema is Alan's to author in `mesiri_contracts.assistant.normalized_message`.

## What M3 consumes

M3 reads a `NormalizedMessage` and requires the following. The M3-side reading
model is `understanding.inbound.NormalizedMessageRef` (lenient: `extra="ignore"`,
so additive M2 fields never break M3).

| Field | Type | Required | M3 use |
|---|---|---|---|
| `message_id` | str | **yes** | `UnderstandingResult.source_message_id`; telemetry |
| `external_message_id` | str | no | provenance / dedup cross-reference |
| `correlation_id` | str | **yes** | propagated unchanged to `UnderstandingResult.correlation_id` and all provider calls/logs |
| `causation_id` | str | no | causal chain (not required by M3) |
| `timestamp` | ISO-8601 str | no | ordering / telemetry |
| `modality` | enum `text\|voice\|image\|document\|interactive\|unknown` | **yes** | routing to text/voice/image path |
| `text` | str | for text/interactive | direct extraction input |
| `media.object_key` | str | for voice/image/document | object-storage key read via the M0 `ObjectStoragePort` |
| `media.mime_type` | str | recommended for media | vision MIME hint |
| `media.size_bytes` / `duration_seconds` | number | no | telemetry / guards |
| `interactive_response.{reply_id,title}` | str | for interactive | text derived from `title` |
| `reply_context.{replied_to_message_id,replied_to_text}` | str | no | future context resolution (not used in M3 foundation) |

## Guarantees

**Alan (producer) guarantees** — schema-valid `NormalizedMessage`, correct
modality, correct external identity, correct media references, correct
interactive/reply data, deduplication done upstream, and a present
`correlation_id`.

**Ilan (consumer) guarantees** — accepts every valid `NormalizedMessage`
fixture; no dependence on raw WhatsApp payloads; correct modality routing;
provider failures handled and observable; schema-valid `UnderstandingResult`;
`correlation_id` propagated unchanged.

## Media handoff

M3 never receives inline bytes. It resolves `media.object_key` through the M0
`ObjectStoragePort` (fake locally, R2 in production). M2 is responsible for
ingesting the media and producing a stable `object_key` before M3 runs. **This
is the main behavior M3 cannot yet exercise against real M2** — see the gap doc.

## Correlation

One `correlation_id` per journey, minted at ingress (M2) and propagated by M3
into every provider call, log line, and the output contract. M3 never mints a
new one for an inbound message.

## Shared fixtures

`scenarios/contracts/m2_to_m3/{valid,invalid}/` — created by M3 for now. When M2
lands, its contract tests must emit data that validates against the same
`valid/` fixtures, and M3's harness (`tests/contract/test_m2_m3_harness.py`)
must accept M2-produced messages with no transformation glue.

## Open decisions (from the master plan, before INT-001)

- [ ] Freeze `NormalizedMessage.v1` (Alan) and replace `NormalizedMessageRef`
      with a direct import.
- [ ] Approve `UnderstandingResult.v1` (Ilan).
- [ ] Approve media handoff mechanism (object-key contract).
- [ ] Approve correlation-ID behavior.
- [ ] Commit shared M2→M3 fixtures jointly.
