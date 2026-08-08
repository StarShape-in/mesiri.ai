"""Unit tests for adding an unknown material to the catalog from WhatsApp
(STA-139) — the create offer inside _run_material_unit_gates plus the two
resume functions it hands off to.

Real problem this fixes: a material name matching nothing in the catalog
dead-ended with "ask your admin to add it first" and the report was
discarded, so the user had to retype it once an admin added the entry.

Whether a sender may create is governed by the org's own
whatsapp_material_create_roles setting, so the role check is covered here
too — an org that hasn't granted a role must keep the old behaviour exactly.
Fakes only: no live DB, no HTTP, no AI providers.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from interactions.pending_report import PendingReportStore
from mesiri_contracts.assistant.canonical_event import (
    CanonicalEventType,
    IntentCompleteness,
)
from mesiri_contracts.assistant.enums import InputModality
from mesiri_contracts.assistant.normalized_message import NormalizedMessage, SenderInfo
from mesiri_contracts.assistant.v2.canonical_event import CanonicalEventV2
from planner import Planner
from runtime.inbound_journey import (
    _run_material_unit_gates,
    resume_pending_report_with_material,
    resume_pending_report_with_material_create,
    resume_pending_report_with_material_unit_choice,
)
from workflows import WorkflowRunResult, WorkflowRunStatus, WorkflowRuntime
from workflows.fakes import FakeWorkflowInstanceRepository, FakeWorkflowRegistry

ORG = "11111111-1111-4111-8111-111111111111"
USR = "22222222-2222-4222-8222-222222222222"
PRJ = "33333333-3333-4333-8333-333333333333"

BAGS_ID = str(uuid.uuid4())


class _FakeRedis:
    def __init__(self) -> None:
        self._store: dict[str, Any] = {}

    def namespaced(self, *parts: str) -> str:
        return ":".join(parts)

    async def set_json(self, key: str, value: Any, *, ttl_seconds: int | None = None) -> None:
        self._store[key] = value

    async def get_json(self, key: str) -> Any | None:
        return self._store.get(key)


def _pending_store() -> PendingReportStore:
    return PendingReportStore(_FakeRedis())


class _ActorStub:
    """Only `role` is read by the "None of these" leg's create check."""

    def __init__(self, role: str) -> None:
        self.role = role
        self.user_id = USR
        self.organization_id = ORG


class _FakeOrgSettings:
    """Stand-in for OrganizationSettingsQueryService returning a canned
    allowed-roles list."""

    def __init__(self, allowed: Any) -> None:
        self._allowed = allowed

    async def get(self, *, organization_id: str, key: str) -> Any:
        return self._allowed


class _FakeCatalogQuery:
    def __init__(
        self,
        *,
        find_materials_result: list[dict[str, Any]] | None = None,
        list_active_result: list[dict[str, Any]] | None = None,
        resolve_unit_result: dict[str, Any] | None = None,
        get_unit_result: dict[str, Any] | None = None,
        units: list[dict[str, Any]] | None = None,
        created: dict[str, Any] | None = None,
    ) -> None:
        self._find = find_materials_result or []
        self._list_active = list_active_result or []
        self._resolve_unit = resolve_unit_result
        self._get_unit = get_unit_result
        self._units = units or []
        self._created = created
        self.create_calls: list[dict[str, Any]] = []

    async def find_materials(self, *, organization_id: str, name: str) -> list[dict[str, Any]]:
        return self._find

    async def list_active_materials(self, *, organization_id: str) -> list[dict[str, Any]]:
        return self._list_active

    async def get_material(self, *, organization_id: str, material_id: str):
        return None

    async def resolve_unit(self, text: str) -> dict[str, Any] | None:
        return self._resolve_unit

    async def get_unit(self, unit_id: str) -> dict[str, Any] | None:
        return self._get_unit

    async def list_units(self) -> list[dict[str, Any]]:
        return self._units

    async def create_material(
        self, *, organization_id: str, name: str, unit_id: str, created_by: str
    ) -> dict[str, Any] | None:
        self.create_calls.append(
            {"name": name, "unit_id": unit_id, "created_by": created_by}
        )
        return self._created


def _event(*, material_name: str = "Fevicol", unit: str | None = "bags") -> CanonicalEventV2:
    fields: dict[str, Any] = {"material_name": material_name, "quantity": 50}
    if unit is not None:
        fields["unit"] = unit
    return CanonicalEventV2(
        event_id="evt_1",
        correlation_id="cor_1",
        source_message_id="msg_1",
        event_type=CanonicalEventType.MATERIAL_RECEIPT_REQUESTED,
        completeness=IntentCompleteness.ACTIONABLE,
        organization_id=ORG,
        user_id=USR,
        project_id=PRJ,
        fields=fields,
    )


# ---------------------------------------------------------------------------
# The gate: when is the create offer shown at all
# ---------------------------------------------------------------------------


async def test_unmatched_name_offers_to_create_for_allowed_role():
    """The reported name matched nothing and the sender's role is in the org's
    allowed list -> offer to add it, holding the report for the tap."""
    catalog = _FakeCatalogQuery(find_materials_result=[])
    store = _pending_store()

    reply = await _run_material_unit_gates(
        _event(),
        catalog_query=catalog,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="PROJECT_MANAGER",
        org_settings_query=_FakeOrgSettings(["ADMIN", "PROJECT_MANAGER"]),
    )

    assert reply is not None
    assert reply.buttons is not None
    assert [b.id for b in reply.buttons] == ["matnew_yes", "matnew_no"]
    assert "Fevicol" in reply.text

    assert await store.pop_pending(user_id=USR) is not None


async def test_unmatched_name_falls_back_to_old_behaviour_for_disallowed_role():
    """A role the org has NOT granted must keep the pre-STA-139 behaviour --
    the whole-catalog picker, never the create offer."""
    other_id = str(uuid.uuid4())
    catalog = _FakeCatalogQuery(
        find_materials_result=[],
        list_active_result=[
            {"id": other_id, "name": "Cement", "is_active": True, "default_unit_id": None}
        ],
    )
    store = _pending_store()

    reply = await _run_material_unit_gates(
        _event(),
        catalog_query=catalog,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="SITE_ENGINEER",
        org_settings_query=_FakeOrgSettings(["ADMIN", "PROJECT_MANAGER"]),
    )

    assert reply is not None
    assert reply.buttons is None, "a disallowed role must not get create buttons"
    assert reply.list_rows is not None
    assert all(r.id.startswith("mat_") for r in reply.list_rows)


async def test_unmatched_name_and_empty_catalog_still_dead_ends_for_disallowed_role():
    catalog = _FakeCatalogQuery(find_materials_result=[], list_active_result=[])
    store = _pending_store()

    reply = await _run_material_unit_gates(
        _event(),
        catalog_query=catalog,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="SITE_ENGINEER",
        org_settings_query=_FakeOrgSettings(["ADMIN"]),
    )

    assert reply is not None
    assert reply.buttons is None
    assert reply.list_rows is None
    assert "couldn't find" in reply.text.lower()


async def test_no_settings_service_denies_creation():
    """Nothing wired -> deny rather than fall back to the spec default: an
    unresolved capability must not be granted implicitly."""
    catalog = _FakeCatalogQuery(find_materials_result=[], list_active_result=[])
    store = _pending_store()

    reply = await _run_material_unit_gates(
        _event(),
        catalog_query=catalog,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="ADMIN",
        org_settings_query=None,
    )

    assert reply is not None
    assert reply.buttons is None, "no settings service must not grant create"


async def test_ambiguous_name_still_shows_picker_not_create_offer():
    """More than one real match is ambiguity, not absence -- the picker must
    still win over the create offer."""
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    catalog = _FakeCatalogQuery(
        find_materials_result=[
            {"id": a, "name": "OPC Cement", "is_active": True, "default_unit_id": None},
            {"id": b, "name": "PPC Cement", "is_active": True, "default_unit_id": None},
        ]
    )
    store = _pending_store()

    reply = await _run_material_unit_gates(
        _event(material_name="cement"),
        catalog_query=catalog,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="ADMIN",
        org_settings_query=_FakeOrgSettings(["ADMIN"]),
    )

    assert reply is not None
    assert reply.list_rows is not None
    assert reply.buttons is None


# ---------------------------------------------------------------------------
# The resume legs
# ---------------------------------------------------------------------------


def _tap(row_id: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id="wamid.tap.1",
        correlation_id="cor_resume_1",
        sender=SenderInfo(wa_id="wa_engineer", profile_name="Engineer"),
        timestamp=datetime(2026, 7, 25, 10, 0, tzinfo=UTC),
        modality=InputModality.INTERACTIVE,
        metadata={"interactive_reply_id": row_id},
    )


class _RecordingWorkflowRuntime(WorkflowRuntime):
    def __init__(self) -> None:
        super().__init__(registry=FakeWorkflowRegistry(), repo=FakeWorkflowInstanceRepository())
        self.started_with: CanonicalEventV2 | None = None

    async def start(self, decision, event):  # type: ignore[override]
        self.started_with = event
        return WorkflowRunResult(
            status=WorkflowRunStatus.COMPLETED,
            workflow_key=decision.workflow_key,
            workflow_instance_id="wf_test",
            correlation_id=event.correlation_id,
            pending_prompt="ok",
        )


def _created_row(name: str = "Fevicol") -> dict[str, Any]:
    return {"id": str(uuid.uuid4()), "name": name, "default_unit_id": BAGS_ID}


async def test_yes_with_known_unit_creates_without_asking_again():
    """"50 bags of Fevicol" already carried a resolvable unit, so tapping Yes
    must create straight away -- no extra unit-picker turn."""
    catalog = _FakeCatalogQuery(
        resolve_unit_result={"id": BAGS_ID, "code": "bag", "display_name": "Bags"},
        created=_created_row(),
    )
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event(unit="bags"))
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_material_create(
        _tap("matnew_yes"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert len(catalog.create_calls) == 1
    assert catalog.create_calls[0]["name"] == "Fevicol"
    assert catalog.create_calls[0]["unit_id"] == BAGS_ID
    assert "Added Fevicol" in reply.text
    assert runtime.started_with is not None, "the held report must continue, not be dropped"
    assert runtime.started_with.fields["unit"] == "Bags"


async def test_yes_without_usable_unit_asks_for_one_and_does_not_create_yet():
    catalog = _FakeCatalogQuery(
        resolve_unit_result=None,
        units=[
            {"id": BAGS_ID, "code": "bag", "display_name": "Bags"},
            {"id": str(uuid.uuid4()), "code": "kg", "display_name": "Kilograms"},
        ],
    )
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event(unit=None))
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_material_create(
        _tap("matnew_yes"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert reply.list_rows is not None
    assert all(r.id.startswith("matunit_") for r in reply.list_rows)
    assert catalog.create_calls == [], "nothing may be created before a unit is chosen"
    assert runtime.started_with is None
    assert await store.pop_pending(user_id=USR) is not None, "report must be re-held for the tap"


async def test_no_declines_with_typo_nudge_and_creates_nothing():
    catalog = _FakeCatalogQuery()
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event())
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_material_create(
        _tap("matnew_no"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert "spelling" in reply.text.lower()
    assert catalog.create_calls == []
    assert runtime.started_with is None
    assert await store.pop_pending(user_id=USR) is None


async def test_unit_pick_creates_material_and_continues_report():
    catalog = _FakeCatalogQuery(
        get_unit_result={"id": BAGS_ID, "code": "bag", "display_name": "Bags"},
        created=_created_row(),
    )
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event(unit=None))
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_material_unit_choice(
        _tap(f"matunit_{BAGS_ID}"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert len(catalog.create_calls) == 1
    assert catalog.create_calls[0]["unit_id"] == BAGS_ID
    assert runtime.started_with is not None
    assert runtime.started_with.fields["unit"] == "Bags"
    assert runtime.started_with.fields.get("material_id")


async def test_create_failure_reports_instead_of_dropping_the_reply():
    """create_material returning None (bad unit, DB trouble) must still
    answer -- a message that gets no reply is indistinguishable from Mesiri
    being down."""
    catalog = _FakeCatalogQuery(
        resolve_unit_result={"id": BAGS_ID, "code": "bag", "display_name": "Bags"},
        created=None,
    )
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event(unit="bags"))
    runtime = _RecordingWorkflowRuntime()

    reply = await resume_pending_report_with_material_create(
        _tap("matnew_yes"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=runtime,
    )

    assert reply is not None
    assert "couldn't add" in reply.text.lower()
    assert runtime.started_with is None


# ---------------------------------------------------------------------------
# A lone substring match no longer auto-resolves, and the picker it produces
# has a way out (ENTITY_RESOLUTION_PLAN.md §5.1). Together these are one
# change: the picker escape is what makes asking safe instead of cornering.
# ---------------------------------------------------------------------------


async def test_lone_substring_match_asks_rather_than_resolving_silently():
    """"cement" against a catalog holding only "Cement Paint" used to record
    Cement Paint silently. It must ask now."""
    paint_id = str(uuid.uuid4())
    catalog = _FakeCatalogQuery(
        find_materials_result=[
            {"id": paint_id, "name": "Cement Paint", "is_active": True, "default_unit_id": None}
        ]
    )
    event = _event(material_name="cement")
    store = _pending_store()

    reply = await _run_material_unit_gates(
        event,
        catalog_query=catalog,
        pending_report_store=store,
        actor_user_id=USR,
        actor_role="ADMIN",
        org_settings_query=_FakeOrgSettings(["ADMIN"]),
    )

    assert reply is not None
    assert reply.list_rows is not None
    assert "material_id" not in event.fields, "a substring guess must not be auto-filled"
    assert [r.id for r in reply.list_rows] == [f"mat_{paint_id}", "mat_none"]
    assert await store.pop_pending(user_id=USR) is not None


async def test_exact_match_still_resolves_without_asking():
    """The fast path everyone relies on must not regress into a picker."""
    cement_id = str(uuid.uuid4())
    catalog = _FakeCatalogQuery(
        find_materials_result=[
            {"id": cement_id, "name": "Cement", "is_active": True, "default_unit_id": None}
        ]
    )
    event = _event(material_name="cement")

    reply = await _run_material_unit_gates(
        event,
        catalog_query=catalog,
        pending_report_store=_pending_store(),
        actor_user_id=USR,
        actor_role="ADMIN",
        org_settings_query=_FakeOrgSettings(["ADMIN"]),
    )

    assert reply is None, "an exact match must sail through the gate"
    assert event.fields["material_id"] == cement_id


async def test_picker_always_offers_a_way_out():
    from channel.replies import MATERIAL_CANDIDATE_NONE_ROW_ID, render_material_picker

    spec = render_material_picker([(str(uuid.uuid4()), "Cement Paint")])
    assert spec.list_rows[-1].id == MATERIAL_CANDIDATE_NONE_ROW_ID
    assert spec.list_rows[-1].title == "None of these"


async def test_picker_stays_within_whatsapps_ten_row_cap_with_the_escape():
    from channel.replies import render_material_picker

    spec = render_material_picker([(str(uuid.uuid4()), f"Material {i}") for i in range(20)])
    assert len(spec.list_rows) == 10, "9 candidates + the escape row"
    assert spec.list_rows[-1].id == "mat_none"


async def test_none_of_these_offers_to_create_when_the_org_allows_it():
    catalog = _FakeCatalogQuery()
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event(material_name="Fevicol"))

    reply = await resume_pending_report_with_material(
        _tap("mat_none"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=_RecordingWorkflowRuntime(),
        actor=_ActorStub(role="PROJECT_MANAGER"),
        org_settings_query=_FakeOrgSettings(["ADMIN", "PROJECT_MANAGER"]),
    )

    assert reply is not None
    assert reply.buttons is not None
    assert [b.id for b in reply.buttons] == ["matnew_yes", "matnew_no"]
    assert "Fevicol" in reply.text
    # Re-held so the create tap that follows still has the report.
    assert await store.pop_pending(user_id=USR) is not None


async def test_none_of_these_dead_ends_honestly_when_creation_is_not_allowed():
    catalog = _FakeCatalogQuery()
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event(material_name="Fevicol"))

    reply = await resume_pending_report_with_material(
        _tap("mat_none"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=_RecordingWorkflowRuntime(),
        actor=_ActorStub(role="SITE_ENGINEER"),
        org_settings_query=_FakeOrgSettings(["ADMIN"]),
    )

    assert reply is not None
    assert reply.buttons is None
    assert "couldn't find" in reply.text.lower()
    assert await store.pop_pending(user_id=USR) is None, "the report is dropped, not left dangling"


async def test_unrelated_tap_falls_through_without_consuming_the_report():
    catalog = _FakeCatalogQuery()
    store = _pending_store()
    await store.set_pending(user_id=USR, event=_event())

    reply = await resume_pending_report_with_material_create(
        _tap("confirm_yes"),
        USR,
        pending_report_store=store,
        catalog_query=catalog,
        planner=Planner(),
        workflow_runtime=_RecordingWorkflowRuntime(),
    )

    assert reply is None
    assert await store.pop_pending(user_id=USR) is not None
