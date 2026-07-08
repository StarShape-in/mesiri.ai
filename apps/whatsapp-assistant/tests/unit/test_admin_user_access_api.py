from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from projects import router as projects_router
from users.router import AccessPolicy, _validate_access_policy


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def first(self):
        return self._rows[0] if self._rows else None

    def fetchall(self):
        return self._rows


class _Conn:
    def __init__(self, results):
        self._results = list(results)

    async def execute(self, _statement):
        return _Result(self._results.pop(0))


class _ConnectContext:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, exc_type, exc, tb):
        return None


class _Engine:
    def __init__(self, conn):
        self._conn = conn

    def connect(self):
        return _ConnectContext(self._conn)


@pytest.mark.asyncio
async def test_list_project_sites_returns_org_scoped_sites(monkeypatch):
    project_id = uuid.uuid4()
    site_id = uuid.uuid4()
    conn = _Conn(
        [
            [SimpleNamespace(id=project_id)],
            [
                SimpleNamespace(
                    id=site_id,
                    project_id=project_id,
                    name="Tower A",
                    status="active",
                )
            ],
        ]
    )
    monkeypatch.setattr(projects_router, "get_engine", lambda: _Engine(conn))

    sites = await projects_router.list_project_sites(project_id, {"org": str(uuid.uuid4())})

    assert len(sites) == 1
    assert sites[0].id == site_id
    assert sites[0].project_id == project_id
    assert sites[0].name == "Tower A"


@pytest.mark.asyncio
async def test_list_project_sites_rejects_project_outside_org(monkeypatch):
    conn = _Conn([[]])
    monkeypatch.setattr(projects_router, "get_engine", lambda: _Engine(conn))

    with pytest.raises(HTTPException) as exc:
        await projects_router.list_project_sites(uuid.uuid4(), {"org": str(uuid.uuid4())})

    assert exc.value.status_code == 404


@pytest.mark.asyncio
async def test_validate_access_policy_accepts_matching_project_sites():
    project_id = uuid.uuid4()
    site_id = uuid.uuid4()
    conn = _Conn(
        [
            [SimpleNamespace(id=project_id)],
            [SimpleNamespace(id=site_id, project_id=project_id)],
        ]
    )
    policy = AccessPolicy(
        mode="custom_projects",
        projects=[
            {
                "projectId": str(project_id),
                "siteAccess": {"mode": "custom_sites", "siteIds": [str(site_id)]},
            }
        ],
    )

    await _validate_access_policy(conn, str(uuid.uuid4()), policy)


@pytest.mark.asyncio
async def test_validate_access_policy_rejects_unknown_project():
    policy = AccessPolicy(
        mode="custom_projects",
        projects=[
            {
                "projectId": str(uuid.uuid4()),
                "siteAccess": {"mode": "all_sites"},
            }
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await _validate_access_policy(_Conn([[]]), str(uuid.uuid4()), policy)

    assert exc.value.status_code == 400
    assert "unknown project" in exc.value.detail


@pytest.mark.asyncio
async def test_validate_access_policy_rejects_site_from_different_project():
    project_id = uuid.uuid4()
    other_project_id = uuid.uuid4()
    site_id = uuid.uuid4()
    conn = _Conn(
        [
            [SimpleNamespace(id=project_id)],
            [SimpleNamespace(id=site_id, project_id=other_project_id)],
        ]
    )
    policy = AccessPolicy(
        mode="custom_projects",
        projects=[
            {
                "projectId": str(project_id),
                "siteAccess": {"mode": "custom_sites", "siteIds": [str(site_id)]},
            }
        ],
    )

    with pytest.raises(HTTPException) as exc:
        await _validate_access_policy(conn, str(uuid.uuid4()), policy)

    assert exc.value.status_code == 400
    assert "outside project" in exc.value.detail
