"""System graph for the control panel — how the assistant reacts to messages.

Platform-admin only. The Mermaid diagram returned here is NOT hand-drawn: it is
generated on request from the live routing tables the runtime actually uses
(understanding pipeline modality branches, canonicalization.mapping, planner
routing table, workflow registry) plus each compiled LangGraph's own
draw_mermaid(). Change any of those tables or graphs and this endpoint reflects
it on the next refresh — there is no separate diagram to keep in sync.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from mesiri.domains.shared.auth import require_platform_admin

router = APIRouter(prefix="/admin/system-graph", tags=["admin"])


class WorkflowGraphInfo(BaseModel):
    workflow_key: str
    implemented: bool
    mermaid: str | None = None


class SystemGraphResponse(BaseModel):
    mermaid: str
    workflows: list[WorkflowGraphInfo]


def _node_id(value: str) -> str:
    """Mermaid-safe node id."""
    return value.replace(".", "_").replace("-", "_")


def _build_pipeline_mermaid() -> str:
    """The end-to-end inbound journey, derived from live routing tables."""
    from canonicalization.mapping import (
        _MATERIAL_DIRECTION_EVENT_TYPE,
        _SIMPLE_EVENT_TYPE,
    )
    from mesiri_contracts.assistant.canonical_event import CanonicalEventType
    from mesiri_contracts.assistant.enums import SemanticType
    from planner.routing import WORKFLOW_KEY_BY_EVENT
    from workflows.registry import _BUILDERS

    lines: list[str] = ["flowchart LR"]

    # --- Understanding stage: modality branches (mirrors pipeline.understand) ---
    lines += [
        '  subgraph Understanding["1 · Understanding"]',
        '    msg([WhatsApp message])',
        '    text{{"text / interactive"}}',
        '    voice{{"voice"}}',
        '    media{{"image / document"}}',
        '    speech["Speech: STT + translation"]',
        '    vision["Vision: OCR / description"]',
        '    extraction["Structured extraction (LLM)"]',
        "    msg --> text & voice & media",
        "    text --> extraction",
        "    voice --> speech --> extraction",
        "    media --> vision --> extraction",
        "  end",
    ]

    # --- Semantic types -> canonical events (live canonicalization mapping) ---
    lines.append('  subgraph Canonicalization["2 · Canonicalization"]')
    for event in CanonicalEventType:
        lines.append(f'    {_node_id(event.name)}(["{event.value}"])')
    lines.append("  end")

    for semantic, event in _SIMPLE_EVENT_TYPE.items():
        lines.append(f'  extraction -- "{semantic.value}" --> {_node_id(event.name)}')
    for direction, event in _MATERIAL_DIRECTION_EVENT_TYPE.items():
        lines.append(
            f'  extraction -- "{SemanticType.MATERIAL_UPDATE.value} · {direction}" '
            f"--> {_node_id(event.name)}"
        )
    lines.append(
        f'  extraction -- "unknown / low confidence" --> {_node_id(CanonicalEventType.UNRECOGNIZED.name)}'
    )

    # --- Planner: events that never start a workflow (see planner/routing.py) ---
    lines += [
        '  subgraph Planner["3 · Planner"]',
        '    direct["DIRECT_REPLY"]',
        '    clarify["CLARIFY"]',
        "  end",
        f"  {_node_id(CanonicalEventType.GENERAL_QUESTION_ASKED.name)} --> direct",
        f"  {_node_id(CanonicalEventType.UNRECOGNIZED.name)} --> direct",
        f"  {_node_id(CanonicalEventType.CLARIFICATION_REQUIRED.name)} --> clarify",
        '  direct --> reply(["Reply on WhatsApp"])',
        "  clarify --> reply",
    ]

    # --- Workflow routing table + registry implementation status ---
    lines.append('  subgraph Workflows["4 · Workflows (LangGraph)"]')
    for key in sorted({k for k in WORKFLOW_KEY_BY_EVENT.values()}, key=lambda k: k.value):
        implemented = key in _BUILDERS
        label = key.value if implemented else f"{key.value} · not built yet"
        shape = f'[["{label}"]]' if implemented else f'["{label}"]'
        lines.append(f"    wf_{_node_id(key.value)}{shape}")
    lines.append("  end")

    for event, key in WORKFLOW_KEY_BY_EVENT.items():
        lines.append(f"  {_node_id(event.name)} --> wf_{_node_id(key.value)}")

    for key in WORKFLOW_KEY_BY_EVENT.values():
        target = "reply" if key in _BUILDERS else "unsupported"
        lines.append(f"  wf_{_node_id(key.value)} --> {target}")
    lines.append('  unsupported(["\'Not supported yet\' reply"])')

    return "\n".join(lines)


def _workflow_graphs() -> list[WorkflowGraphInfo]:
    """One Mermaid diagram per workflow, drawn by LangGraph itself."""
    from mesiri_contracts.assistant.planner_decision import WorkflowKey
    from workflows.registry import _BUILDERS, WorkflowRegistry

    registry = WorkflowRegistry()
    infos: list[WorkflowGraphInfo] = []
    for key in WorkflowKey:
        implemented = key in _BUILDERS
        mermaid: str | None = None
        try:
            graph = registry.get_graph(key)
            if graph is not None:
                mermaid = graph.get_graph().draw_mermaid()
        except Exception:  # noqa: BLE001 — langgraph optional; degrade to status-only
            pass
        infos.append(
            WorkflowGraphInfo(workflow_key=key.value, implemented=implemented, mermaid=mermaid)
        )
    return infos


@router.get("", response_model=SystemGraphResponse)
async def get_system_graph(_admin: dict = Depends(require_platform_admin)):
    return SystemGraphResponse(
        mermaid=_build_pipeline_mermaid(),
        workflows=_workflow_graphs(),
    )
