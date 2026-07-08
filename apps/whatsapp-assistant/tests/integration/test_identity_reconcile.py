"""M6.5 reconcile_all — projects control plane into context layer with bridges."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text

from context.identity_bridge import context_organization_id, context_user_id
from context.identity_projection import IdentityProjectionService

pytestmark = pytest.mark.integration


@pytest.fixture
def sync_engine():
    from context.identity_projection import build_sync_engine

    engine = build_sync_engine()
    org_id = uuid.uuid4()
    user_id = uuid.uuid4()
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO organizations (id, name, status) "
                "VALUES (:id, :name, 'Active') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {"id": org_id, "name": "M6.5 Reconcile Test Org"},
        )
        conn.execute(
            text(
                "INSERT INTO users (id, full_name, organization_id, whatsapp_number, status) "
                "VALUES (:id, :name, :org, :wa, 'active') "
                "ON CONFLICT (id) DO NOTHING"
            ),
            {
                "id": user_id,
                "name": "Reconcile Tester",
                "org": org_id,
                "wa": "+919999999001",
            },
        )
    yield engine, org_id, user_id
    with engine.begin() as conn:
        ctx_org = context_organization_id(org_id)
        ctx_user = context_user_id(user_id)
        conn.execute(text("DELETE FROM external_identities WHERE user_id = :u"), {"u": ctx_user})
        conn.execute(
            text("DELETE FROM organization_memberships WHERE organization_id = :o"),
            {"o": ctx_org},
        )
        conn.execute(text("DELETE FROM context_users WHERE id = :u"), {"u": ctx_user})
        conn.execute(text("DELETE FROM context_organizations WHERE id = :o"), {"o": ctx_org})
        conn.execute(text("DELETE FROM users WHERE id = :id"), {"id": user_id})
        conn.execute(text("DELETE FROM organizations WHERE id = :id"), {"id": org_id})
    engine.dispose()


def test_reconcile_projects_organization_and_user(sync_engine) -> None:
    engine, org_id, user_id = sync_engine
    service = IdentityProjectionService(engine=engine)
    service.project_one("organization", org_id)
    service.project_one("user", user_id)

    ctx_org = context_organization_id(org_id)
    ctx_user = context_user_id(user_id)
    with engine.connect() as conn:
        row = conn.execute(
            text(
                "SELECT canonical_organization_id::text FROM context_organizations WHERE id = :id"
            ),
            {"id": ctx_org},
        ).one()
        assert str(row[0]) == str(org_id)
        row = conn.execute(
            text("SELECT canonical_user_id::text FROM context_users WHERE id = :id"),
            {"id": ctx_user},
        ).one()
        assert str(row[0]) == str(user_id)
        ext = conn.execute(
            text(
                "SELECT COUNT(*) FROM external_identities "
                "WHERE provider = 'whatsapp' AND external_subject = '+919999999001'"
            )
        ).scalar_one()
        assert ext == 1
