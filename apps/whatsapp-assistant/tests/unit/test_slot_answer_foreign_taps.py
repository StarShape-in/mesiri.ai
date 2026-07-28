"""A tap on one picker must never be eaten by an unrelated open question.

Reported from testing: with a worker-promotion offer open, sending a photo
and choosing "Attendance" from the "what is this photo for?" list replied
"Sorry, I didn't catch that. Reply with all, none, or the names of the
workers to add." The photo was never processed.

handle_slot_answer accepts INTERACTIVE messages and runs *before* both the
category-tap handler and the image-purpose picker (see the ordering in
runtime/dependencies.py), so any pending slot question swallowed their taps
and tried to read "Attendance" as a worker's name.

This is not specific to promotion -- an open "which account?" question would
have eaten the same tap. What makes it safe to distinguish is that slot
options always carry dynamic values (worker ids, account ids) and never the
app's own fixed row ids.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from interactions.handler import _FOREIGN_PICKER_IDS, InteractionHandler
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.planner_decision import WorkflowKey
from mesiri_contracts.assistant.v2.workflow_state import WorkflowStateV2
from mesiri_contracts.context.enums import WorkflowPhase
from workflows.fakes import FakeWorkflowInstanceRepository
from workflows.runtime import WorkflowRuntime

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"


class _ExplodingRegistry:
    """Any graph lookup here means a foreign tap reached the slot machinery."""

    def get_graph(self, key):  # noqa: ANN001, ANN201
        raise AssertionError(f"a foreign picker tap reached the slot graph: {key}")


def _tap(row_id: str, title: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id=f"wamid.{row_id}",
        correlation_id=f"cor_{row_id}",
        sender=SenderInfo(wa_id="919000000000", profile_name="Engineer"),
        modality=InputModality.INTERACTIVE,
        text=title,
        timestamp=datetime.now(UTC),
        metadata={"interactive_reply_id": row_id},
    )


def _runtime_with_open_question() -> WorkflowRuntime:
    repo = FakeWorkflowInstanceRepository()
    repo.seed(
        WorkflowStateV2(
            workflow_instance_id="wf_promo",
            workflow_key=WorkflowKey.WORKER_PROMOTION,
            correlation_id="cor_old",
            organization_id=ORG,
            user_id=USR,
            phase=WorkflowPhase.COLLECTING_FIELDS,
            collected_fields={"promotable_workers": [{"name": "Rahul"}]},
            awaiting_slot="promotion_choice",
            pending_prompt="Would you like to add any of these workers?",
        ),
        version=0,
    )
    return WorkflowRuntime(registry=_ExplodingRegistry(), repo=repo)


def _handler(runtime: WorkflowRuntime) -> InteractionHandler:
    return InteractionHandler(workflow_runtime=runtime)


@pytest.mark.parametrize(
    ("row_id", "title"),
    [
        ("img_attendance", "Attendance"),  # the exact tap that was reported
        ("img_expense", "Expense"),
        ("img_site_update", "Site Update"),
        ("cat_labour", "Labour"),
        ("cat_material", "Material"),
    ],
)
async def test_a_picker_tap_is_not_swallowed_by_an_open_slot_question(row_id, title):
    handled = await _handler(_runtime_with_open_question()).handle_slot_answer(
        USR, _tap(row_id, title)
    )

    assert handled is None, f"{row_id} was consumed as a slot answer"


async def test_a_genuine_slot_answer_still_reaches_the_workflow():
    """The guard must not deafen the slot machinery to real answers -- a
    typed reply carries no picker id and has to go through."""
    runtime = _runtime_with_open_question()
    typed = NormalizedMessage(
        message_id="wamid.typed",
        correlation_id="cor_typed",
        sender=SenderInfo(wa_id="919000000000", profile_name="Engineer"),
        modality=InputModality.TEXT,
        text="save all",
        timestamp=datetime.now(UTC),
    )

    with pytest.raises(AssertionError, match="reached the slot graph"):
        await _handler(runtime).handle_slot_answer(USR, typed)


def test_every_fixed_picker_row_is_protected():
    """Derived from the row definitions rather than written out, so adding a
    row to a picker cannot leave it unprotected."""
    from channel.replies import CATEGORY_ROWS, IMAGE_PURPOSE_ROWS

    for row in (*IMAGE_PURPOSE_ROWS, *CATEGORY_ROWS):
        assert row.id in _FOREIGN_PICKER_IDS
