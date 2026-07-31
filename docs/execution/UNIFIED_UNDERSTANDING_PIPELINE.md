# Unified Understanding Pipeline — Design Doc

**Status:** Proposed, no code written (2026-07-31). Supersedes the *trigger*
design in [`COMPOSITE_REQUEST_PLAN_LAYER.md`](COMPOSITE_REQUEST_PLAN_LAYER.md) §9
and completes the *unification* that its §7 stated but never executed.
**Owner:** Ilan Usman
**Started:** 2026-07-31
**Last updated:** 2026-07-31
**Linear:** _(epic to be created — see §8)_

> **Resuming in a new session?** Read §2 first — it is the finding that
> motivates everything else. Then §4 (the target architecture), §5 (the
> decisions and what was rejected), and §8 (phases, in order — Phase A is
> deliberately risk-free and lands first).

> **Purpose of this document.** Durable memory for this change. If a future
> session — human or AI — loses all conversational context, this file alone
> should explain what is wrong today, what replaces it, why, in what order,
> and what evidence must exist before each phase merges.

---

## 1. The trace that started this

A real Malayalam voice message, 2026-07-31:

> ഒരു പുതിയ പ്രോജക്ട് ആഡ് ആക്ക് ബിദിലാജ് എന്നുള്ള പേരുള്ള ഒരു പ്രോജക്ട്
> എന്നിട്ട് പിന്നെ സൈറ്റ് എ എന്നുള്ള ഒരു സൈറ്റും ക്രിയേറ്റ് ചെയ്യ് പിന്നെ
> ഞാൻ ഒരു ഉസ്മാൻ എന്നുള്ള പേരിലുള്ള ഒരു എഞ്ചിനീയറിങ് സൈറ്റ് എഞ്ചിനീയറിങ്
> ആഡ് ആക്കണം അവന്റെ WhatsApp നമ്പർ ഞാൻ കുറച്ചു കഴിഞ്ഞ് അയച്ചു തരുന്നുണ്ട്

Translated by the pipeline itself:

> Add a new project, a project named Bidilaj, and then create a site called
> Site A. Then I need to add an engineer, a site engineer, named Usman. I
> will send his WhatsApp number a little later.

Transcription and translation are **correct**. What the pipeline then produced:

| Field | Value |
|---|---|
| `semantic_type` | `add_project_member` |
| `overall_confidence` | `high` |
| extracted fields | `member_name: Usman` |

Three requests in, one out. The project and the site are gone — not deferred,
not reported, not surfaced anywhere. And because `project_id` is unresolved
(Bidilaj does not exist), the message ends at
[`_run_project_gate`](../../apps/whatsapp-assistant/src/runtime/inbound_journey/seeding.py)
asking *"Which project is this for?"* over a list that **cannot contain
Bidilaj**, since creating it was one of the dropped intents.

The reply is not just wrong, it is confusingly wrong: it asks the user to
choose from the world as it was before the message they just sent.

### 1.1 Why the existing decomposition layer did not catch it

[`decomposed_plan.py`](../../apps/whatsapp-assistant/src/runtime/inbound_journey/decomposed_plan.py)
runs **only** when the primary extraction returns `semantic_type == unknown`
(its own module docstring states this as settled by trace evidence). Here
extraction returned `add_project_member` at `high` confidence, so the entire
composite-request layer — decomposition, entity-linking, ordering, the plan
preview, all of it — was never invoked.

**The gate is `unknown`. The signal needed is "is this several requests?".
Those are different questions, and they are not correlated.** A model can be
confidently wrong about arity. This one was.

### 1.2 The two traces — why the `unknown` gate is not salvageable

`COMPOSITE_REQUEST_PLAN_LAYER.md` §9 chose the `unknown` gate on
**2026-07-30, on the strength of a real trace**, and explicitly weighed and
rejected `intents[]` at that time. That decision was sound given the evidence
it had. One day later there are two traces, and they are nearly the same
message:

| | Trace A (2026-07-30) | Trace B (2026-07-31) |
|---|---|---|
| Language | Malayalam voice | Malayalam voice |
| Intents stated | 3 (project → site → user) | 3 (project → site → member) |
| Deferred field | "I'll send his number" | "I will send his WhatsApp number a little later" |
| `semantic_type` | **`unknown`** | **`add_project_member`** |
| `overall_confidence` | `high` | `high` |
| Decomposition ran? | **yes** — gate matched | **no** — gate missed |
| Outcome | 3-step plan, preview shown | 1 intent, project picker without Bidilaj |

Two structurally identical requests; opposite classifications; opposite
outcomes. §9's premise — *"for exactly the messages that need decomposing,
`semantic_type` carries no signal at all"* — is disproved by Trace B, where
it carried a confident and wrong signal.

**This is the fact that changes the decision.** The gate is not mistuned; it
is measuring a variable (was the model unsure?) that is independent of the
one that matters (how many requests are there?). §9's own reasoning that the
gate is "near-free" holds only if multi-intent reliably implies `unknown`,
and it does not. ADR-U1 reverses §9's choice on this evidence, not on
preference.

---

## 2. Root cause, and the larger finding

### 2.1 The schema makes the truth unrepresentable

```python
class ExtractionResult(BaseModel):
    semantic_type: str = "unknown"          # <- exactly one, always
    fields: dict[str, Any] = ...
```

There is **no value** `semantic_type` can hold that correctly describes the
Malayalam message. The model was asked "what is the intent of this text" and
answered honestly and confidently about one of the three it found. `high`
confidence is not a malfunction — it is a correct statement that
`add_project_member` really is in there.

This reframes the whole problem:

> The bug is not that decomposition is gated wrongly. The bug is that arity
> is decided by a field that cannot express it, and decomposition is a
> rescue path bolted on to catch the cases where that failure happened to
> coincide with low confidence.

No trigger heuristic fixes this, because every heuristic is a filter over a
signal (`unknown`, or lexical cues like *"then" / പിന്നെ / എന്നിട്ട്*) that
is a proxy for arity rather than a measurement of it. Tuning the proxy
trades false negatives for false positives forever.

### 2.2 Three mechanisms answer "how many things is this message?"

Auditing outward from the trace, the codebase answers that question in three
separate places, at three different stages, with three different vocabularies:

| # | Mechanism | Answer it can give | Fed by | Live? |
|---|---|---|---|---|
| 1 | `ExtractionResult.semantic_type` | "exactly 1", always | the extract call | yes |
| 2 | [`build_canonical_events`](../../apps/whatsapp-assistant/src/canonicalization/builder.py) → [`workflows/batch.py`](../../apps/whatsapp-assistant/src/workflows/batch.py) + `PendingBatchStore` | "1 or 2" — the deterministic `work_item` expansion only | canonicalization | **yes** — wired at [`process.py:482`](../../apps/whatsapp-assistant/src/runtime/inbound_journey/process.py) / [`dependencies.py:666`](../../apps/whatsapp-assistant/src/runtime/dependencies.py) |
| 3 | `decompose()` → `planning/` + `PlanStore` + `plan_executor` | "N" | a **second** LLM call, gated on `unknown` | yes, since 2026-07-30 |

Mechanisms **2 and 3 are two live orchestrators**. Both sequence several
`CanonicalEventV2`s with a confirmation between each. They do not share:

| | `workflows/batch.py` | `planning/` + `plan_executor.py` |
|---|---|---|
| Store | `PendingBatchStore` (30-min TTL) | `PlanStore` (own TTL) |
| Advance path | `interactions/handler.py:281` | `plan_executor.advance_plan` |
| Reply formatting | `format_batch_prefix`, `summarize_batch_outcome` | `format_plan_summary`, `render_plan_preview` |
| Failure semantics | flat FIFO — **no dependency notion** | transitive-dependent cancellation (ADR-C4) |
| Ordering | authored order | topological sort over registry `provides`/`requires` |

### 2.3 This was designed, then not executed

To be accurate about prior intent: `COMPOSITE_REQUEST_PLAN_LAYER.md` §7
already says —

> `PendingBatchStore` generalizes into `PlanStore` (same Redis key shape,
> same TTL reasoning, same pop-once discipline). `batch.py`'s formatting
> functions largely survive.

— and §3's **P5** states *"One plan, one executor… the principle that keeps
this layer and the entity-resolution layer from becoming two systems."*

So the unification was designed. Phase 4 then built `PlanStore` **alongside**
`PendingBatchStore` rather than replacing it, and §14's risk row
*"~~Two orchestrators~~ — **Closed**"* recorded the closure against the
entity-resolution layer only, which made the still-open batch duplication
invisible in the one table meant to surface it.

**Correction to that doc:** the "two orchestrators" risk is **not closed**.
It is closed for entity-resolution and open for `batch.py`. §9 of this doc
records the amendment.

---

## 3. Principles

- **U1 — Arity is measured once, at the one stage that reads the whole
  message.** Not inferred later, not rescued after a failure.
- **U2 — `n = 1` is the common case of the general path, never a separate
  path.** The moment single-intent has its own pipeline, the two drift, and
  every gate must be written twice (which is exactly what happened).
- **U3 — One plan, one executor.** Inherited verbatim from
  `COMPOSITE_REQUEST_PLAN_LAYER.md` P5. This doc finishes enforcing it.
- **U4 — Composing intents and competing interpretations are different
  axes.** `candidates` (existing) are rival readings of the same request;
  `intents` (new) are distinct requests that must all happen. Conflating
  them would be unrecoverable — see ADR-U3.
- **U5 — The 95% path may not regress to fix the 5% path.** Single-intent
  accuracy is the gate on Phase B, enforced by the existing golden suite
  (§7), not by inspection.
- **U6 — Every stage deleted must have its behaviour preserved or its loss
  stated.** No silent capability drops during unification.

---

## 4. Target architecture

```
NormalizedMessage
      │
      ▼
  EXTRACT ─────────────► intents: [i₁ … iₙ]        n ≥ 1, one LLM call
      │                                            (arity measured HERE, once)
      ▼
  CANONICALIZE ────────► events:  [e₁ … eₙ]        + deterministic work_item
      │                                              expansion (unchanged)
      ▼
  LINK ────────────────► StepRefs                  no-op when n = 1
      │
      ▼
  PLAN ────────────────► Plan(n steps)             n = 1 is the common case
      │
      ▼
  GATES per step ──────► project / site / material / stock
      │                                            structural, not per-path
      ▼
  CONFIRM ─────────────► n = 1: today's single confirmation (unchanged UX)
      │                  n > 1: §8 whole-plan preview (Yes / No / Edit)
      ▼
  EXECUTE ─────────────► plan_executor              ONE executor
```

Four structural changes, in dependency order:

1. **`ExtractionResult.intents: list[ExtractedIntent]`** — arity becomes
   representable. `semantic_type` survives as a derived property
   (`intents[0].semantic_type`) through the migration window.
2. **`build_canonical_events` becomes genuinely plural** — one
   `CanonicalEventV2` per intent, *plus* the existing deterministic
   `work_item` → `ACTIVITY_CONTINUATION` expansion, which is a real derived
   segment and stays. `build_canonical_event` (singular) becomes a thin
   `events[0]` shim.
3. **Everything becomes a `Plan`.** `process.py` stops branching between
   single / batch / decomposed. `workflows/batch.py` and `batch_store.py`
   are deleted; their callers repoint at `plan_executor`.
4. **Gates run per step by construction** — because there is only one path
   through which a step can reach execution.

### 4.1 What this fixes that today's design cannot

| Symptom | Today | After |
|---|---|---|
| Confident-but-multi message (the trace) | silently truncated to 1 intent | n intents, all planned |
| Gates skipped for decomposed segments | patched for project/site on 2026-07-30; material/stock still open | structural — one path, gates run once, for every step |
| Two orchestrators | live, divergent failure semantics | one |
| A dropped required field (Usman's number) | segment silently vanishes from the plan | still open — see §10, but now in **one** place to fix rather than three |

### 4.2 The deferred-field interaction (still open after this change)

The same trace states *"I will send his WhatsApp number a little later."*
`CREATE_USER_REQUESTED` requires `whatsapp_number`
([`mapping.py:188`](../../apps/whatsapp-assistant/src/canonicalization/mapping.py)),
so that intent canonicalizes to `CLARIFICATION_REQUIRED` and
`build_plan_from_segments` drops it — the known V1 gap already documented in
`test_decomposed_plan.py::test_a_deferred_required_field_drops_the_segment_from_the_plan`.

This unification **does not fix that**, and must not be described as if it
does. What it changes is that after Phase A there is exactly one place where
the fix belongs (the preview's "I couldn't include X yet — also send me Y"
line), instead of three paths that would each need it.

---

## 5. Decisions

### ADR-U1 — Merge arity into extraction; do not add a segmentation stage

**Decision.** Extraction returns `intents: list[...]`. There is no separate
segmentation call.

**This reverses `COMPOSITE_REQUEST_PLAN_LAYER.md` §9**, which weighed this
exact option on 2026-07-30 and chose the gated separate decomposer instead.
That choice was correct on its evidence; §1.2 here is the new evidence that
invalidates its premise. Note that §9's stated reason for rejecting
`intents[]` — *"regresses single-intent accuracy on every existing path"* —
was **right**, and is not dismissed: it is now the governing risk of Phase B
and the entire subject of §7's merge gate.

**Why.** The model already reads the entire message in the extract call.
Asking *"list every distinct request you see"* instead of *"what is the
request"* is the same call, same tokens, same latency, same cost. A separate
pre-pass would add one LLM round trip to **every** message — including the
~95% that are single-intent — to recover information the extract call
already had and was structurally prevented from returning.

**Rejected alternative: unconditional segmentation stage before extraction.**
Keeps the extraction prompt untouched (its only real advantage — zero
regression risk on the 95% path), but pays a permanent latency and cost tax
on every message, and creates split-brain: two models independently
reasoning about boundaries, where a segmenter saying "2" and an extractor
confidently classifying segment 1 as something spanning both is
unresolvable. Reconsider only if §7's golden-suite gate proves
un-passable — that is the one outcome that would make the tax worth paying.

**Rejected alternative: keep `decompose()` as a second opinion.** The
argument for keeping it is robustness — one bad call loses everything. But
that is already true today: one bad extraction call already loses everything,
which is precisely this trace. A stage that only runs after a failure cannot
improve a case where the failure was silent and confident.

### ADR-U2 — `n = 1` produces a Plan too

**Decision.** Every message produces a `Plan`, including single-intent ones.
The `n = 1` path differs only in **presentation** (today's single
confirmation, not the whole-plan preview) — a branch on `len(plan.steps)`
at the reply layer, not a separate pipeline.

**Why.** U2. The gate gap fixed on 2026-07-30 existed *because* single-intent
and decomposed were separate paths, so gates written for one never ran in
the other. Fixing that by re-adding gates to the second path (what was done
on 2026-07-30, for project/site only) treats the symptom. Collapsing the
paths removes the class of bug.

**Cost, stated plainly.** Every single-intent message now allocates a `Plan`
and a `PlanStore` write it did not before. This is one extra Redis
round trip on the hot path — measured, not assumed, before Phase A merges
(§7).

### ADR-U3 — `intents` is a new axis, not a reuse of `candidates`

**Decision.** Add `intents`. Do **not** overload `candidates`.

**Why.** `UnderstandingResult.candidates: list[Candidate]` already exists and
is already a list — the tempting shortcut. But
[`_select_candidate`](../../apps/whatsapp-assistant/src/canonicalization/builder.py)
picks the single candidate matching `understanding.semantic_type`, because
candidates are **rival interpretations** of one request (ambiguity — see
`planner/ambiguity.py`). Intents are **co-occurring** requests, all of which
must execute. Overloading one list to mean both would make "did the user ask
for two things, or might they have meant one of two things?" unanswerable,
and `planner/ambiguity.py` would silently start treating separate requests
as competing readings. Two axes, two fields.

### ADR-U4 — `workflows/batch.py` is deleted, not extended

**Decision.** Delete `batch.py` + `batch_store.py`. Preserve their
formatting behaviour by porting it into the plan reply layer.

**Why.** U3/P5, and §2.3 — this is what §7 of the prior doc already
prescribed. `batch.py`'s flat FIFO has no dependency notion, so keeping it
would mean the material→activity case permanently runs under weaker failure
semantics than every other multi-step case.

**Non-negotiable preservation.** The material→activity batch is the only
multi-segment case that works in production today. Its behaviour is the
regression anchor (§7) — it must be byte-identical in reply text before and
after, which the prior doc's §13 also demanded.

---

## 6. Contract changes

### 6.1 `ExtractionResult` (platform/ai — internal model)

```python
class ExtractedIntent(BaseModel):
    """One distinct request found in a message. Composing, not competing
    (see ADR-U3)."""
    semantic_type: str = "unknown"
    fields: dict[str, Any] = Field(default_factory=dict)
    unknown_fields: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    field_confidences: dict[str, float] = Field(default_factory=dict)
    source_span: str | None = None          # the sub-text this came from
    warnings: list[str] = Field(default_factory=list)


class ExtractionResult(BaseModel):
    intents: list[ExtractedIntent] = Field(default_factory=list)

    # --- migration shims: derived, removed at the end of Phase B ---
    @property
    def semantic_type(self) -> str:
        return self.intents[0].semantic_type if self.intents else "unknown"

    @property
    def fields(self) -> dict[str, Any]:
        return self.intents[0].fields if self.intents else {}
    # (unknown_fields / missing_fields / field_confidences likewise)

    # unchanged, message-level not intent-level:
    detected_language: str | None = None
    transcript: str | None = None
    translated_text: str | None = None
    provider: str | None = None
    model: str | None = None
    latency_ms: float | None = None
```

**Normalization invariant** (mirrors `DecompositionResult._normalize`'s
instinct, which is the one piece of the deleted layer worth keeping):
an empty `intents` list normalizes to a single `unknown` intent, so
"no intents" is never representable downstream.

### 6.2 `UnderstandingResult` (shared/contracts — the M3 output contract)

Same shape: add `intents: list[Candidate]`, keep `semantic_type` and
`candidates` as derived properties through the migration. `model_config =
{"extra": "forbid"}` means this is a **versioned contract change** —
`CONTRACT_VERSION` stays `v1` only if the derived properties keep every
existing consumer valid; otherwise it goes to `v2` and
`M2_M3_INTEGRATION_CONTRACT.md` needs the corresponding row.

### 6.3 Blast radius (measured 2026-07-31)

| | Count |
|---|---|
| `.semantic_type` read sites, non-test | **15**, across **6** files |
| …of which are the real structural consumer | `canonicalization/builder.py` (5), `planner/ambiguity.py` (2) |
| …of which are set-sites | `understanding/pipeline.py` (4) |
| …of which are display/logging only | `understanding/runtime.py`, `process.py:331`, `scripts/verify_m2_m3_direct.py` |
| `decompose()` implementations to delete | 5 files (2 adapters, port, resolver, fakes) |

### 6.4 Code deleted

| File | LOC |
|---|---|
| `workflows/batch.py` | 161 |
| `workflows/batch_store.py` | 151 |
| `runtime/inbound_journey/decomposed_plan.py` | 377 |
| `runtime/inbound_journey/pending_decomposition.py` | 116 |
| `planning/decomposition.py` (the `decompose`-fed half) | 219 |
| `mesiri_ai/ports/decomposition.py` | 31 |
| **Total** | **~1,055** |

Plus the `decompose()` method in both provider adapters, the resolver, and
the fakes.

**Note for the record:** `decomposed_plan.py` and `pending_decomposition.py`
were written on 2026-07-30 (commit `333dfa1`, hours before this doc). They
are deleted here because they exist to rescue a schema that Phase B fixes at
the root. What survives from that work is everything underneath it —
`PlanStore`, `plan_executor`, `planning/ordering.py`, `planning/binding.py`,
`planning/outputs.py`, `planning/preview.py`, and the gate *logic* — which
becomes the single path rather than the second one.

---

## 7. Regression strategy — the gate on Phase B

**Decision (2026-07-31): the existing golden/scenario suite is the merge
gate.** The intents-plural prompt does not merge until every existing golden
and scenario test is green, unmodified.

Rationale and its limit, stated honestly: this directly measures "did
single-intent accuracy degrade" against cases already written down, and it
costs nothing to run. It does **not** cover message shapes nobody has
written a test for — a real-traffic replay set would, and remains the
stronger option if the golden suite proves too thin once the prompt changes
land (§10).

Concretely, before Phase B merges:

1. **Full monorepo suite green** — currently 2,633 passed / 16 skipped.
2. **Golden + scenario suites green with no test edits.** A test that needs
   editing to pass is a regression until proven otherwise, in writing, in
   this doc.
3. **The material→activity batch reply text is byte-identical** pre/post
   (ADR-U4's non-negotiable).
4. **Over-splitting probe**: a fixture set of deliberately-single-intent
   messages that a list-shaped prompt is most likely to wrongly split —
   *"I paid 5000 for cement"* (expense vs. expense+material), *"10 masons
   worked on the slab today"* (labour vs. labour+activity). These are new
   tests, and they are the specific failure mode ADR-U1 accepts risk on.
5. **The Malayalam trace in §1 becomes a scenario fixture** — 3 intents,
   correct order, with the `whatsapp_number` gap surfaced rather than
   silent (§4.2).

Phase A carries no AI-behavior risk and is gated on (1) + (3) only.

---

## 8. Phases

**Sequencing decision (2026-07-31): Phase A first, in full, before Phase B
starts.** The orchestrator unification is pure refactoring with a
deterministic test gate; the schema change is the one with model-behaviour
risk. Landing A first means B changes one prompt into an already-clean
pipeline, so any regression B causes is unambiguously B's.

### Phase A — Unify the orchestrators (no AI behaviour change)

| # | Step | Verification |
|---|---|---|
| A1 | Extend `PlanStore`/`plan_executor` to cover what `PendingBatchStore` does: running outcome log, `(2 of 3)` progress prefix, closing summary. Port `format_batch_prefix` / `summarize_batch_outcome` behaviour into the plan reply layer. | Unit tests on the ported formatters, asserting identical output strings. |
| A2 | Repoint `build_canonical_events`' multi-event output at `build_plan_from_segments` instead of `batch_store.start_batch`. The `work_item` expansion becomes a 2-step Plan. | The material→activity regression anchor, byte-identical. |
| A3 | Repoint `interactions/handler.py:281`'s batch-advance at `plan_executor.advance_plan`. Delete the `batch_store` branch. | Full suite; the single-active invariant (§7.5 of the prior doc) must still hold. |
| A4 | Make `n = 1` produce a Plan. Reply layer branches on `len(plan.steps)`: 1 → today's confirmation, >1 → preview. | Full suite green with **zero** reply-text changes for single-intent messages. |
| A5 | Move the gates so they run per step. Deletes the 2026-07-30 project/site special case in `decomposed_plan.py` and closes the material/stock half structurally. | The gate tests from `test_decomposed_plan.py` re-pointed at the unified path. |
| A6 | Delete `workflows/batch.py`, `workflows/batch_store.py`, and their wiring in `dependencies.py` / `message_journey.py` / `process.py`. | Full suite; grep for orphaned references. |
| A7 | Measure the added `PlanStore` write on the single-intent hot path (ADR-U2's stated cost). | A latency number recorded in this doc, not an assumption. |

### Phase B — Intents-plural extraction

| # | Step | Verification |
|---|---|---|
| B1 | Add `ExtractedIntent` + `intents` to `ExtractionResult` with derived shims (§6.1). No prompt change yet — adapters emit a 1-element list. | Full suite green, entirely unchanged behaviour. |
| B2 | Same for `UnderstandingResult` (§6.2). Decide `v1`-compatible vs `v2` and update `M2_M3_INTEGRATION_CONTRACT.md`. | Contract tests; `extra: forbid` compatibility check. |
| B3 | `build_canonical_events` maps one event per intent. | Existing multi-event test + new n>1 fixtures. |
| B4 | **Change the extraction prompt** in both adapters to return all intents. This is the risk step. | §7's full gate — all five items. |
| B5 | Migrate the 15 read sites off the shims; delete the shims. | Full suite; grep for `.semantic_type`. |
| B6 | Delete `decompose()` everywhere, `decomposed_plan.py`, `pending_decomposition.py`, the port, adapters, fakes, and the `unknown`-gated branch in `process.py`. | Full suite; §6.4's LOC accounting reconciles. |

### Phase C — Deferred, not in scope here

The `whatsapp_number`-arrives-later gap (§4.2) and the whole-plan permission
pre-check (`COMPOSITE_REQUEST_PLAN_LAYER.md` Phase 6, still not started, and
still a confirmed real gap in `plan_executor.py`). Both become
**single-place** fixes after Phase A, which is the main reason to do A first.

---

## 9. Amendments to `COMPOSITE_REQUEST_PLAN_LAYER.md`

Items 1 and 2 were **applied on 2026-07-31**, at the same time as this doc,
because both were statements that had become factually false — leaving them
correct-looking in the older doc is the exact drift that let the duplicate
orchestrator survive unnoticed. Items 3 and 4 are informational.

1. ~~**§14 risk table** — reopen *"Two orchestrators"*.~~ **Applied.** Row now
   reads REOPENED, with the distinction between the entity-resolution
   closure (real) and the `batch.py` duplication (never closed).
2. ~~**§9 (Decomposition)** — mark superseded.~~ **Applied.** §9 now carries a
   supersession banner; its body is kept unchanged as the record of why the
   gate was chosen, since its deferred-required-field analysis is still
   accurate and still open.
3. **§10 phases** — Phase 5 (migrate remaining entity types) and Phase 6
   (permission pre-check) survive unchanged and are unaffected by this doc.
4. **§14** — the *"single-message gates never re-run per decomposed segment"*
   row is closed by Phase A5 **structurally**, superseding the 2026-07-30
   partial closure (project/site only).

---

## 10. Risks

| Risk | Mitigation |
|---|---|
| **Intents-plural prompt degrades single-intent accuracy** | The central risk of ADR-U1, hitting the ~95% path. §7's golden-suite gate plus the over-splitting probe fixtures (§7.4). If the gate cannot be passed, ADR-U1's rejected alternative (separate segmentation stage) is reconsidered — that is the explicit escape hatch. |
| **Golden suite is too thin to detect real degradation** | Acknowledged limit of the chosen gate (§7). Escalation path is the real-traffic replay set, deferred rather than rejected. |
| **Deleting `batch.py` loses the one working multi-segment behaviour** | ADR-U4's byte-identical reply-text anchor, verified at A2 before deletion at A6 — deletion is the *last* step, not the first. |
| **Every single-intent message pays a `PlanStore` write** | Measured at A7 and recorded. If material, the reply layer can defer persistence until `n > 1` — but that reintroduces a branch, so it needs its own decision, not a silent optimization. |
| **`UnderstandingResult` is a cross-team versioned contract (`extra: forbid`)** | B2 makes the `v1`-vs-`v2` call explicitly and updates `M2_M3_INTEGRATION_CONTRACT.md`; required reviewer per that contract's header is Alan. |
| **Concurrent sessions in this repo** | The entity-resolution layer is actively developed in parallel (`ENTITY_RESOLUTION_PLAN.md`). Phase A touches `process.py`, `dependencies.py`, `message_journey.py`, `interactions/handler.py` — all shared. Fetch before staging, stage only own files, never `git add -A`. |
| **Phase B stalls half-migrated** | The derived shims (§6.1) mean B1–B3 are independently shippable and behaviour-neutral; only B4 changes behaviour, and B5/B6 are cleanup. A stall leaves a working system with dead shims, not a broken one. |

---

## 11. Open questions

- **Does `source_span` on `ExtractedIntent` earn its place?** It would let
  the preview quote the user's own words per step ("*create a site called
  Site A*" → `Create site Site A`), which is a real UX gain for a 5-step
  plan. But it is another thing the model must get right. Decide at B4.
- **Does the over-splitting probe belong in `scenarios/` or `tests/unit/`?**
  It is a model-behaviour assertion, so it may need the `provider` marker
  and real credentials — in which case it cannot be the merge gate it is
  described as in §7.4. **Resolve before B4.**
- **What happens to `planner/ambiguity.py` when `n > 1`?** Ambiguity is
  per-intent (ADR-U3), so a 3-intent message could produce 3 independent
  ambiguity resolutions. Today's UX has no shape for that. Probably: resolve
  ambiguity per step at bind time (ADR-C2's just-in-time principle already
  applies), but this is unexamined.
- **Plan TTL** — inherited open question from the prior doc's §12, now more
  pressing since *every* message becomes a plan.

---

*Last updated: 2026-07-31 — proposed, no code written. Phase A is the next
action; it is gated on §7 items (1) and (3) only.*
