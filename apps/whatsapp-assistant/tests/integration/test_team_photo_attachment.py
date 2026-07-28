"""attach_team_photo against a real database.

The write itself is what needs proving here: the attachment_type must
satisfy the CHECK constraint added in migration 0454, the row must point at
the right report, and a report belonging to another organization must be
refused. None of that is visible from a fake connection -- an earlier labour
INSERT shipped broken for exactly that reason.
"""

from __future__ import annotations

import datetime
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from mesiri.bootstrap.settings import Settings

pytestmark = pytest.mark.integration


@pytest.fixture
async def test_engine():
    settings = Settings()
    engine = create_async_engine(settings.postgres.dsn(), echo=False)
    yield engine
    await engine.dispose()


@pytest.fixture
async def seeded(test_engine: AsyncEngine):
    """One organization, one user, one recorded attendance report."""

    org_id, user_id = uuid.uuid4(), uuid.uuid4()
    project_id, report_id = uuid.uuid4(), uuid.uuid4()
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text(
                "INSERT INTO organizations (id, name, deployment_type, db_route, status,"
                " created_at, updated_at) VALUES (:id, 'Org', 'local', 'default', 'active',"
                " now(), now())"
            ),
            {"id": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO users (id, organization_id, email, hashed_password, full_name,"
                " role, status, created_at, updated_at) VALUES (:id, :org, :email, 'h',"
                " 'Engineer', 'SITE_ENGINEER', 'active', now(), now())"
            ),
            {"id": user_id, "org": org_id, "email": f"t{uuid.uuid4().hex[:6]}@example.com"},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO projects (id, organization_id, name, created_at, updated_at)"
                " VALUES (:id, :org, 'Test Project', now(), now())"
            ),
            {"id": project_id, "org": org_id},
        )
        await conn.execute(
            sa.text(
                "INSERT INTO labour_attendance_reports (id, organization_id, project_id,"
                " occurred_date,"
                " recorded_via, created_at, created_by) VALUES (:id, :org, :project, :day,"
                " 'whatsapp_text', now(), :user)"
            ),
            {
                "id": report_id,
                "org": org_id,
                "project": project_id,
                "day": datetime.date(2026, 7, 29),
                "user": user_id,
            },
        )
    yield {"org_id": org_id, "user_id": user_id, "report_id": report_id}
    # Only this fixture's own rows, in FK order. Wiping these tables wholesale
    # is unsafe in a shared database -- every other suite writes to users and
    # organizations too, and "DELETE FROM users" fails outright while anything
    # else still references one.
    async with test_engine.begin() as conn:
        await conn.execute(
            sa.text("DELETE FROM labour_attendance_attachments WHERE report_id = :r"),
            {"r": report_id},
        )
        await conn.execute(
            sa.text("DELETE FROM labour_attendance_lines WHERE report_id = :r"),
            {"r": report_id},
        )
        await conn.execute(
            sa.text("DELETE FROM labour_attendance_reports WHERE id = :r"), {"r": report_id}
        )
        await conn.execute(
            sa.text("DELETE FROM projects WHERE id = :p"), {"p": project_id}
        )
        await conn.execute(sa.text("DELETE FROM users WHERE id = :u"), {"u": user_id})
        await conn.execute(sa.text("DELETE FROM organizations WHERE id = :o"), {"o": org_id})


class _DbAdapter:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    def transaction(self):
        return self._engine.begin()


def _service(engine: AsyncEngine):
    from runtime.workforce_query import PostgresWorkforceQueryService

    return PostgresWorkforceQueryService(_DbAdapter(engine))


async def test_a_team_photo_attaches_to_the_report(test_engine: AsyncEngine, seeded):
    attachment_id = await _service(test_engine).attach_team_photo(
        organization_id=str(seeded["org_id"]),
        report_id=str(seeded["report_id"]),
        media_object_key="media/team-photo.jpg",
        created_by=str(seeded["user_id"]),
    )

    assert attachment_id is not None
    async with test_engine.connect() as conn:
        row = (
            await conn.execute(
                sa.text(
                    "SELECT report_id, media_object_key, attachment_type, created_by"
                    " FROM labour_attendance_attachments WHERE id = :id"
                ),
                {"id": uuid.UUID(attachment_id)},
            )
        ).mappings().first()

    assert row["report_id"] == seeded["report_id"]
    assert row["media_object_key"] == "media/team-photo.jpg"
    assert row["created_by"] == seeded["user_id"]
    # The point of the dedicated type: a gallery or a report can ask for the
    # crew photo without also getting the photographed attendance sheet.
    assert row["attachment_type"] == "attendance_team_photo"


async def test_a_report_belonging_to_another_organization_is_refused(
    test_engine: AsyncEngine, seeded
):
    """Tenancy is checked against the report rather than trusted from the
    caller, so a photo can never be pinned to another company's record."""
    result = await _service(test_engine).attach_team_photo(
        organization_id=str(uuid.uuid4()),
        report_id=str(seeded["report_id"]),
        media_object_key="media/team-photo.jpg",
        created_by=str(seeded["user_id"]),
    )

    assert result is None
    async with test_engine.connect() as conn:
        count = (
            await conn.execute(
                sa.text(
                    "SELECT count(*) FROM labour_attendance_attachments WHERE report_id = :r"
                ),
                {"r": seeded["report_id"]},
            )
        ).scalar()
    assert count == 0


async def test_an_unknown_report_is_refused(test_engine: AsyncEngine, seeded):
    result = await _service(test_engine).attach_team_photo(
        organization_id=str(seeded["org_id"]),
        report_id=str(uuid.uuid4()),
        media_object_key="media/team-photo.jpg",
        created_by=str(seeded["user_id"]),
    )
    assert result is None


async def test_the_attendance_record_itself_is_untouched(test_engine: AsyncEngine, seeded):
    """Attendance is append-only (P5). Attaching a photo afterwards adds a
    row pointing at the report -- it must never rewrite or supersede it."""
    async with test_engine.connect() as conn:
        before = (
            await conn.execute(
                sa.text("SELECT * FROM labour_attendance_reports WHERE id = :id"),
                {"id": seeded["report_id"]},
            )
        ).mappings().first()

    await _service(test_engine).attach_team_photo(
        organization_id=str(seeded["org_id"]),
        report_id=str(seeded["report_id"]),
        media_object_key="media/team-photo.jpg",
        created_by=str(seeded["user_id"]),
    )

    async with test_engine.connect() as conn:
        after = (
            await conn.execute(
                sa.text("SELECT * FROM labour_attendance_reports WHERE id = :id"),
                {"id": seeded["report_id"]},
            )
        ).mappings().first()

    assert dict(before) == dict(after)
