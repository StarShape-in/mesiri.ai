"""Correction — documents where in-place field correction actually lives.

A *correction* is a user reply that changes a field value while a workflow
awaits confirmation -- e.g. "Actually, make it 5 bags, not 4."

Despite this module's name, the correction logic itself does NOT live here --
this file is deliberately just documentation plus (previously) a constant
that turned out to be dead code, removed below. The real mechanism:

    interactions/llm_classifier.py classifies a slow-path reply's segments,
    producing InteractionIntent.CORRECTION with a list of FieldCorrections.

    interactions/handler.py's handle_slow_path() intercepts CORRECTION
    segments directly -- BEFORE calling policy.decide() -- and calls
    workflows.WorkflowRuntime.correct(loaded, segment.corrections).

    workflows/runtime.py's correct() merges the corrections into
    collected_fields, re-invokes the graph to produce a new draft_action +
    pending_prompt, and persists the result under the SAME workflow_instance_id
    via an optimistic-locked transition() (loaded.version) -- so a correction
    patches the pending draft in place rather than starting a new workflow,
    and a lost version race fails safely (FAILED result) rather than
    silently double-applying.

policy.py's `decide()` never sees CORRECTION at all for this reason: it is
resolved one layer up, in handle_slow_path, before decide() is reached.
policy.decide() only ever receives CONFIRM/REJECT/CANCEL/AMBIGUOUS.

This module previously exported `CORRECTION_DEFERRED_NOTICE` and described
correction as "deferred post-M7" -- both were stale as of the mechanism
above landing; the constant had no remaining callers and has been removed
rather than kept as dead code.
"""

from __future__ import annotations
