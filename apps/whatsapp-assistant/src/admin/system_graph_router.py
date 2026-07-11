"""System graph for the control panel — how the assistant reacts to messages.

Platform-admin only. Two capabilities:

1. GET ``/admin/system-graph`` — a structured, drill-down-ready map of the
   inbound pipeline. Nothing here is hand-drawn: the Mermaid diagram, the stage
   nodes, the workflow list, the required fields and the example messages are all
   generated on request from the live tables the runtime actually uses
   (understanding modality branches, ``canonicalization.mapping``, planner
   ``routing``, workflow ``registry``) plus each compiled LangGraph's own
   ``draw_mermaid()``, and the example copy from ``channel.replies``. Change any
   of those and this endpoint reflects it on the next refresh.

2. POST ``/admin/system-graph/simulate`` — run one message through the *real*
   pipeline (real AI providers) as a chosen org+user, capturing the reply instead
   of sending it to WhatsApp, and returning the full routing trace. Single-shot
   and side-effect-free: the material graph only builds a draft and asks for
   confirmation; nothing is persisted until a "YES" resume, which this harness
   never sends. See the ``dry_run`` marker in the response.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from mesiri.domains.shared.auth import require_platform_admin

router = APIRouter(prefix="/admin/system-graph", tags=["admin"])


# ---------------------------------------------------------------------------
# Response models
# ---------------------------------------------------------------------------
class StageNode(BaseModel):
    id: str
    label: str
    description: str | None = None


class PipelineStage(BaseModel):
    key: str
    title: str
    summary: str
    nodes: list[StageNode]


class WorkflowGraphInfo(BaseModel):
    workflow_key: str
    title: str
    implemented: bool
    canonical_event: str | None = None
    semantic_type: str | None = None
    required_fields: list[str] = []
    required_field_labels: list[str] = []
    node_names: list[str] = []
    example_messages: list[str] = []
    mermaid: str | None = None


class SystemGraphResponse(BaseModel):
    mermaid: str
    stages: list[PipelineStage]
    workflows: list[WorkflowGraphInfo]


class SimulateRequest(BaseModel):
    organization_id: uuid.UUID
    user_id: uuid.UUID
    text: str
    modality: str = "text"


class SimulateResponse(BaseModel):
    dry_run: bool = True
    ran_as_wa_id: str
    replies: list[str]
    understanding: dict | None = None
    resolved_context: dict | None = None
    canonical_event: dict | None = None
    planner_decision: dict | None = None
    workflow_run: dict | None = None


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _node_id(value: str) -> str:
    """Mermaid-safe node id."""
    return value.replace(".", "_").replace("-", "_")


_WORKFLOW_TITLES: dict[str, str] = {
    "material.receipt": "Material Receipt",
    "material.usage": "Material Usage",
    "expense.submit": "Expense",
    "equipment.usage": "Equipment Usage",
    "labour.attendance": "Labour Attendance",
    "site.update": "Site Update",
}


def _quoted(text: str) -> list[str]:
    """Pull the double-quoted example fragments out of a copy string."""
    return re.findall(r'"([^"]+)"', text)


def _example_messages_by_workflow() -> dict[str, list[str]]:
    """Example messages per workflow, sourced verbatim from channel.replies so
    the control panel shows exactly what the assistant tells users to send."""
    from channel.replies import _CATEGORY_PROMPTS, _EXAMPLES

    material_examples = _quoted(_EXAMPLES)  # [received-example, used-example]
    receipt = material_examples[:1]
    usage = material_examples[1:2] or material_examples[:1]
    return {
        "material.receipt": receipt,
        "material.usage": usage,
        "equipment.usage": _quoted(_CATEGORY_PROMPTS.get("cat_equipment", "")),
        "labour.attendance": _quoted(_CATEGORY_PROMPTS.get("cat_labour", "")),
        "expense.submit": _quoted(_CATEGORY_PROMPTS.get("cat_expense", "")),
        "site.update": ["Concrete pour finished on the 3rd floor"],
    }


def _workflow_node_names(graph: object | None) -> list[str]:
    """Node ids of a compiled LangGraph, minus the synthetic start/end."""
    if graph is None:
        return []
    try:
        nodes = graph.get_graph().nodes  # type: ignore[attr-defined]
        return [n for n in nodes if n not in ("__start__", "__end__")]
    except Exception:  # noqa: BLE001
        return []


# ---------------------------------------------------------------------------
# Pipeline map (structured)
# ---------------------------------------------------------------------------
def _build_stages() -> list[PipelineStage]:
    """The four pipeline stages as structured, clickable nodes."""
    from canonicalization.mapping import REQUIRED_FIELDS
    from mesiri_contracts.assistant.canonical_event import CanonicalEventType
    from mesiri_contracts.assistant.planner_decision import PlannerDecisionType

    understanding = PipelineStage(
        key="understanding",
        title="1 · Understanding",
        summary="Turns any message into text + structured fields. The path depends on modality.",
        nodes=[
            StageNode(id="text", label="Text / interactive", description="Straight to extraction."),
            StageNode(id="voice", label="Voice", description="Speech-to-text + translation, then extraction."),
            StageNode(id="media", label="Image / document", description="Vision (OCR / description), then extraction."),
            StageNode(id="extraction", label="Structured extraction", description="LLM pulls fields (material, quantity, amount…) and a semantic type."),
        ],
    )
    canonicalization = PipelineStage(
        key="canonicalization",
        title="2 · Canonicalization",
        summary="Maps the understood message to one canonical business event and checks required fields.",
        nodes=[
            StageNode(
                id=event.value,
                label=event.value,
                description=("needs: " + ", ".join(REQUIRED_FIELDS.get(event, ())))
                if REQUIRED_FIELDS.get(event)
                else "no required fields",
            )
            for event in CanonicalEventType
        ],
    )
    planner = PipelineStage(
        key="planner",
        title="3 · Planner",
        summary="Decides what to do with the event.",
        nodes=[
            StageNode(id=d.value, label=d.value, description=_PLANNER_DECISION_DOC.get(d.value, ""))
            for d in PlannerDecisionType
        ],
    )
    workflows = PipelineStage(
        key="workflows",
        title="4 · Workflows",
        summary="START_WORKFLOW events run a LangGraph that drafts a record and asks the user to confirm.",
        nodes=[
            StageNode(id=key, label=title, description="")
            for key, title in _WORKFLOW_TITLES.items()
        ],
    )
    return [understanding, canonicalization, planner, workflows]


_PLANNER_DECISION_DOC: dict[str, str] = {
    "start_workflow": "Run the matching workflow (only material is built today).",
    "clarify": "Ask the user for the missing required fields.",
    "direct_reply": "Answer directly — greetings, questions, unrecognized.",
    "ignore": "Do nothing (rare — e.g. system noise).",
}


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

    lines += [
        '  subgraph Understanding["1 · Understanding"]',
        "    msg([WhatsApp message])",
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


def _workflow_infos() -> list[WorkflowGraphInfo]:
    """Structured, drill-down info per workflow key."""
    from canonicalization.mapping import (
        _MATERIAL_DIRECTION_EVENT_TYPE,
        _SIMPLE_EVENT_TYPE,
        REQUIRED_FIELDS,
    )
    from channel.replies import _FIELD_LABELS
    from mesiri_contracts.assistant.canonical_event import CanonicalEventType
    from mesiri_contracts.assistant.enums import SemanticType
    from mesiri_contracts.assistant.planner_decision import WorkflowKey
    from planner.routing import WORKFLOW_KEY_BY_EVENT
    from workflows.registry import _BUILDERS, WorkflowRegistry

    # Reverse the routing table: workflow key -> canonical event.
    event_by_key = {key: event for event, key in WORKFLOW_KEY_BY_EVENT.items()}
    # Canonical event -> semantic type (best-effort, for display only).
    semantic_by_event: dict[CanonicalEventType, SemanticType] = {
        e: s for s, e in _SIMPLE_EVENT_TYPE.items()
    }
    for e in _MATERIAL_DIRECTION_EVENT_TYPE.values():
        semantic_by_event[e] = SemanticType.MATERIAL_UPDATE

    examples = _example_messages_by_workflow()
    registry = WorkflowRegistry()

    infos: list[WorkflowGraphInfo] = []
    for key in WorkflowKey:
        implemented = key in _BUILDERS
        event = event_by_key.get(key)
        semantic = semantic_by_event.get(event) if event else None
        req = list(REQUIRED_FIELDS.get(event, ())) if event else []

        mermaid: str | None = None
        graph = None
        try:
            graph = registry.get_graph(key)
            if graph is not None:
                mermaid = graph.get_graph().draw_mermaid()
        except Exception:  # noqa: BLE001 — langgraph optional; degrade to status-only
            pass

        infos.append(
            WorkflowGraphInfo(
                workflow_key=key.value,
                title=_WORKFLOW_TITLES.get(key.value, key.value),
                implemented=implemented,
                canonical_event=event.value if event else None,
                semantic_type=semantic.value if semantic else None,
                required_fields=req,
                required_field_labels=[_FIELD_LABELS.get(f, f.replace("_", " ")) for f in req],
                node_names=_workflow_node_names(graph),
                example_messages=examples.get(key.value, []),
                mermaid=mermaid,
            )
        )
    return infos


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@router.get("", response_model=SystemGraphResponse)
async def get_system_graph(_admin: dict = Depends(require_platform_admin)):
    return SystemGraphResponse(
        mermaid=_build_pipeline_mermaid(),
        stages=_build_stages(),
        workflows=_workflow_infos(),
    )


async def _lookup_user_wa_id(org_id: uuid.UUID, user_id: uuid.UUID) -> str:
    """Resolve the chosen user's registered WhatsApp number (the pipeline keys
    identity off it). Raises HTTPException if the user is missing or unregistered."""
    import sqlalchemy as sa

    from admin.router import get_engine, users_table

    engine = get_engine()
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(users_table.c.whatsapp_number).where(
                sa.and_(users_table.c.id == user_id, users_table.c.organization_id == org_id)
            )
        )
        row = result.first()
    if row is None:
        raise HTTPException(status_code=404, detail="User not found in that organization")
    if not row.whatsapp_number:
        raise HTTPException(
            status_code=400,
            detail="That user has no WhatsApp number on file, so a message can't be simulated as them.",
        )
    return str(row.whatsapp_number)


@router.post("/simulate", response_model=SimulateResponse)
async def simulate_message(
    body: SimulateRequest,
    request: Request,
    _admin: dict = Depends(require_platform_admin),
):
    """Run one message through the real pipeline as the chosen user, capturing the
    reply instead of sending it to WhatsApp. Side-effect-free (no confirmation is
    auto-sent, so nothing is persisted)."""
    from mesiri_contracts.assistant.enums import InputModality
    from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
    from mesiri_contracts.common.ids import new_id
    from runtime.dependencies import get_container
    from runtime.inbound_journey import process_inbound_message

    try:
        modality = InputModality(body.modality)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Unsupported modality: {body.modality}") from None
    if modality not in (InputModality.TEXT, InputModality.INTERACTIVE):
        raise HTTPException(
            status_code=400,
            detail="Only text simulation is supported for now (voice/image need media upload).",
        )

    wa_id = await _lookup_user_wa_id(body.organization_id, body.user_id)

    container = get_container(request)

    message = NormalizedMessage(
        message_id=new_id("sim"),
        sender=SenderInfo(wa_id=wa_id, phone_number=wa_id),
        timestamp=datetime.now(UTC),
        modality=modality,
        text=body.text,
        metadata={"simulated": True},
    )

    captured: list[str] = []

    async def _capture_text(_to: str, text: str) -> None:
        captured.append(text)

    async def _capture_list(_to: str, body: str, button_label: str, rows) -> None:  # noqa: ARG001
        options = "\n".join(f"  • {getattr(r, 'title', r)}" for r in rows)
        captured.append(f"{body}\n{options}")

    result = await process_inbound_message(
        message,
        actor_user_id=str(body.user_id),
        pipeline=container.pipeline,
        context_resolver=container.context_resolver,
        planner=container.planner,
        workflow_runtime=container.workflow_runtime,
        interaction_handler=container.interaction_handler,
        send_text=_capture_text,
        send_list=_capture_list,
        context_debug=False,
        # No loggers: this is a dry run, not a real inbound message.
    )

    def _dump(obj) -> dict | None:
        return obj.model_dump(mode="json") if obj is not None else None

    return SimulateResponse(
        dry_run=True,
        ran_as_wa_id=wa_id,
        replies=captured,
        understanding=_dump(result.understanding),
        resolved_context=_dump(result.resolved_context),
        canonical_event=_dump(result.canonical_event),
        planner_decision=_dump(result.planner_decision),
        workflow_run={
            "status": result.workflow_run.status.value,
            "workflow_key": result.workflow_run.workflow_key.value,
            "workflow_instance_id": result.workflow_run.workflow_instance_id,
        }
        if result.workflow_run is not None
        else None,
    )
