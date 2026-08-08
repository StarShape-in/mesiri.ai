"""Unit tests for AuthorizationContext and related models."""

from __future__ import annotations

import uuid

import pytest

from mesiri.authorization.context import (
    AccessPolicy,
    AuthorizationContext,
    ProjectAccessScope,
    SiteAccessScope,
    resolve_site_scope,
)


class TestAccessPolicy:
    """Tests for AccessPolicy model and parsing."""

    def test_from_db_json_all_projects(self):
        """Test parsing all_projects policy."""
        policy_json = {"mode": "all_projects", "projects": []}
        policy = AccessPolicy.from_db_json(policy_json)

        assert policy.mode == "all_projects"
        assert policy.projects == []

    def test_from_db_json_custom_projects(self):
        """Test parsing custom_projects policy with explicit grants."""
        project_id = str(uuid.uuid4())
        policy_json = {
            "mode": "custom_projects",
            "projects": [
                {"projectId": project_id, "siteAccess": {"mode": "all_sites", "siteIds": []}}
            ],
        }
        policy = AccessPolicy.from_db_json(policy_json)

        assert policy.mode == "custom_projects"
        assert len(policy.projects) == 1
        assert policy.projects[0]["projectId"] == project_id

    def test_from_db_json_null_defaults_to_empty_custom(self):
        """Test that null policy defaults to empty custom (deny by default)."""
        policy = AccessPolicy.from_db_json(None)

        assert policy.mode == "custom_projects"
        assert policy.projects == []

    def test_from_db_json_unsupported_mode_defaults_to_empty_custom(self):
        """Test that unsupported mode defaults to empty custom (deny by default)."""
        policy_json = {"mode": "invalid_mode", "projects": []}
        policy = AccessPolicy.from_db_json(policy_json)

        assert policy.mode == "custom_projects"
        assert policy.projects == []

    def test_from_db_json_malformed_projects_defaults_to_empty_custom(self):
        """Test that malformed projects list defaults to empty custom."""
        policy_json = {"mode": "custom_projects", "projects": "not a list"}
        policy = AccessPolicy.from_db_json(policy_json)

        assert policy.mode == "custom_projects"
        assert policy.projects == []


class TestProjectAccessScope:
    """Tests for ProjectAccessScope model."""

    def test_grants_all_org_projects(self):
        """Test all_projects scope grants all org projects."""
        scope = ProjectAccessScope(mode="all_projects", project_ids=set())

        assert scope.grants_all_org_projects is True
        assert scope.grants_no_projects is False

    def test_grants_no_projects_when_empty_custom(self):
        """Test empty custom scope grants no projects."""
        scope = ProjectAccessScope(mode="custom_projects", project_ids=set())

        assert scope.grants_all_org_projects is False
        assert scope.grants_no_projects is True

    def test_custom_scope_with_projects(self):
        """Test custom scope with explicit project grants."""
        project_ids = {uuid.uuid4(), uuid.uuid4()}
        scope = ProjectAccessScope(mode="custom_projects", project_ids=project_ids)

        assert scope.grants_all_org_projects is False
        assert scope.grants_no_projects is False
        assert len(scope.project_ids) == 2


class TestSiteAccessScope:
    """Tests for SiteAccessScope model."""

    def test_grants_all_sites(self):
        scope = SiteAccessScope(mode="all_sites", site_ids=set())

        assert scope.grants_all_sites is True
        assert scope.grants_no_sites is False

    def test_grants_no_sites_when_empty_custom(self):
        scope = SiteAccessScope(mode="custom_sites", site_ids=set())

        assert scope.grants_all_sites is False
        assert scope.grants_no_sites is True

    def test_custom_scope_with_sites(self):
        site_ids = {uuid.uuid4(), uuid.uuid4()}
        scope = SiteAccessScope(mode="custom_sites", site_ids=site_ids)

        assert scope.grants_all_sites is False
        assert scope.grants_no_sites is False
        assert len(scope.site_ids) == 2


class TestResolveSiteScope:
    """Tests for resolve_site_scope — mirrors _resolve_project_scope's deny-by-default rules."""

    def test_all_projects_mode_grants_all_sites(self):
        """all_projects org-wide access implies all_sites for any project."""
        policy = AccessPolicy(mode="all_projects", projects=[])
        scope = resolve_site_scope(policy, uuid.uuid4())

        assert scope.grants_all_sites is True

    def test_custom_projects_all_sites_grant(self):
        project_id = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[{"projectId": str(project_id), "siteAccess": {"mode": "all_sites"}}],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.grants_all_sites is True

    def test_custom_projects_custom_sites_with_matches(self):
        project_id = uuid.uuid4()
        site_id_1 = uuid.uuid4()
        site_id_2 = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[
                {
                    "projectId": str(project_id),
                    "siteAccess": {
                        "mode": "custom_sites",
                        "siteIds": [str(site_id_1), str(site_id_2)],
                    },
                }
            ],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.grants_all_sites is False
        assert scope.grants_no_sites is False
        assert scope.site_ids == {site_id_1, site_id_2}

    def test_custom_sites_empty_grants_no_sites(self):
        project_id = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[
                {
                    "projectId": str(project_id),
                    "siteAccess": {"mode": "custom_sites", "siteIds": []},
                }
            ],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.grants_no_sites is True

    def test_project_not_in_grants_denies_by_default(self):
        """A project_id with no matching grant resolves to empty custom scope."""
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[{"projectId": str(uuid.uuid4()), "siteAccess": {"mode": "all_sites"}}],
        )
        scope = resolve_site_scope(policy, uuid.uuid4())

        assert scope.grants_no_sites is True

    def test_missing_site_access_denies_by_default(self):
        project_id = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[{"projectId": str(project_id)}],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.grants_no_sites is True

    def test_malformed_site_access_mode_denies_by_default(self):
        project_id = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[{"projectId": str(project_id), "siteAccess": {"mode": "invalid_mode"}}],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.grants_no_sites is True

    def test_malformed_site_ids_denies_by_default(self):
        project_id = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[
                {
                    "projectId": str(project_id),
                    "siteAccess": {"mode": "custom_sites", "siteIds": "not a list"},
                }
            ],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.grants_no_sites is True

    def test_invalid_site_id_string_skipped(self):
        project_id = uuid.uuid4()
        valid_site_id = uuid.uuid4()
        policy = AccessPolicy(
            mode="custom_projects",
            projects=[
                {
                    "projectId": str(project_id),
                    "siteAccess": {
                        "mode": "custom_sites",
                        "siteIds": [str(valid_site_id), "not-a-uuid"],
                    },
                }
            ],
        )
        scope = resolve_site_scope(policy, project_id)

        assert scope.site_ids == {valid_site_id}


class TestAuthorizationContext:
    """Tests for AuthorizationContext model."""

    def test_is_active_true_for_active_user(self):
        """Test is_active property for active user."""
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="active",
            access_policy=AccessPolicy(mode="all_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
        )

        assert ctx.is_active is True

    def test_is_active_false_for_inactive_user(self):
        """Test is_active property for inactive user."""
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="suspended",
            access_policy=AccessPolicy(mode="all_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
        )

        assert ctx.is_active is False

    def test_context_is_immutable(self):
        """Test that AuthorizationContext is frozen/immutable."""
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="active",
            access_policy=AccessPolicy(mode="all_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="all_projects", project_ids=set()),
        )

        with pytest.raises((AttributeError, TypeError)):
            ctx.status = "suspended"  # type: ignore

    def test_site_scope_for_project_reads_precomputed_site_scopes(self):
        """site_scope_for_project looks up the precomputed site_scopes dict
        (resolved upfront by AuthorizationService from project_members/
        site_members) -- access_policy is no longer consulted here at all."""
        project_id = uuid.uuid4()
        site_id = uuid.uuid4()
        ctx = AuthorizationContext(
            user_id=uuid.uuid4(),
            organization_id=uuid.uuid4(),
            role="admin",
            status="active",
            access_policy=AccessPolicy(mode="custom_projects", projects=[]),
            project_scope=ProjectAccessScope(mode="custom_projects", project_ids={project_id}),
            site_scopes={project_id: SiteAccessScope(mode="custom_sites", site_ids={site_id})},
        )

        scope = ctx.site_scope_for_project(project_id)

        assert scope.site_ids == {site_id}
