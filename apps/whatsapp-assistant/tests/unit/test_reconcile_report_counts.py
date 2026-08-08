"""Unit tests for ReconcileReport's counts (context/identity_projection.py).

These numbers are shown directly on the control panel's Sync Health page, so
a counter that silently reads 0 forever isn't cosmetic -- it's a wrong
answer to "are WhatsApp numbers linked?", pointing an operator at a problem
that doesn't exist.

`external_identities` was exactly that: declared on ReconcileReport but
never incremented by reconcile_all, so it read 0 no matter how many
identities had been written. Fakes only -- no live DB.
"""

from __future__ import annotations

from context.identity_projection import IdentityProjectionService


class _FakeResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self):
        return self._rows


class _FakeConn:
    """Returns canned rows per query, keyed off the table each one selects."""

    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self._tables = tables

    def execute(self, statement, params=None):
        sql = str(statement)
        for table, rows in self._tables.items():
            if f"FROM {table}" in sql:
                return _FakeResult(rows)
        return _FakeResult([])

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeEngine:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def begin(self):
        return self._conn


class _StubbedService(IdentityProjectionService):
    """Real reconcile_all, stubbed per-entity projection -- the loop and its
    counting are what's under test, not the SQL each projection runs."""

    def __init__(self, tables: dict[str, list[dict]]) -> None:
        self._engine = _FakeEngine(_FakeConn(tables))

    def _project_organization(self, conn, canonical_id) -> None: ...
    def _project_user(self, conn, canonical_id) -> None: ...
    def _project_project(self, conn, canonical_id) -> None: ...
    def _project_site(self, conn, canonical_id) -> None: ...
    def _project_membership(self, conn, canonical_user_id) -> None: ...


def _service(users: list[dict]) -> _StubbedService:
    return _StubbedService(
        {
            "organizations": [{"id": "o1", "name": "Acme", "status": "active"}],
            "users": users,
            "projects": [{"id": "p1", "organization_id": "o1", "name": "P", "status": "active"}],
            "sites": [],
            "project_members": [{"user_id": "u1"}],
        }
    )


def _user(uid: str, whatsapp_number: str | None) -> dict:
    return {
        "id": uid,
        "full_name": "Someone",
        "organization_id": "o1",
        "whatsapp_number": whatsapp_number,
        "status": "active",
    }


def test_external_identities_counts_users_with_a_whatsapp_number():
    """The regression this guards: the count read 0 forever, which on the
    Sync Health page looks like no WhatsApp numbers are linked at all."""
    report = _service(
        [
            _user("u1", "+91 99999 99001"),
            _user("u2", "919999999002"),
            _user("u3", None),
        ]
    ).reconcile_all()

    assert report.users == 3
    assert report.external_identities == 2, (
        "only the two users with a usable WhatsApp number get an "
        "external_identities row written"
    )


def test_users_without_a_number_are_not_counted():
    report = _service([_user("u1", None), _user("u2", "")]).reconcile_all()

    assert report.users == 2
    assert report.external_identities == 0


def test_punctuation_only_number_is_not_counted():
    """_digits strips non-digits; a number that reduces to nothing writes no
    external identity, so it must not be counted as one."""
    report = _service([_user("u1", "+-- ()")]).reconcile_all()

    assert report.users == 1
    assert report.external_identities == 0


def test_other_counts_are_unaffected():
    report = _service([_user("u1", "919999999001")]).reconcile_all()

    assert report.organizations == 1
    assert report.projects == 1
    assert report.sites == 0
    assert report.memberships == 1
    assert report.errors == []


def test_a_failing_user_projection_is_reported_and_not_counted():
    class _Exploding(_StubbedService):
        def _project_user(self, conn, canonical_id) -> None:
            raise RuntimeError("boom")

    service = _Exploding(
        {
            "organizations": [],
            "users": [_user("u1", "919999999001")],
            "projects": [],
            "sites": [],
            "project_members": [],
        }
    )
    report = service.reconcile_all()

    assert report.users == 0
    assert report.external_identities == 0, (
        "a user whose projection failed wrote no external identity either"
    )
    assert len(report.errors) == 1
    assert "boom" in report.errors[0]
