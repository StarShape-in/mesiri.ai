"""Every named worker gets a durable id at the moment they are first recorded.

Before this, a worker not already in the register was stored with
`worker_id = NULL` and their history was keyed on the *name string*. Promoting
them later inserted a brand-new register row, so the days they had already
worked stayed attached to the old key while everything afterwards accrued to
the new id -- one person, two histories, neither complete. Production shows
26 people in attendance with only 8 linked to a register row.

This deliberately departs from the Labour plan's principle P1 ("attendance
never writes the register"). The trade is documented in
`_ensure_worker_identities`: P1 kept the register clean at the cost of making
temporary workers' history unmergeable, and the register can be filtered by
worker_type while a fragmented history cannot be repaired after the fact.
"""

from __future__ import annotations

import inspect
import uuid

from mesiri.infrastructure.postgres.repositories import labour_execution

_SOURCE = inspect.getsource(labour_execution.PostgresLabourExecutionRepository)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def mappings(self):
        return self

    def all(self):
        return self._rows


class _FakeConn:
    """Captures executed statements so the find-or-create decisions can be
    asserted without a database."""

    def __init__(self, existing_workers=None):
        self.statements: list[tuple[str, dict]] = []
        self._existing = existing_workers or []

    async def execute(self, statement, params=None):
        sql = str(statement)
        self.statements.append((sql, params or {}))
        if "SELECT id, name, trade FROM workforce_workers" in sql:
            return _FakeResult(self._existing)
        return _FakeResult([])

    def inserts_into_workers(self):
        return [
            params
            for sql, params in self.statements
            if "INSERT INTO workforce_workers" in sql
        ]


class _Line:
    def __init__(self, worker_name=None, trade=None, worker_id=None, daily_wage=None,
                 contractor=None, headcount=1):
        self.worker_name = worker_name
        self.worker_name_original = None
        self.trade = trade
        self.worker_id = worker_id
        self.daily_wage = daily_wage
        self.contractor = contractor
        self.headcount = headcount
        self.activity = None


class _Cmd:
    def __init__(self, lines):
        self.lines = lines


ORG = uuid.UUID("11111111-1111-4111-8111-111111111111")
USER = uuid.UUID("22222222-2222-4222-8222-222222222222")


async def _resolve(lines, existing=None):
    repo = labour_execution.PostgresLabourExecutionRepository.__new__(
        labour_execution.PostgresLabourExecutionRepository
    )
    conn = _FakeConn(existing)
    resolved = await repo._ensure_worker_identities(conn, _Cmd(lines), ORG, USER)
    return resolved, conn


# --- Creating an identity --------------------------------------------------

async def test_a_newly_named_worker_gets_an_id_and_a_register_row():
    resolved, conn = await _resolve([_Line(worker_name="Akhilesh", trade="helper")])

    assert 0 in resolved
    inserted = conn.inserts_into_workers()
    assert len(inserted) == 1
    assert inserted[0]["name"] == "Akhilesh"
    assert inserted[0]["id"] == resolved[0]


async def test_the_new_row_is_marked_temporary_not_permanent():
    """The register must still distinguish someone who merely appeared on a
    sheet from someone deliberately registered -- that distinction is what
    makes departing from P1 acceptable."""
    _, conn = await _resolve([_Line(worker_name="Akhilesh", trade="helper")])
    sql, _ = next(s for s in conn.statements if "INSERT INTO workforce_workers" in s[0])
    assert "'temporary'" in sql
    assert "'permanent'" not in sql


async def test_the_name_is_stored_as_reported_not_normalized():
    """Normalization is a matching aid; storing it would change what the
    dashboard shows back to the supervisor."""
    _, conn = await _resolve([_Line(worker_name="Ravi  KUMAR", trade="mason")])
    assert conn.inserts_into_workers()[0]["name"] == "Ravi  KUMAR"


async def test_the_wage_and_contractor_from_the_line_seed_the_register_row():
    _, conn = await _resolve(
        [_Line(worker_name="Akhilesh", trade="helper", daily_wage=820, contractor="Kumar Agency")]
    )
    row = conn.inserts_into_workers()[0]
    assert row["daily_wage"] == 820
    assert row["contractor"] == "Kumar Agency"


# --- Reusing an identity ---------------------------------------------------

async def test_a_worker_already_in_the_register_is_reused_not_duplicated():
    existing_id = uuid.uuid4()
    resolved, conn = await _resolve(
        [_Line(worker_name="Ravi", trade="mason")],
        existing=[{"id": existing_id, "name": "Ravi", "trade": "mason"}],
    )
    assert resolved[0] == existing_id
    assert conn.inserts_into_workers() == []


async def test_matching_ignores_case_spacing_and_trade_spelling():
    existing_id = uuid.uuid4()
    resolved, conn = await _resolve(
        [_Line(worker_name="  ravi   kumar ", trade="Masons")],
        existing=[{"id": existing_id, "name": "Ravi Kumar", "trade": "mason"}],
    )
    assert resolved[0] == existing_id
    assert conn.inserts_into_workers() == []


async def test_the_same_new_person_named_twice_in_one_report_gets_one_row():
    """Two lines, one person, one register row -- otherwise a single sheet
    listing someone twice would fork them immediately."""
    resolved, conn = await _resolve(
        [_Line(worker_name="Akhilesh", trade="helper"),
         _Line(worker_name="akhilesh", trade="helper")]
    )
    assert resolved[0] == resolved[1]
    assert len(conn.inserts_into_workers()) == 1


async def test_the_same_name_in_a_different_trade_is_a_different_person():
    """Matching's own rule is exact name AND exact trade; identity follows it
    rather than inventing a second, looser rule."""
    existing_id = uuid.uuid4()
    resolved, conn = await _resolve(
        [_Line(worker_name="Ravi", trade="painter")],
        existing=[{"id": existing_id, "name": "Ravi", "trade": "mason"}],
    )
    assert resolved[0] != existing_id
    assert len(conn.inserts_into_workers()) == 1


# --- What is left alone ----------------------------------------------------

async def test_a_line_already_matched_to_a_worker_is_untouched():
    resolved, conn = await _resolve(
        [_Line(worker_name="Ravi", trade="mason", worker_id=str(uuid.uuid4()))]
    )
    assert resolved == {}
    assert conn.inserts_into_workers() == []


async def test_a_headcount_group_never_becomes_a_worker():
    """"7 masons" names nobody. Creating a register row for it would invent a
    person who does not exist."""
    resolved, conn = await _resolve([_Line(worker_name=None, trade="mason", headcount=7)])
    assert resolved == {}
    assert conn.inserts_into_workers() == []


async def test_a_blank_name_never_becomes_a_worker():
    for blank in ("", "   ", None):
        resolved, conn = await _resolve([_Line(worker_name=blank, trade="mason")])
        assert resolved == {}
        assert conn.inserts_into_workers() == []


async def test_nothing_is_queried_when_no_line_needs_an_identity():
    """The common case once a register is established -- it must not cost a
    read of the whole register for nothing."""
    _, conn = await _resolve([_Line(worker_name=None, headcount=5, trade="helper")])
    assert conn.statements == []


# --- Wiring ----------------------------------------------------------------

def test_the_line_insert_uses_the_resolved_identity():
    assert "identities.get(index)" in _SOURCE


def test_identities_are_resolved_inside_the_report_transaction():
    """Same connection as the report and line inserts, so two reports naming
    the same new person cannot race into two rows."""
    assert "_ensure_worker_identities(conn, cmd, organization_id, created_by)" in _SOURCE
