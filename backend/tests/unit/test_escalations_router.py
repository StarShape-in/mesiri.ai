"""Escalations router (#10 Human Review) -- route shape only.

Pure metadata check, no live DB and no app construction: verifies the
expected paths/methods exist on the router. The actual query logic lives in
PostgresEscalationRepository (Postgres-only, no unit coverage here -- same
scoping as this session's other Postgres-only work with no live DB on the
authoring machine).
"""

from __future__ import annotations

from mesiri.domains.escalations.router import router


def _route_map() -> dict[str, set[str]]:
    routes: dict[str, set[str]] = {}
    for route in router.routes:
        routes.setdefault(route.path, set()).update(route.methods)
    return routes


def test_router_is_prefixed_and_tagged():
    assert router.prefix == "/escalations"
    assert "escalations" in router.tags


def test_list_pending_route_exists():
    routes = _route_map()
    assert "/escalations" in routes
    assert "GET" in routes["/escalations"]


def test_get_one_route_exists():
    routes = _route_map()
    assert "/escalations/{escalation_id}" in routes
    assert "GET" in routes["/escalations/{escalation_id}"]


def test_resolve_route_exists():
    routes = _route_map()
    assert "/escalations/{escalation_id}/resolve" in routes
    assert "POST" in routes["/escalations/{escalation_id}/resolve"]
