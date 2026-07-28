"""Worker promotion workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed (optional
``workflow`` dependency group). Mirrors test_labour_attendance_graph.py.

Two things only the compiled graph can show:

1. **The state survives being persisted.** Between messages the runtime saves
   the graph's state with ``model_dump_json()`` and rebuilds it from the
   database on the next one. These tests round-trip through a real
   ``WorkflowStateV2`` rather than passing dicts straight from one pass to
   the next, because passing dicts is exactly what hid the bug this file now
   guards: an earlier version seeded a create-callable into the state, which
   could not serialize at all. Saving raised, the run was recorded as failed,
   and the promotion offer silently never arrived. Every node-level test
   passed throughout, because they used a fake repository that never
   serializes anything.

2. **The conditional edge routes on both slots.** A promotion run can take
   three messages (offer → duplicate question → answer), and a router that
   only recognised the first slot would fall through and lose the held-back
   worker.
"""

from __future__ import annotations

import uuid

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.planner_decision import WorkflowKey  # noqa: E402
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2  # noqa: E402
from mesiri_contracts.context.enums import WorkflowPhase  # noqa: E402
from workflows.registry import WorkflowRegistry  # noqa: E402
from workflows.worker_promotion.graph import build_worker_promotion_graph  # noqa: E402
from workflows.worker_promotion.nodes import (  # noqa: E402
    DUPLICATE_SLOT,
    PROMOTION_SLOT,
    WORKERS_TO_CREATE,
)

RAVI = {"name": "Ravi", "trade": "mason", "daily_wage": "800"}


def _base_state(fields: dict, **extra) -> dict:
    state = {
        "workflow_instance_id": "wf_promo_1",
        "workflow_key": WorkflowKey.WORKER_PROMOTION.value,
        "correlation_id": "cor_1",
        "organization_id": "org1",
        "user_id": "usr1",
        "project_id": "prj1",
        "site_id": None,
        "collected_fields": fields,
    }
    state.update(extra)
    return state


def _through_the_database(result: dict) -> dict:
    """Persist the graph's state and read it back, exactly as the runtime does
    between two inbound messages. Raises if anything in it cannot be stored."""
    saved = WorkflowStateV2(
        workflow_instance_id=str(uuid.uuid4()),
        workflow_key=WorkflowKey.WORKER_PROMOTION,
        correlation_id="cor_1",
        organization_id=str(uuid.uuid4()),
        user_id=str(uuid.uuid4()),
        phase=WorkflowPhase.COLLECTING_FIELDS,
        collected_fields=result["collected_fields"],
        awaiting_slot=result["awaiting_slot"],
        pending_prompt=result["pending_prompt"],
    )
    revived = WorkflowStateV2.model_validate_json(saved.model_dump_json())
    return dict(revived.collected_fields)


async def test_offer_pass_builds_a_storable_list():
    graph = build_worker_promotion_graph()

    result = await graph.ainvoke(_base_state({"promotable_workers": [RAVI]}))

    assert result["awaiting_slot"] == PROMOTION_SLOT
    assert "Ravi" in result["pending_prompt"]
    # The pass that used to fail: everything the node returned must persist.
    assert _through_the_database(result)["promotable_workers"] == [RAVI]


async def test_answering_hands_the_worker_back_for_the_caller_to_write():
    """The node decides and the caller writes, so what the graph produces is
    a plain list of workers -- carried across the database round trip."""
    graph = build_worker_promotion_graph()

    asked = await graph.ainvoke(_base_state({"promotable_workers": [RAVI]}))

    resumed = await graph.ainvoke(
        _base_state(
            {**_through_the_database(asked), "_slot_answer_text": "all"},
            awaiting_slot=asked["awaiting_slot"],
        )
    )

    assert resumed["collected_fields"][WORKERS_TO_CREATE] == [
        {"name": "Ravi", "trade": "mason", "daily_wage": "800"}
    ]
    assert "Added to your Worker Register: Ravi" in resumed["pending_prompt"]
    assert resumed["awaiting_slot"] is None


async def test_the_duplicate_question_survives_a_third_pass_through_the_graph():
    graph = build_worker_promotion_graph()
    register = [
        {"worker_id": "w1", "name": "Ravi Kumar", "trade": "mason", "contractor": None}
    ]

    offered = await graph.ainvoke(
        _base_state({"promotable_workers": [RAVI], "_register": register})
    )

    held = await graph.ainvoke(
        _base_state(
            {**_through_the_database(offered), "_slot_answer_text": "Ravi"},
            awaiting_slot=offered["awaiting_slot"],
        )
    )

    assert held["awaiting_slot"] == DUPLICATE_SLOT
    assert not held["collected_fields"].get(WORKERS_TO_CREATE)

    resolved = await graph.ainvoke(
        _base_state(
            {**_through_the_database(held), "_slot_answer_text": "Ravi"},
            awaiting_slot=held["awaiting_slot"],
        )
    )

    assert [w["name"] for w in resolved["collected_fields"][WORKERS_TO_CREATE]] == ["Ravi"]
    assert resolved["awaiting_slot"] is None


async def test_registry_resolves_the_worker_promotion_key():
    registry = WorkflowRegistry()
    graph = registry.get_graph(WorkflowKey.WORKER_PROMOTION)
    assert graph is not None
    assert registry.get_graph(WorkflowKey.WORKER_PROMOTION) is graph
