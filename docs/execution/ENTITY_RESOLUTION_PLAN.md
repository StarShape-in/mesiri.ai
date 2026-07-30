# Entity Resolution & Workflow Chaining

> **Status:** proposed (design only — no code written)
> **Author:** drafted 2026-07-30
> **Module Placement Log row:** see `AGENTS.md`

---

## 1. The problem, stated by a real message

A project manager sent, in Malayalam:

> ഹോസ്പിറ്റൽ പ്രോജക്റ്റിലെ ഹൈസം എന്നുള്ള ഒരു പ്രൊജക്ട് മാനേജർ ആയിട്ട് ഒന്ന് ആഡ് ആക്കൂ
> *("add Hysam to the hospital project as a project manager")*

They confirmed the draft with **Yes**, and got:

```
⚠️ Couldn't record this: couldn't find an active user named Hysam
```

Three separate failures are visible in that one reply:

1. **It is a dead end.** The assistant knows a user is missing and knows how to
   create one (`WorkflowKey.CREATE_USER` shipped the same day), but the two
   facts never meet.
2. **It fails *after* confirmation.** The name is resolved at execution time
   (`application/projects/handlers.py:173`), so the user confirms a draft that
   was never capable of succeeding. "Yes" → "actually, no."
3. **It can never succeed by retrying.** `find_by_full_name_active`
   (`repositories/users.py:42`) is a case-insensitive *exact* match. ഹൈസം
   transliterates as Hysam / Hisham / Haisam / Haitham. If the person exists as
   "Hisham", every retry fails identically, forever.

The obvious fix — "if the user is missing, offer to create one" — is a fourth
bug waiting to happen. It hard-codes one pair of workflows and does nothing for
the next pair.

---

## 2. Why this is not one bug

The same shape — *resolve a named thing; it isn't there; now what?* — is
implemented independently across the codebase:

| Layer | Count | Examples |
|---|---|---|
| Backend resolvers | ~8 modules | `materials/resolution.py`, `expenses/resolution.py`, `finance/resolution.py`, `finance/petty_cash_resolution.py`, `automations/name_resolution.py`, `projects/name_resolution.py`, `progress/resolution.py` |
| Assistant gates | 4 | `_run_material_unit_gates`, `_run_project_gate`, `_run_site_gate`, `_run_stock_gate` |
| Hold/resume paths | 7 | `resume_pending_report_with_{project,material,unit,site,material_create,material_unit_choice,stock_choice}` |
| Seed functions | 15 | `_seed_account_candidates`, `_seed_petty_cash_recipient`, `_seed_worker_candidates`, … |

**The duplication is already documented in the code itself.** Read the module
docstrings in order:

- `projects/name_resolution.py` — *"mirroring `application/automations/name_resolution.py`'s AudienceNameResolver shape almost exactly"*
- `automations/name_resolution.py` — *"mirroring `application/finance/resolution.py`'s AccountLookupResolver shape and reusing the exact lookup"*
- `finance/resolution.py` — *"mirrors `application/expenses/resolution.py`"*
- `expenses/resolution.py` — *"mirrors `application/materials/resolution.py`"*
- `progress/resolution.py` — *"mirroring `application/materials/resolution.py`"*

A copy-chain five deep, each link acknowledged in writing. Nobody did anything
wrong; there was simply never a shared abstraction to reach for, so each new
entity type honestly copied the nearest neighbour.

### 2.1 The good behaviour already exists — once

Materials are the exception. An unknown material on a usage report does **not**
hard-reject; it offers to create the material and then *resumes the original
report* (`resume_pending_report_with_material_create`). "50 bags cement for slab
work" already works the way the whole product should.

Every other entity type hard-rejects instead — and
`application/finance/resolution.py` elevates that to a stated principle:
*"hard rejection, never a silent default."*

That principle is right about **never silently guessing** and wrong about
**stopping there**. Refusing to invent a value is correct. Refusing to offer the
user a way forward is what makes the assistant feel like a bot.

**The design goal of this plan is to make the material behaviour the default for
every entity type, rather than a special case someone wrote once.**

---

## 3. Design

Three pieces. The third is what distinguishes this from an `if/else`.

### 3.1 One resolution outcome

Every "find the thing the user named" becomes one call with three outcomes:

```
resolve(entity_type, name_hint, scope) →
    Resolved(id)             → carry on, unchanged
    Ambiguous([candidates])  → picker: "Did you mean Hisham?"
    Missing                  → this thing does not exist yet
```

`Ambiguous` is where the transliteration problem is solved — **once**, for every
entity type, instead of eight times. ഹൈസം → Hysam is a near-miss on Hisham, not
an absence. Prior art to lift: `domains/workforce/matching.py`'s `match_worker`,
already doing fuzzy person-matching for labour attendance.

### 3.2 The registry declares the graph

`workflows/registry.py` is already the single source of truth for workflow
metadata (it gained the user-facing copy fields on 2026-07-30). Two more
declarations:

```python
provides: frozenset[EntityType]   # CREATE_USER          -> {USER}
requires: frozenset[EntityType]   # ADD_PROJECT_MEMBER   -> {USER, PROJECT}
```

Both are `frozenset`, matching `allowed_roles: frozenset[str]` on the same
dataclass. `provides` is a set rather than a single value even though every
workflow today provides at most one entity — a workflow that creates a user
*and* their petty-cash account is plausible, and widening a field later is more
disruptive than starting wide.

These two fields are shared with the Composite Request Plan layer, which reads
the same table forwards while this layer reads it backwards (see §9).

Then *"a USER is missing — what now?"* is a **lookup**, not a branch:

```python
provider = workflow_that_provides(EntityType.USER)   # → CREATE_USER
```

This is the whole point. No module contains the sentence "if the user is
missing, run create-user." A new entity type declares itself and is wired in;
nothing else changes. Workflows come to know about each other through the
registry rather than through hand-written pairings.

### 3.3 One hold-and-resume continuation

> Workflow **W** blocked needing entity **E** → run the workflow that provides
> **E** → substitute the new id → **resume W where it left off.**

This is what stops it feeling like a bot. Not "✅ user created" followed by the
user retyping their original request — it finishes the job they actually asked
for:

```
"add Hysam to the hospital project as PM"
  → USER "Hysam" unresolved; nearest active user is "Hisham"
  → "Did you mean Hisham?"  [Hisham] [Someone else]
  → [Someone else] → "Create a new user, Hysam?"  [Yes] [Skip]
  → [Yes] → "What's their WhatsApp number?" → 9198765xxxxx → created
  → …and Hysam is added to the hospital project as PM. Done.
```

**The substrate already exists.** `PendingReportStore` holds one
`CanonicalEventV2` per user (pop-once, 10-minute TTL), and `_plan_and_run` is
already shared by all seven resume functions. The generalisation is small:
hold the event *plus* which entity is missing and which field to patch, then
re-run `_plan_and_run` after the provider workflow succeeds. That is exactly
what `resume_pending_report_with_material_create` does today, minus the
hard-coding of "material".

---

## 4. Decisions

**ADR-E1 — Resolution moves before the draft, not after.**
Today the name is resolved at execution time, so the user confirms a doomed
draft. Resolution belongs in the gate phase, before a confirmation prompt is
ever shown. Workflow nodes cannot do I/O (`workflows/runtime.py`), so this runs
as a seeding/gate step, the same place the material and project gates already
run.

**ADR-E2 — Backend resolvers stay as defence in depth.**
This plan does not delete the backend `*resolution.py` modules. They are
explicitly documented as defence-in-depth guards for the REST path, which has no
assistant gate in front of it. They stop being the *primary* mechanism for chat,
and their rejection messages stop being user-facing copy — but a command that
reaches a Handler unresolved must still be rejected, not silently defaulted.

**ADR-E3 — Depth 1 only in V1.**
`PendingReportStore` holds exactly one pending event per user. A chain where
creating a user itself requires creating something else would need a stack. V1
resolves one missing entity per request; a second missing prerequisite inside
the provider workflow is a plain error. Revisit only with a real case.

**ADR-E4 — `Missing` always offers, never auto-creates.**
The offer is tappable Yes/Skip, never implicit. Creating a user, a vendor, or a
money account is a real write with real consequences (a new user gets WhatsApp
access to org data). "Never a silent default" from
`application/finance/resolution.py` is preserved exactly — what changes is that
the alternative to a silent default becomes an offer rather than a dead end.

**ADR-E5 — Role gates apply to the provider, not just the original.**
A SITE_ENGINEER who triggers a `Missing USER` must not be offered CREATE_USER,
because `_PROJECT_CREATE_ROLES` will refuse them. The offer is filtered by
`WorkflowDefinition.allowed_roles` (added 2026-07-30) — the same field the
capability menu and help matcher already filter on. They get the plain "not
found" reply, plus who to ask.

**ADR-E6 — Reuse `ProjectSetupOfferStore`'s shape, not the store itself.**
The project→site→member chain already implements "offer the next step as
tappable buttons, remember what it was about, expire after 10 minutes." That
shape is right and should be generalised; whether it becomes one store or two is
an implementation detail for Phase 1.

---

## 5. Sequencing

A strangler, not a big-bang rewrite. Each phase leaves the system working.

| Phase | Work | Proves |
|---|---|---|
| **0** | This document; Module Placement Log row | Shape agreed before code |
| **1** | `EntityType`, resolution outcome, registry `provides`/`requires`, one generic continuation | The mechanism exists |
| **2** | Migrate **USER** onto it (the live Hysam bug), including `Ambiguous` fuzzy matching | End-to-end on a real failure |
| **3** | Migrate **MATERIAL** | The strongest correctness check — the generic path must reproduce `resume_pending_report_with_material_create` exactly. If it can't, the design is wrong |
| **4** | Migrate ACCOUNT, VENDOR, AUDIENCE, PROJECT, SITE; delete each bespoke resolver as it moves | The ~10 duplicates collapse |

Phases 1–2 fix the reported bug. Phases 3–4 are where the duplication actually
dies. **Phase 3 is the honest test of this plan** — materials are the one entity
whose good behaviour already exists, so if the generic mechanism cannot express
it without special-casing, the abstraction is wrong and should be reconsidered
rather than forced.

---

## 6. Non-goals

- **Not** a rewrite of the workflow engine, the planner, or LangGraph usage.
- **Not** a change to what any workflow *does* once its entities resolve.
- **Not** auto-creation of anything (ADR-E4).
- **Not** multi-level chaining (ADR-E3).
- **Not** a replacement for backend validation (ADR-E2).

---

## 7. Open questions

1. **Fuzzy threshold.** How close is "did you mean"? Too loose suggests
   strangers; too tight and ഹൈസം never finds Hisham. Needs real org data —
   `match_worker`'s existing threshold is the starting point, not the answer.
2. **Cross-script matching.** Does the near-match run on the Malayalam original,
   the transliteration, or both? Extraction gives us the translated text; the
   original script may be the better signal for a person's name.
3. **Does `EntityType` belong in `shared/contracts`?** It is registry-local
   metadata today (`WorkflowCategory` is deliberately *not* in contracts). If the
   backend resolvers ever key off it, that changes.
4. **Idempotency across the resume.** The original event carries an idempotency
   key generated before the pause. Confirm it survives the create-and-resume trip
   without either replaying or duplicating.

---

## 8. Relationship to the Composite Request Plan layer

[`COMPOSITE_REQUEST_PLAN_LAYER.md`](COMPOSITE_REQUEST_PLAN_LAYER.md) (Ilan,
same day) covers the *other* half of the same problem: one message stating
several intents up front ("create project Paraclette, then site Tower B, add
Hysamm as PM, and log slab work started"), rather than one intent discovering a
missing prerequisite mid-flight.

The two were designed independently and converged on the same registry
declaration (§3.2). That document defers field ownership to whichever design
lands first; this one landed first, so the `frozenset` shapes above are
canonical — a shape adopted *from* that doc, since it was the better of the two.

**Adopted from that document verbatim, because it is correct and this plan is
incomplete without it:**

> There is one plan object and one executor. Decomposition inserts steps into it
> before execution; entity resolution inserts steps into it during execution. A
> missing entity is a step insertion, not a separate suspend mechanism.

Without that invariant the two layers would produce two dependency sequencers,
two Redis state stores, two confirmation UXes, and no defined answer to "what
happens when a planned step hits a missing entity."

**Consequence for build order:** this layer's generic continuation (§3.3) *is*
that layer's executor — discovered late instead of early. So this one is built
first, and composite decomposition becomes a second producer of steps into
machinery that already exists. Building it the other way round would mean
constructing plan sequencing on top of the ten independent resolvers this plan
is collapsing.

One consequence to carry into Phase 1: ADR-E3 (depth 1) is a constraint on
*this* layer's suspend-and-resume, not on plan length. A composite plan of five
steps is not "depth 5" — it is one plan with five steps, each of which may
suspend once.

---

## 9. Verification

This plan is written against a bug found by sending real WhatsApp messages, and
must be verified the same way. Unit tests can prove the continuation resumes;
only a live Malayalam message can prove ഹൈസം reaches Hisham.

Every phase needs a live send before it is called done.
