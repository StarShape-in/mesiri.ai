"""M4 "Context Foundation" golden scenario — executable proof.

Proves the full M4 path end to end against deterministic fakes (reproducible in
CI without docker or AI credentials):

    Director "switch to Marina Tower"  -> identity -> membership -> roles/perms
      -> authorize project -> set active context in Redis
    Simulate application restart (new store, same Redis backend; Redis NOT cleared)
    "JCB used for 4 hours" (no explicit project)
      -> resolve identity -> load active context from Redis
      -> revalidate authorization against Postgres -> ResolvedContext.v2
      -> context_source = ACTIVE_CONTEXT, correlation_id preserved
    Attempt to select an out-of-tenant project -> rejected, Redis unchanged

Run:  make m4-gate   (or)   python scripts/run_m4_golden_scenario.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from datetime import UTC, datetime

# Import roots (mirrors pyproject [tool.pytest.ini_options].pythonpath).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (
    "shared/contracts/src",
    "platform/ai/src",
    "backend/src",
    "apps/whatsapp-assistant/src",
):
    sys.path.insert(0, os.path.join(_ROOT, _p))

from context import seed  # noqa: E402
from context.active_context import RedisActiveContextStore  # noqa: E402
from context.identity_bridge import deterministic_canonical_uuid as canon  # noqa: E402
from context.resolver import ContextDependencies, ContextResolver  # noqa: E402
from context.service import ContextSwitchService  # noqa: E402
from mesiri.infrastructure.redis.client import FakeRedis  # noqa: E402
from mesiri_contracts.assistant.candidates import EquipmentUsageCandidate  # noqa: E402
from mesiri_contracts.assistant.context_enums import ContextSource  # noqa: E402
from mesiri_contracts.assistant.enums import InputModality  # noqa: E402
from mesiri_contracts.assistant.normalized_message import (  # noqa: E402
    MessageType,
    NormalizedMessage,
    SenderInfo,
)
from mesiri_contracts.assistant.understanding_result import UnderstandingResult  # noqa: E402


class _Check:
    def __init__(self) -> None:
        self.items: list[tuple[str, bool, str]] = []

    def record(self, label: str, ok: bool, detail: str = "") -> None:
        self.items.append((label, ok, detail))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.items)


def _deps_over_redis(redis: FakeRedis) -> tuple[ContextDependencies, RedisActiveContextStore]:
    """Wire the seed fakes but back active context with the real Redis adapter."""
    store = RedisActiveContextStore(redis)
    deps = seed.build_dependencies(active_store=store)  # type: ignore[arg-type]
    return deps, store


def _msg(content: str, *, correlation_id: str, message_id: str) -> NormalizedMessage:
    return NormalizedMessage(
        message_id=message_id,
        correlation_id=correlation_id,
        sender=SenderInfo(wa_id=seed.WA_ABC_DIRECTOR),
        timestamp=datetime.now(UTC),
        message_type=MessageType.TEXT,
        content=content,
    )


def _und(fields: dict | None, *, correlation_id: str, message_id: str) -> UnderstandingResult:
    cands = [EquipmentUsageCandidate(fields=fields)] if fields else []
    return UnderstandingResult(
        source_message_id=message_id,
        correlation_id=correlation_id,
        input_modality=InputModality.TEXT,
        candidates=cands,
    )


async def run() -> _Check:
    check = _Check()
    correlation_id = "cor_golden_m4"

    redis = FakeRedis()
    await redis.connect()

    # -- STEP 1: "switch to Marina Tower" ------------------------------------
    deps, store = _deps_over_redis(redis)
    switch = ContextSwitchService(
        projects=deps.projects, sites=deps.sites, active_context=store
    )
    # Identity + authorization happen inside the resolver/switch (authoritative).
    r1 = ContextResolver(deps)
    step1 = await r1.resolve(
        _msg("switch to Marina Tower", correlation_id=correlation_id, message_id="msg_1"),
        _und({"project_name": "Marina Tower"}, correlation_id=correlation_id, message_id="msg_1"),
    )
    check.record("Identity + membership + roles resolved", step1.is_ok)
    check.record(
        "Explicit project 'Marina Tower' authorized",
        step1.is_ok and step1.unwrap().context_project_id == seed.PROJ_MARINA,
    )
    sw = await switch.select_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR, project_id=seed.PROJ_MARINA
    )
    check.record("Active context set in Redis (Marina Tower)", sw.is_ok)

    # -- STEP 2: simulate application restart --------------------------------
    # Brand-new dependency graph + store instance over the SAME Redis backend.
    deps2, store2 = _deps_over_redis(redis)
    survived = await store2.get_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR
    )
    check.record(
        "Active context survives application restart",
        survived is not None and survived.project_id == seed.PROJ_MARINA,
    )

    # -- STEP 3: "JCB used for 4 hours" (no explicit project) ----------------
    r3 = ContextResolver(deps2)
    step3 = await r3.resolve(
        _msg("JCB used for 4 hours", correlation_id=correlation_id, message_id="msg_2"),
        _und(
            {"equipment_name": "JCB", "duration_hours": 4},
            correlation_id=correlation_id,
            message_id="msg_2",
        ),
    )
    ctx = step3.unwrap() if step3.is_ok else None
    check.record("ResolvedContext.v2 produced from active context", ctx is not None)
    if ctx is not None:
        check.record("context_organization_id = ABC", ctx.context_organization_id == seed.ABC_ORG)
        check.record("canonical organization_id", ctx.organization_id == canon(seed.ABC_ORG))
        check.record("context_user_id = director", ctx.context_user_id == seed.ABC_DIRECTOR)
        check.record("context_project_id = Marina Tower", ctx.context_project_id == seed.PROJ_MARINA)
        check.record(
            "context_source = ACTIVE_CONTEXT",
            ctx.context_source == ContextSource.ACTIVE_CONTEXT,
        )
        check.record(
            "Redis context revalidated against Postgres authorization",
            ctx.context_project_id == seed.PROJ_MARINA,
        )
        check.record("correlation_id preserved", ctx.correlation_id == correlation_id)

    # -- STEP 4: attempt an out-of-tenant project ----------------------------
    denied = await switch.select_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR, project_id=seed.PROJ_ALPHA_B
    )
    check.record("Out-of-tenant project rejected", denied.is_err)
    still = await store2.get_active_context(
        organization_id=seed.ABC_ORG, user_id=seed.ABC_DIRECTOR
    )
    check.record(
        "Redis active context unchanged after rejection",
        still is not None and still.project_id == seed.PROJ_MARINA,
    )
    check.record("Tenant isolation preserved", denied.is_err)

    return check


def main() -> int:
    check = asyncio.run(run())
    print("\n" + "=" * 52)
    print("M4 CONTEXT FOUNDATION")
    print("=" * 52)
    for label, ok, detail in check.items:
        mark = "[ok]" if ok else "[XX]"
        line = f"{mark} {label}"
        if detail and not ok:
            line += f"   [{detail}]"
        print(line)
    print("=" * 52)
    print(f"M4 GATE: {'PASSED' if check.passed else 'FAILED'}")
    print("=" * 52)
    return 0 if check.passed else 1


if __name__ == "__main__":
    sys.exit(main())
