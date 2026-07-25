"""Shared single-choice slot-filling helper for LangGraph workflow nodes.

Pure -- no I/O, no AI calls, no DB. Candidate lists are seeded into a node's
`collected_fields` by the caller before the graph runs (a node must never
query a repository itself, see workflows/runtime.py's docstring); this module
only decides whether to auto-fill, ask, or leave a field unset, and matches a
free-text/numbered reply back against the same candidate list. One instance
of this pattern is reused by every finance workflow that needs to ask "which
one?" -- expense_capture's account slot today, transfers/petty cash later
(see docs/execution/FINANCE_MODULE_PLAN.md's Slice 1).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class SlotCandidate:
    value: str
    label: str


@dataclass(frozen=True, slots=True)
class SlotResolution:
    """Outcome of resolving one single-choice slot for a single node pass.

    Exactly one of `resolved_value` or `awaiting_slot` is set -- never both,
    never neither (0 candidates resolves to `resolved_value=None` with no
    question asked, since there is nothing to choose between).
    """

    resolved_value: str | None
    awaiting_slot: str | None
    slot_prompt: str | None

    def __post_init__(self) -> None:
        if self.awaiting_slot is not None and self.slot_prompt is None:
            raise ValueError("awaiting_slot requires a slot_prompt")
        if self.awaiting_slot is not None and self.resolved_value is not None:
            raise ValueError("a slot cannot be both resolved and awaiting an answer")


def resolve_single_choice_slot(
    *, slot_name: str, prompt_title: str, candidates: list[SlotCandidate]
) -> SlotResolution:
    """0 candidates -> proceed unset (nothing to choose between). 1 candidate
    -> auto-fill silently, never ask when there is no real ambiguity. N
    candidates -> ask, as a numbered list."""
    if not candidates:
        return SlotResolution(resolved_value=None, awaiting_slot=None, slot_prompt=None)
    if len(candidates) == 1:
        return SlotResolution(
            resolved_value=candidates[0].value, awaiting_slot=None, slot_prompt=None
        )
    return SlotResolution(
        resolved_value=None,
        awaiting_slot=slot_name,
        slot_prompt=_format_prompt(prompt_title, candidates),
    )


def match_slot_answer(text: str, candidates: list[SlotCandidate]) -> str | None:
    """Match a numbered or free-text reply against candidate labels.

    Numbered replies ("2") are the fast path; free text matches case-
    insensitively against a candidate's label (exact or substring either
    direction, so "site cash" matches "Site Cash" and a slightly longer
    phrase like "from site cash please" still matches). Returns None when
    nothing matches -- the caller re-asks rather than guessing.
    """
    stripped = text.strip()
    if not stripped:
        return None
    if stripped.isdigit():
        index = int(stripped) - 1
        if 0 <= index < len(candidates):
            return candidates[index].value
    lowered = stripped.lower()
    for candidate in candidates:
        label_lower = candidate.label.lower()
        if lowered == label_lower or lowered in label_lower or label_lower in lowered:
            return candidate.value
    return None


def _format_prompt(title: str, candidates: list[SlotCandidate]) -> str:
    lines = [title, ""]
    lines.extend(f"{i}. {c.label}" for i, c in enumerate(candidates, start=1))
    lines.append("")
    lines.append("Reply with a number, or just tell me which one.")
    return "\n".join(lines)
