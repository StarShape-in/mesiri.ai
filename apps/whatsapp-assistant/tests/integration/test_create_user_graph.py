"""Create-user workflow graph — real LangGraph integration test.

Skipped automatically when ``langgraph`` isn't installed (optional
``workflow`` dependency group). Proves the compiled conditional-edge graph
(resolve_whatsapp_number's slot-fill) actually runs end to end; unit tests
in tests/unit/test_create_user_nodes.py exercise the same node logic with
fakes and need no LangGraph import at all. Mirrors
test_expense_capture_graph.py.

The scenario this exists to prove: ENTITY_RESOLUTION_PLAN.md's CREATE_USER
chain starts this workflow with only a name, no number -- before
resolve_whatsapp_number existed, that produced a terminal, non-resumable
result (a pending_prompt with no awaiting_slot), and the number typed in
reply to "What's their WhatsApp number?" was silently lost, confirmed by a
live trace. test_missing_number_leaves_a_real_awaiting_slot_not_a_dead_end
is the regression guard for exactly that bug.
"""

from __future__ import annotations

import pytest

pytest.importorskip("langgraph")

from mesiri_contracts.assistant.draft_action import DraftActionType  # noqa: E402
from workflows.create_user.graph import build_create_user_graph  # noqa: E402
from workflows.create_user.nodes import _NUMBER_SLOT_NAME  # noqa: E402

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


def _base_state(fields: dict) -> dict:
    return {
        "workflow_instance_id": "wf_1",
        "workflow_key": "user.create",
        "correlation_id": "cor_1",
        "organization_id": ORG,
        "user_id": USR,
        "project_id": None,
        "site_id": None,
        "collected_fields": fields,
    }


async def test_name_and_number_together_builds_a_draft_in_one_pass():
    graph = build_create_user_graph()

    result = await graph.ainvoke(
        _base_state({"full_name": "Rajesh", "whatsapp_number": "9198765xxxxx".replace("x", "4")})
    )

    assert result["draft_action"].action_type is DraftActionType.CREATE_USER
    assert result.get("awaiting_slot") is None
    assert "Confirm this action" in result["pending_prompt"]


async def test_missing_number_leaves_a_real_awaiting_slot_not_a_dead_end():
    """The regression guard for the live bug: starting with a name and no
    number must leave a resumable state, not a terminal one."""
    graph = build_create_user_graph()

    result = await graph.ainvoke(_base_state({"full_name": "Hysam", "role": "PROJECT_MANAGER"}))

    assert result.get("draft_action") is None
    assert result["awaiting_slot"] == _NUMBER_SLOT_NAME
    assert "number" in result["pending_prompt"].lower()
    # Fields collected so far survive the pause, same as every other
    # slot-filling workflow.
    assert result["collected_fields"]["full_name"] == "Hysam"
    assert result["collected_fields"]["role"] == "PROJECT_MANAGER"


async def test_full_round_trip_slot_answer_then_draft():
    """The end-to-end shape WorkflowRuntime drives: start() pauses on the
    missing number; provide_input() re-invokes the graph with
    _slot_answer_text set to the user's reply and awaiting_slot carried
    forward -- this is what turns "the number was lost" into "the number
    resolves and a draft appears"."""
    graph = build_create_user_graph()

    first = await graph.ainvoke(_base_state({"full_name": "Hysam"}))
    assert first["awaiting_slot"] == _NUMBER_SLOT_NAME

    resumed_fields = dict(first["collected_fields"])
    resumed_fields["_slot_answer_text"] = "+91 97781 90485"
    second = await graph.ainvoke(
        {
            **_base_state(resumed_fields),
            "awaiting_slot": first["awaiting_slot"],
        }
    )

    assert second["draft_action"].action_type is DraftActionType.CREATE_USER
    assert second["draft_action"].fields["full_name"] == "Hysam"
    assert second["draft_action"].fields["whatsapp_number"] == "919778190485"
    assert second.get("awaiting_slot") is None


async def test_an_invalid_number_reasks_rather_than_building_a_bad_draft():
    graph = build_create_user_graph()

    first = await graph.ainvoke(_base_state({"full_name": "Hysam"}))
    resumed_fields = dict(first["collected_fields"])
    resumed_fields["_slot_answer_text"] = "abc"
    second = await graph.ainvoke(
        {**_base_state(resumed_fields), "awaiting_slot": first["awaiting_slot"]}
    )

    assert second.get("draft_action") is None
    assert second["awaiting_slot"] == _NUMBER_SLOT_NAME
    assert "valid" in second["pending_prompt"].lower()


async def test_missing_name_still_gets_the_old_single_message_retry_not_a_slot():
    """The name field's behaviour is deliberately untouched -- only the
    number became a real slot."""
    graph = build_create_user_graph()

    result = await graph.ainvoke(_base_state({"whatsapp_number": "919876543210"}))

    assert result.get("draft_action") is None
    assert result.get("awaiting_slot") is None
    assert "name" in result["pending_prompt"].lower()
