# Parallel Implementation Report — M1 Infrastructure + M3 Foundation

**Author:** Ilan
**Date:** 2026-07-04
**Scope:** M1 (Infrastructure Alive) + independent M3 (Understanding) foundation, in parallel with Alan's M2.

---

## 1. Baseline repository state
Pure scaffold. Every Python file and every `pyproject.toml` (root, `backend`,
`shared/contracts`, `platform/ai`, `apps/whatsapp-assistant`) was **0 bytes**;
`docker-compose.yml` was empty; CI was TypeScript/pnpm only. **M0 existed as
documentation only** — no contract code (`NormalizedMessage.v1`,
`UnderstandingResult.v1`), no error contract, no infra. No Python tests existed,
so there was no test baseline to record. Toolchain: Python 3.10, `uv` 0.5.14,
Docker present.

## 2. Existing architecture discovered
Conceptual layering in `02_ownership_and_boundaries.md` maps onto the repo as:
`services/whatsapp` → `apps/whatsapp-assistant/src/ingress` (Alan/M2);
`services/assistant/**/understanding` → `apps/whatsapp-assistant/src/understanding` (Ilan/M3);
contracts → `shared/contracts` (`mesiri_contracts`); AI gateway → `platform/ai`
(`mesiri_ai`); infrastructure/domain → `backend` (`mesiri`).

## 3. M1 files created (highlights)
- `pyproject.toml` (workspace, pytest pythonpath, ruff/mypy), `Makefile`, `.env.example`, `docker-compose.yml`, `.github/workflows/ci-python.yml`
- Contracts: `mesiri_contracts/common/{errors,result,ids,clock,storage,health}.py`
- `mesiri/bootstrap/{settings,container,lifecycle}.py`
- `mesiri/observability/{logging,tracing,health}.py`
- `mesiri/infrastructure/{errors,objectstorage/{fake,r2},postgres/database,redis/client}.py`
- `mesiri/http/app.py` (+ `backend/apps/api/main.py` entrypoint)
- `backend/alembic.ini`, `backend/migrations/{env.py,script.py.mako,versions/0001_m1_infra_heartbeat.py}`
- `mesiri/scripts/run_m1_golden_scenario.py`
- Scenarios `scenarios/m1/` (001–010) + `backend/tests/integration/test_live_stack.py`

## 4. M1 files modified
Only previously-empty stubs in my ownership + repo root config (`pyproject.toml`,
`docker-compose.yml`, `.gitignore`, `README.md`). No M2 files.

## 5. Infrastructure components implemented
Centralized config with fail-fast prod validation and `SecretStr`; structured
JSON logging with secret/byte redaction; correlation propagation via
`contextvars`; Postgres/Redis/ObjectStorage adapters **each with a real + fake**
implementation behind M0 ports; infra→`MesiriError` mapping; health/readiness
aggregation; ordered lifecycle (startup rollback + best-effort shutdown); FastAPI
`/health/live` + `/health/ready` with correlation middleware; alembic migration
(infra-only).

## 6. M1 scenarios added
`scenario_m1_001..010` — local stack start, per-dependency health, dependency
failure readiness, correlation across dependencies, shared error mapping, clean
shutdown, missing production config, CI without credentials. All with
Given/When/Then/Expected/Forbidden specs.

## 7. M1 golden scenario result
`make m1-golden` (fake mode): **M1 GATE: PASSED** — config validated; Postgres,
Redis, object storage reachable; write+read on each; one `correlation_id`
preserved across all operations; readiness HEALTHY; clean shutdown verified.

## 8. M1 Gate Status: **PASSED** (fake mode, reproducible without docker/credentials)
Caveat: the **live-docker** lane (`MESIRI_GOLDEN_USE_FAKES=false`, real Postgres/
Redis) is implemented and wired into CI but was **not executed locally** — Docker
Desktop's engine is not running in this environment. Real adapters import cleanly
with infra SDKs installed.

## 9. M3 foundation files created
- Contracts: `mesiri_contracts/assistant/{enums,confidence,candidates,understanding_result}.py`
- `mesiri_ai/{models,confidence,fakes,fixtures}.py`
- `mesiri_ai/ports/{speech,vision,extraction}.py`
- `mesiri_ai/core/{errors,fallback}.py`
- `mesiri_ai/adapters/{sarvam/adapter,gemini/adapter}.py`
- `understanding/{inbound,pipeline}.py`
- Tests: `platform/ai/tests/*`, `apps/whatsapp-assistant/tests/{unit,contract}/*`

## 10. Provider interfaces implemented
`SpeechUnderstandingProvider`, `VisionUnderstandingProvider`,
`StructuredExtractionProvider`. Translation is **not** a separate port — Sarvam
returns transcript + translation from one call (no unnecessary abstraction).

## 11. Provider adapters implemented
Sarvam (speech) and Gemini (vision + extraction). SDKs lazily imported and
isolated inside adapters; responses converted to Mesiri-owned models; malformed
output → `PROVIDER_MALFORMED_OUTPUT`; bounded retry + timeout + latency via the
resilience helper. Fakes cover all required fixtures.

## 12. Extraction schemas implemented
`ExpenseCandidate`, `EquipmentUsageCandidate`, `MaterialUpdateCandidate`,
`LabourUpdateCandidate`, `GeneralSiteUpdateCandidate`, `GeneralQuestionCandidate`
— all optional fields with `unknown_fields`/`missing_fields`/`field_confidences`;
values are never fabricated.

## 13. Confidence policy implemented
Deterministic `ConfidencePolicy` → HIGH/MEDIUM/LOW/UNUSABLE from provider
success, schema validity, required/missing fields, ambiguity, and average field
confidence. Pure and independently tested.

## 14. Fake providers and fixtures added
Deterministic fakes + fixtures: Malayalam JCB voice, valid/partial/unreadable
receipt, empty transcript, provider timeout/unavailable, malformed output,
low-confidence. No test calls a paid API.

## 15. M3 foundation tests result
All pass. Covers adapter conversion, resilience/timeout/retry, error mapping,
malformed output, extraction/schema validity, missing-fields-stay-unknown,
confidence policy, correlation propagation, graceful failure handling, and
architecture-boundary scans (no SDK/persistence leakage in understanding).

## 16. M2 → M3 integration requirements
Documented in `M2_M3_INTEGRATION_CONTRACT.md`: required `NormalizedMessage`
fields, media handoff via object-key + M0 `ObjectStoragePort`, correlation
propagation, and the consumer guarantee (accept every valid fixture → schema-valid
`UnderstandingResult` with the inbound correlation_id).

## 17. Integration gaps discovered
`M2_M3_INTEGRATION_GAP.md`: GAP-001 `NormalizedMessage.v1` not authored in code
(M3 uses a lenient reading model + fixtures); GAP-002 real media ingestion /
object-key contract; GAP-003 provider SDK surface unverified. None block the M3
*foundation*; GAP-001/002 block the INT-001 gate.

## 18. Shared files modified
`shared/contracts` — added my own contract files and `common/*`; did **not**
author `assistant/normalized_message.py` (Alan's). `scenarios/contracts/m2_to_m3/`
fixtures created for joint review. Root config files (pyproject/compose/gitignore/
README).

## 19. Potential merge conflicts
Low. M2 ingress files were never touched (verified: still 0 bytes). The only
shared-review surfaces are `shared/contracts` (additive) and the shared fixtures
directory. Recommend Alan reviews `enums.py` (shared `InputModality`) and the
integration contract/fixtures.

## 20. Full test suite result
`63 passed, 3 deselected` (the 3 are docker-gated integration tests) in ~1s.
Ruff clean across all runtime + test code.

## 21. Known limitations
- Live-docker golden + integration lane not executed locally (engine down).
- Provider adapter SDK surfaces are assumed (GAP-003) — verify on pin.
- `NormalizedMessageRef` is a stand-in until `NormalizedMessage.v1` is authored.
- mypy config exists but is not yet a CI gate.

## 22. Next action after Alan merges M2
1. Replace `understanding.inbound.NormalizedMessageRef` with a direct import of
   the frozen `NormalizedMessage.v1`.
2. Point the harness fixtures at M2-produced messages (no glue); confirm they
   still validate against `scenarios/contracts/m2_to_m3/valid/`.
3. Agree the media object-key contract; drop harness media pre-population.
4. Pin `sarvamai` / `google-genai`, run provider-marked tests, adjust adapters.
5. Run INT-001 on `integration/m2-m3` (real Malayalam voice + receipt image).

---

**Status:** M1 GATE PASSED (fake-mode proof) · **M3 FOUNDATION READY FOR M2 INTEGRATION**
