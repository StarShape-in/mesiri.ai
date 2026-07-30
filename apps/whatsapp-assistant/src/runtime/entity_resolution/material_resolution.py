"""Express a materials-catalog lookup in the shared resolution vocabulary --
Phase 3 of docs/execution/ENTITY_RESOLUTION_PLAN.md §5.

Phase 3 is the plan's own stated correctness check: materials are the one
entity whose good behaviour already existed before the entity-resolution
layer, so if the generic mechanism cannot express it *without special-casing*,
the abstraction is wrong. Migrating it produced two findings, both recorded
here rather than papered over.

## Finding 1 -- the layer splits in two, and materials need only one half

`member_resolution.py` contributes BOTH halves to USER: the matching
technique (difflib near-match scoring, because an org's user list has no
searchable structure and ഹൈസം/Hisham must still meet) and the outcome
vocabulary (Resolved/Ambiguous/Missing).

Materials need only the second. Their matching already happens in SQL and is
already right: `find_by_name_exact_active` then `find_by_name_fuzzy`'s
substring/ILIKE over a catalog the org itself curated. Substring is the
*better* technique here -- "cement" should match "OPC Cement 53 Grade", which
difflib scores at 0.35 and would discard, while difflib's strength (catching
a transliteration one character off) is not what a product catalog needs.

So this module deliberately does NOT re-implement scoring. It classifies a
list the caller already fetched. That is not a gap in the abstraction; it is
the abstraction being honest about which of its two halves each entity needs.

## Finding 2 -- there is no `EntityType.MATERIAL`, on purpose

`EntityType`'s members are the entities a *workflow* provides
(`workflow_that_provides`), and no workflow provides MATERIAL: creating a
catalog entry is a direct `create_material` write inside
`_create_material_and_resume`, not a confirmed workflow the way CREATE_USER
is. Adding a member here would make `workflow_that_provides(MATERIAL)` return
None -- a lie in a table whose entire purpose is answering that question.

The chaining half of the plan (§3's "insert a step, run the provider
workflow, resume where it left off") therefore does not apply to materials at
all, and the create-offer/resume legs in `resume.py` stay exactly as they
are. Only the gate's *vocabulary* moves.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from workflows.entities import Ambiguous, Candidate, Missing, ResolutionOutcome, Resolved


def classify_material_matches(
    name_hint: str, matches: Sequence[Mapping[str, Any]]
) -> ResolutionOutcome:
    """Turn `MaterialCatalogQueryService.find_materials`' rows into the shared
    Resolved/Ambiguous/Missing vocabulary.

    Pure -- the query already happened. `matches` is that call's result
    verbatim, which carries its own contract worth restating: an exact
    (case-insensitive) match is returned ALONE, so a single row here is
    either "the one exact hit" or "the one substring candidate".

    Those two are deliberately not distinguished, because the caller before
    this module did not distinguish them either -- one match auto-fills
    `material_id` and moves on. That is preserved byte-for-byte (Phase 3 is a
    migration, not a behaviour change), but it is worth naming that it sits in
    tension with `find_by_name_fuzzy`'s own docstring, which says substring
    candidates are "never auto-accepted":

      "50 bags of cement" against a catalog holding exactly one row matching
      *cement* ("OPC Cement 53 Grade") resolves silently rather than asking.

    Unlike the USER case that tension is bounded, which is why it was left
    alone rather than "fixed" inside a refactor: the resolved material's real
    name is rendered in the confirmation prompt the user must still answer, so
    a wrong substring hit is visible and rejectable before anything is
    written. A wrong USER match, by contrast, silently grants a stranger
    access to org data -- which is why `member_resolution.py` refuses to
    auto-accept anything short of an exact match. See ENTITY_RESOLUTION_PLAN
    .md §7's open question on thresholds if this ever needs revisiting.
    """
    if not matches:
        return Missing(name_hint=name_hint)

    if len(matches) == 1:
        row = matches[0]
        return Resolved(entity_id=str(row["id"]), display_name=str(row["name"]))

    return Ambiguous(
        candidates=tuple(
            Candidate(entity_id=str(row["id"]), display_name=str(row["name"]))
            for row in matches
        )
    )
