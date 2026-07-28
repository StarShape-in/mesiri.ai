"""Worker promotion is hooked onto the paths that actually carry the events.

The bug these guard against shipped twice and was invisible to every other
test in the suite: the promotion functions were correct, fully unit-tested,
and called from the wrong place. Nothing ever triggered.

A confirmation reply ("yes", or a Confirm tap) is resolved by
``handle_fast_path`` in runtime/dependencies.py, which sends its reply and
**returns** -- ``process_inbound_message`` (runtime/inbound_journey.py) never
runs for that message. The answer to the promotion offer arrives on the same
file's ``handle_slot_answer`` branch, which also returns. Hooks placed in
inbound_journey therefore fire for nobody, which is exactly what happened.

These are source-level assertions rather than behavioural ones on purpose.
The failure mode is not "the function is wrong" -- it is "the function is
never reached", which a test that calls the function directly can never
detect. Checking the call site is the only thing that catches it.
"""

from __future__ import annotations

import inspect
import re


def _dependencies_source() -> str:
    import runtime.dependencies as deps

    return inspect.getsource(deps)


def _block_after(source: str, marker: str, stop: str) -> str:
    """The source between ``marker`` and the next occurrence of ``stop``."""
    start = source.index(marker)
    end = source.index(stop, start)
    return source[start:end]


def test_the_confirmation_fast_path_triggers_the_promotion_offer():
    """Attendance is confirmed here, so the follow-up offer has to be here."""
    source = _dependencies_source()
    block = _block_after(
        source,
        "handle_fast_path(ctx.user_id, message, actor=ctx)",
        "handle_slot_answer",
    )
    # The *call*, not the import line -- an import alone proves nothing, and
    # matching the bare name let a first version of this test pass against a
    # hook that had been removed.
    assert "await _maybe_trigger_worker_promotion(" in block


def test_the_slot_answer_path_writes_the_promoted_workers():
    """The reply naming who to add arrives here, and the node cannot write."""
    source = _dependencies_source()
    block = _block_after(
        source,
        "handle_slot_answer(ctx.user_id, message)",
        "try_handle_account_admin_command",
    )
    assert "await _create_promoted_workers(" in block


def test_the_inbound_journey_does_not_pretend_to_handle_promotion():
    """Both hooks lived here once and fired for nobody. If they come back,
    it means someone re-made the same mistake -- the journey is not reached
    for either event."""
    import runtime.inbound_journey as journey

    source = inspect.getsource(journey)
    # The definitions still live here; only the *call sites* must not.
    calls = re.findall(
        r"^\s+(?:await\s+)?_safe\(\s*$\n\s+(_maybe_trigger_worker_promotion|_create_promoted_workers)\(",
        source,
        re.MULTILINE,
    )
    assert calls == [], f"promotion hooked into a path that never runs for it: {calls}"
