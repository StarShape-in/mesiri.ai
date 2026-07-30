"""runtime/entity_resolution/material_resolution.py -- Phase 3 of
ENTITY_RESOLUTION_PLAN.md: the materials catalog expressed in the shared
Resolved/Ambiguous/Missing vocabulary.

Pure function, no DB and no fakes needed -- the SQL matching happens before
this and is the catalog repository's own concern (see that module's docstring
on why materials need only half of the entity-resolution layer).

The behavioural proof that this migration changed nothing lives in
test_material_create_gate.py / test_material_unit_gates.py, which exercise
_run_material_unit_gates end-to-end and were not modified for Phase 3.
"""

from __future__ import annotations

import uuid

from runtime.entity_resolution.material_resolution import classify_material_matches
from workflows.entities import Ambiguous, Missing, Resolved

CEMENT_ID = str(uuid.uuid4())
OPC_ID = str(uuid.uuid4())
PPC_ID = str(uuid.uuid4())


def _row(material_id: str, name: str) -> dict:
    return {"id": material_id, "name": name, "is_active": True, "default_unit_id": None}


def test_no_matches_is_missing_and_carries_the_hint_back():
    outcome = classify_material_matches("Fevicol", [])
    assert isinstance(outcome, Missing)
    # ADR-E4: Missing always offers to create with the EXACT reported name,
    # never an invented one -- so the hint has to survive.
    assert outcome.name_hint == "Fevicol"


def test_one_match_resolves():
    outcome = classify_material_matches("cement", [_row(CEMENT_ID, "Cement")])
    assert isinstance(outcome, Resolved)
    assert outcome.entity_id == CEMENT_ID
    assert outcome.display_name == "Cement"


def test_several_matches_are_ambiguous_in_order():
    outcome = classify_material_matches(
        "cement", [_row(OPC_ID, "OPC Cement"), _row(PPC_ID, "PPC Cement")]
    )
    assert isinstance(outcome, Ambiguous)
    assert [c.entity_id for c in outcome.candidates] == [OPC_ID, PPC_ID]
    assert [c.display_name for c in outcome.candidates] == ["OPC Cement", "PPC Cement"]


def test_a_single_substring_match_is_auto_accepted():
    """Documents the tension named in the module docstring rather than
    hiding it: find_by_name_fuzzy calls substring hits "never auto-accepted",
    but a lone one has always resolved silently here, and Phase 3 is a
    migration rather than a behaviour change. Bounded, unlike the USER case:
    the resolved name is rendered in the confirmation the user still answers.

    If this is ever tightened to Ambiguous, this test is the one that should
    fail loudly and be rewritten deliberately.
    """
    outcome = classify_material_matches("cement", [_row(OPC_ID, "OPC Cement 53 Grade")])
    assert isinstance(outcome, Resolved)
    assert outcome.display_name == "OPC Cement 53 Grade"


def test_non_string_ids_are_normalized_to_str():
    """find_materials returns rows straight from the repository, where id is a
    uuid.UUID rather than a str -- the outcome must not leak that through to
    canonical_event.fields, which is serialized to JSON."""
    real_uuid = uuid.uuid4()
    outcome = classify_material_matches(
        "cement", [{"id": real_uuid, "name": "Cement", "is_active": True}]
    )
    assert isinstance(outcome, Resolved)
    assert outcome.entity_id == str(real_uuid)
    assert isinstance(outcome.entity_id, str)
