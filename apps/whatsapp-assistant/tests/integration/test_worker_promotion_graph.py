"""Worker promotion workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed (optional
``workflow`` dependency group). Mirrors test_labour_attendance_graph.py.

What only the compiled graph can prove: the DB write happens inside a real
LangGraph *sync* node, which LangGraph runs via
``run_in_executor(None, node_fn)`` -- a fresh ThreadPoolExecutor thread with
no event loop of its own. inbound_journey.py's `_sync_create_worker` bridges
into that thread with `asyncio.run(coro)`. A unit test that calls the node
function directly (test_worker_promotion_nodes.py) never actually crosses
that boundary, so it cannot catch a regression back to the earlier
`asyncio.get_event_loop().run_until_complete(...)` pattern, which raises
RuntimeError from inside a non-main thread with no event loop set -- silently
swallowed by the node's `except Exception`, turning into a permanent
"Could not add" for every promotion.
"""

from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.planner_decision import WorkflowKey  # noqa: E402
from workflows.registry import WorkflowRegistry  # noqa: E402
from workflows.worker_promotion.graph import build_worker_promotion_graph  # noqa: E402
from workflows.worker_promotion.nodes import DUPLICATE_SLOT, PROMOTION_SLOT  # noqa: E402

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


def _threadpool_bridge_create_fn(record: list[dict]):
    """The exact pattern inbound_journey.py's `_sync_create_worker` uses:
    a synchronous callable that bridges into an async DB call via
    asyncio.run(), because the node it's called from runs in a
    ThreadPoolExecutor thread with no event loop of its own."""

    async def _write(name: str, trade: str | None, daily_wage) -> None:
        record.append({"name": name, "trade": trade, "daily_wage": daily_wage})

    def _sync_create_worker(*, name: str, trade: str | None, daily_wage) -> None:
        asyncio.run(_write(name, trade, daily_wage))

    return _sync_create_worker


async def test_offer_pass_builds_the_list():
    graph = build_worker_promotion_graph()

    result = await graph.ainvoke(_base_state({"promotable_workers": [RAVI]}))

    assert result["awaiting_slot"] == PROMOTION_SLOT
    assert "Ravi" in result["pending_prompt"]


async def test_answering_all_writes_the_worker_through_the_real_executor_thread():
    """The regression guard: the create_fn callable runs inside a real
    LangGraph sync node dispatched via run_in_executor -- not called directly
    from the test, which would never exercise the threading boundary at all."""
    graph = build_worker_promotion_graph()
    created: list[dict] = []

    asked = await graph.ainvoke(_base_state({"promotable_workers": [RAVI]}))

    resumed = await graph.ainvoke(
        _base_state(
            {
                **asked["collected_fields"],
                "_slot_answer_text": "all",
                "_create_worker_fn": _threadpool_bridge_create_fn(created),
            },
            awaiting_slot=asked["awaiting_slot"],
        )
    )

    assert created == [{"name": "Ravi", "trade": "mason", "daily_wage": "800"}]
    assert "Added to your Worker Register: Ravi" in resumed["pending_prompt"]
    assert resumed["awaiting_slot"] is None


async def test_the_duplicate_question_survives_a_third_pass_through_the_graph():
    """The promotion run can take three messages (offer → duplicate question →
    answer). Only the compiled graph proves the conditional edge routes back
    to END on the *second* slot too -- a router that only recognised the first
    would fall through and lose the held-back worker."""
    graph = build_worker_promotion_graph()
    created: list[dict] = []
    register = [
        {"worker_id": "w1", "name": "Ravi Kumar", "trade": "mason", "contractor": None}
    ]

    offered = await graph.ainvoke(
        _base_state({"promotable_workers": [RAVI], "_register": register})
    )

    held = await graph.ainvoke(
        _base_state(
            {
                **offered["collected_fields"],
                "_slot_answer_text": "Ravi",
                "_create_worker_fn": _threadpool_bridge_create_fn(created),
            },
            awaiting_slot=offered["awaiting_slot"],
        )
    )

    assert held["awaiting_slot"] == DUPLICATE_SLOT
    assert created == []

    resolved = await graph.ainvoke(
        _base_state(
            {
                **held["collected_fields"],
                "_slot_answer_text": "Ravi",
                "_create_worker_fn": _threadpool_bridge_create_fn(created),
            },
            awaiting_slot=held["awaiting_slot"],
        )
    )

    assert [c["name"] for c in created] == ["Ravi"]
    assert resolved["awaiting_slot"] is None


async def test_registry_resolves_the_worker_promotion_key():
    registry = WorkflowRegistry()
    graph = registry.get_graph(WorkflowKey.WORKER_PROMOTION)
    assert graph is not None
    assert registry.get_graph(WorkflowKey.WORKER_PROMOTION) is graph
