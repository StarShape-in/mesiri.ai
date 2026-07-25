"""Unit tests for assigning user access from the control panel.

Two surfaces now grant project/site access: the web dashboard (tenant admin,
org from the JWT) and the control panel (platform admin, org from the path).
They must apply identical rules, because the result decides which project a
WhatsApp report is filed against and what the dashboard permits.

The rules live once in users/access_service.py; these tests pin the parts
that would be dangerous to get wrong — cross-tenant grants, and the
all_projects bypass writing no membership rows.

Fakes only: no live DB.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from users.access_service import (
    ALL_PROJECTS,
    CUSTOM_PROJECTS,
    AccessPolicy,
    apply_access_policy,
    validate_access_policy,
)

ORG = uuid.uuid4()
OTHER_ORG = uuid.uuid4()
USER = uuid.uuid4()
PROJECT = uuid.uuid4()
SITE = uuid.uuid4()


class _Row:
    def __init__(self, **kw):
        self.__dict__.update(kw)


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows

    def first(self):
        return self._rows[0] if self._rows else None


class _FakeConn:
    """Records executed statements and replays canned SELECT results."""

    def __init__(self, results: list[list]) -> None:
        self._results = list(results)
        self.statements: list[str] = []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append(sql)
        if sql.strip().upper().startswith("SELECT"):
            return _Result(self._results.pop(0) if self._results else [])
        return _Result([])

    def sql_of_type(self, verb: str) -> list[str]:
        return [s for s in self.statements if s.strip().upper().startswith(verb)]


# ---------------------------------------------------------------------------
# Validation — the cross-tenant guard
# ---------------------------------------------------------------------------


async def test_rejects_a_project_from_another_organization():
    """The control panel passes org_id from the URL, so without this a
    platform admin could grant access to another tenant's project by id."""
    policy = AccessPolicy(
        mode=CUSTOM_PROJECTS,
        projects=[{"projectId": str(PROJECT), "siteAccess": {"mode": "all_sites"}}],
    )
    # Project lookup scoped to ORG returns nothing -> the project isn't theirs.
    conn = _FakeConn([[]])

    with pytest.raises(HTTPException) as exc:
        await validate_access_policy(conn, ORG, policy)
    assert exc.value.status_code == 400
    assert "unknown project" in exc.value.detail


async def test_rejects_a_site_that_belongs_to_a_different_project():
    policy = AccessPolicy(
        mode=CUSTOM_PROJECTS,
        projects=[
            {
                "projectId": str(PROJECT),
                "siteAccess": {"mode": "custom_sites", "siteIds": [str(SITE)]},
            }
        ],
    )
    conn = _FakeConn(
        [
            [_Row(id=PROJECT)],  # project belongs to org
            [_Row(id=SITE, project_id=uuid.uuid4())],  # but site is elsewhere
        ]
    )

    with pytest.raises(HTTPException) as exc:
        await validate_access_policy(conn, ORG, policy)
    assert "outside project" in exc.value.detail


@pytest.mark.parametrize("mode", ["", "everything", "ALL_PROJECTS", None])
async def test_rejects_an_unrecognised_mode(mode):
    with pytest.raises(HTTPException):
        await validate_access_policy(_FakeConn([]), ORG, AccessPolicy(mode=str(mode)))


async def test_rejects_an_unrecognised_site_mode():
    policy = AccessPolicy(
        mode=CUSTOM_PROJECTS,
        projects=[{"projectId": str(PROJECT), "siteAccess": {"mode": "some_sites"}}],
    )
    with pytest.raises(HTTPException) as exc:
        await validate_access_policy(_FakeConn([]), ORG, policy)
    assert "siteAccess.mode" in exc.value.detail


async def test_all_projects_needs_no_project_lookup():
    """The bypass names no projects, so there is nothing to validate."""
    conn = _FakeConn([])
    await validate_access_policy(conn, ORG, AccessPolicy(mode=ALL_PROJECTS, projects=[]))
    assert conn.statements == []


# ---------------------------------------------------------------------------
# Applying the policy
# ---------------------------------------------------------------------------


async def test_all_projects_writes_no_membership_rows():
    """all_projects is a *live* bypass. Materialising one row per project
    that exists today would silently exclude every project created later —
    the bug that shaped this design."""
    conn = _FakeConn([[]])  # no existing memberships

    await apply_access_policy(
        conn,
        user_id=USER,
        org_id=ORG,
        user_role="SITE_ENGINEER",
        policy=AccessPolicy(mode=ALL_PROJECTS, projects=[]),
    )

    assert conn.sql_of_type("INSERT") == [], "all_projects must write no membership rows"
    # It must still clear any prior explicit grants, which the bypass supersedes.
    assert conn.sql_of_type("DELETE"), "previous grants must be cleared"
    assert conn.sql_of_type("UPDATE"), "access_policy must still be saved"


async def test_custom_projects_writes_a_membership_row_per_project():
    conn = _FakeConn(
        [
            [_Row(id=PROJECT)],  # validation: project is in org
            [],  # existing memberships to clear
        ]
    )

    await apply_access_policy(
        conn,
        user_id=USER,
        org_id=ORG,
        user_role="SITE_ENGINEER",
        policy=AccessPolicy(
            mode=CUSTOM_PROJECTS,
            projects=[{"projectId": str(PROJECT), "siteAccess": {"mode": "all_sites"}}],
        ),
    )

    inserts = conn.sql_of_type("INSERT")
    assert len(inserts) == 1
    assert "project_members" in inserts[0]


async def test_custom_sites_writes_site_rows_too():
    conn = _FakeConn(
        [
            [_Row(id=PROJECT)],
            [_Row(id=SITE, project_id=PROJECT)],
            [],  # existing memberships
        ]
    )

    await apply_access_policy(
        conn,
        user_id=USER,
        org_id=ORG,
        user_role="SITE_ENGINEER",
        policy=AccessPolicy(
            mode=CUSTOM_PROJECTS,
            projects=[
                {
                    "projectId": str(PROJECT),
                    "siteAccess": {"mode": "custom_sites", "siteIds": [str(SITE)]},
                }
            ],
        ),
    )

    inserts = conn.sql_of_type("INSERT")
    assert any("project_members" in s for s in inserts)
    assert any("site_members" in s for s in inserts)


async def test_grants_are_replaced_not_appended():
    """Removing a project has to work as reliably as adding one."""
    conn = _FakeConn(
        [
            [_Row(id=PROJECT)],
            [_Row(project_id=uuid.uuid4())],  # an existing grant to be cleared
        ]
    )

    await apply_access_policy(
        conn,
        user_id=USER,
        org_id=ORG,
        user_role="SITE_ENGINEER",
        policy=AccessPolicy(
            mode=CUSTOM_PROJECTS,
            projects=[{"projectId": str(PROJECT), "siteAccess": {"mode": "all_sites"}}],
        ),
    )

    deletes = conn.sql_of_type("DELETE")
    assert any("project_members" in s for s in deletes)
    assert any("site_members" in s for s in deletes)


async def test_a_new_user_starts_with_no_project_access():
    """DEFAULT_ACCESS_POLICY is what every newly created user gets. It must
    stay deny-by-default: a person added from the control panel should reach
    nothing until access is granted (an ADMIN excepted, by role)."""
    from users.access_service import DEFAULT_ACCESS_POLICY

    assert DEFAULT_ACCESS_POLICY["mode"] == CUSTOM_PROJECTS
    assert DEFAULT_ACCESS_POLICY["projects"] == []


async def test_membership_rows_carry_the_users_role():
    """project_members.role is read when resolving what someone may do
    within a project, so it has to match the user's actual role."""
    conn = _FakeConn([[_Row(id=PROJECT)], []])
    captured: list = []

    original_execute = conn.execute

    async def _capture(statement, params=None):
        compiled = getattr(statement, "compile", None)
        if compiled is not None and str(statement).strip().upper().startswith("INSERT"):
            captured.append(statement.compile().params)
        return await original_execute(statement, params)

    conn.execute = _capture  # type: ignore[method-assign]

    await apply_access_policy(
        conn,
        user_id=USER,
        org_id=ORG,
        user_role="PROJECT_MANAGER",
        policy=AccessPolicy(
            mode=CUSTOM_PROJECTS,
            projects=[{"projectId": str(PROJECT), "siteAccess": {"mode": "all_sites"}}],
        ),
    )

    assert captured, "a membership row should have been inserted"
    assert captured[0]["role"] == "PROJECT_MANAGER"
