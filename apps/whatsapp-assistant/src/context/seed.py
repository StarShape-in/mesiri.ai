"""Deterministic M4 seed dataset + fake-repository factory.

One dataset drives unit tests, scenarios, and the golden proof so behaviour is
reproducible without a live database. It encodes the topology required by the
gate: two organizations, same project name across tenants, single-project and
multi-project users, directors, sites, defaults, and a disabled membership.

Topology
--------
ORG A (org_a):
  user_engineer  (engineer)  -> Project Alpha [Site A1, Site A2]
  user_director  (director)  -> Project Alpha, Project Beta [Site B1], default=Alpha
  user_disabled  (membership disabled)
ORG B (org_b):
  user_orgb                  -> Project Alpha (B) [Site Other]   # same name, isolated

Golden (ABC Construction):
  abc_org, director wa_director_001 -> Marina Tower [Block A, Block B], Airport
  Expansion; default = Airport Expansion.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from .fakes import (
    FakeActiveContextStore,
    FakeContextPreferenceRepository,
    FakeExternalIdentityRepository,
    FakeMembershipRepository,
    FakeProjectRepository,
    FakeReplyContextProvider,
    FakeRolePermissionRepository,
    FakeSiteRepository,
    FakeWorkflowContextProvider,
    _AuthorizedStore,
)
from .identity_bridge import build_fake_bridge_from_seed
from .models import (
    ContextPreferences,
    ExternalIdentity,
    Membership,
    Organization,
    Project,
    Site,
    User,
)
from .resolver import ContextDependencies

# -- Identifiers -------------------------------------------------------------
ORG_A = "org_a"
ORG_B = "org_b"
ABC_ORG = "abc_org"

USER_ENGINEER = "user_engineer"
USER_DIRECTOR = "user_director"
USER_DISABLED = "user_disabled"
USER_ORGB = "user_orgb"
ABC_DIRECTOR = "abc_director"

WA_ENGINEER = "wa_engineer_001"
WA_DIRECTOR = "wa_director_a_001"
WA_DISABLED = "wa_disabled_001"
WA_ORGB = "wa_orgb_001"
WA_UNKNOWN = "wa_unknown_999"
WA_ABC_DIRECTOR = "wa_director_001"

# Org A
PROJ_ALPHA = "proj_alpha"
PROJ_BETA = "proj_beta"
SITE_A1 = "site_a1"
SITE_A2 = "site_a2"
SITE_B1 = "site_b1"
# Org B (same project name "Project Alpha", different tenant)
PROJ_ALPHA_B = "proj_alpha_b"
SITE_OTHER = "site_other"
# Golden
PROJ_MARINA = "proj_marina"
PROJ_AIRPORT = "proj_airport"
SITE_BLOCK_A = "site_block_a"
SITE_BLOCK_B = "site_block_b"

ROLE_ENGINEER = "role_engineer"
ROLE_DIRECTOR = "role_director"


@dataclass(slots=True)
class SeedWorld:
    """The concrete objects, so tests can assert on ids without magic strings."""

    organizations: list[Organization]
    users: list[User]
    identities: list[ExternalIdentity]
    memberships: list[Membership]
    projects: list[Project]
    sites: list[Site]
    preferences: list[ContextPreferences]
    membership_roles: dict[str, list[str]]
    membership_permissions: dict[str, list[str]]
    project_access: dict[str, set[str]]


def build_world() -> SeedWorld:
    organizations = [
        Organization(ORG_A, is_active=True),
        Organization(ORG_B, is_active=True),
        Organization(ABC_ORG, is_active=True),
    ]
    users = [
        User(USER_ENGINEER, is_active=True, locale="en-IN", timezone="Asia/Kolkata"),
        User(USER_DIRECTOR, is_active=True, locale="en-IN", timezone="Asia/Kolkata"),
        User(USER_DISABLED, is_active=True),
        User(USER_ORGB, is_active=True),
        User(ABC_DIRECTOR, is_active=True, locale="en-IN", timezone="Asia/Kolkata"),
    ]
    identities = [
        ExternalIdentity("whatsapp", WA_ENGINEER, USER_ENGINEER),
        ExternalIdentity("whatsapp", WA_DIRECTOR, USER_DIRECTOR),
        ExternalIdentity("whatsapp", WA_DISABLED, USER_DISABLED),
        ExternalIdentity("whatsapp", WA_ORGB, USER_ORGB),
        ExternalIdentity("whatsapp", WA_ABC_DIRECTOR, ABC_DIRECTOR),
    ]
    memberships = [
        Membership("mem_eng", ORG_A, USER_ENGINEER, is_active=True),
        Membership("mem_dir", ORG_A, USER_DIRECTOR, is_active=True),
        Membership("mem_disabled", ORG_A, USER_DISABLED, is_active=False),
        Membership("mem_orgb", ORG_B, USER_ORGB, is_active=True),
        Membership("mem_abc_dir", ABC_ORG, ABC_DIRECTOR, is_active=True),
    ]
    projects = [
        Project(PROJ_ALPHA, ORG_A, "Project Alpha"),
        Project(PROJ_BETA, ORG_A, "Project Beta"),
        Project(PROJ_ALPHA_B, ORG_B, "Project Alpha"),  # same name, other tenant
        Project(PROJ_MARINA, ABC_ORG, "Marina Tower"),
        Project(PROJ_AIRPORT, ABC_ORG, "Airport Expansion"),
    ]
    sites = [
        Site(SITE_A1, PROJ_ALPHA, ORG_A, "Site A1"),
        Site(SITE_A2, PROJ_ALPHA, ORG_A, "Site A2"),
        Site(SITE_B1, PROJ_BETA, ORG_A, "Site B1"),
        Site(SITE_OTHER, PROJ_ALPHA_B, ORG_B, "Site Other"),
        Site(SITE_BLOCK_A, PROJ_MARINA, ABC_ORG, "Block A"),
        Site(SITE_BLOCK_B, PROJ_MARINA, ABC_ORG, "Block B"),
    ]
    preferences = [
        # Engineer has a single project; no explicit default needed.
        ContextPreferences(ORG_A, USER_DIRECTOR, default_project_id=PROJ_ALPHA),
        ContextPreferences(ABC_ORG, ABC_DIRECTOR, default_project_id=PROJ_AIRPORT),
    ]
    membership_roles = {
        "mem_eng": [ROLE_ENGINEER],
        "mem_dir": [ROLE_DIRECTOR],
        "mem_abc_dir": [ROLE_DIRECTOR],
    }
    membership_permissions = {
        "mem_eng": ["expense.create", "equipment.log"],
        "mem_dir": ["expense.create", "equipment.log", "project.switch", "report.view"],
        "mem_abc_dir": ["expense.create", "equipment.log", "project.switch", "report.view"],
    }
    project_access = {
        USER_ENGINEER: {PROJ_ALPHA},
        USER_DIRECTOR: {PROJ_ALPHA, PROJ_BETA},
        USER_ORGB: {PROJ_ALPHA_B},
        ABC_DIRECTOR: {PROJ_MARINA, PROJ_AIRPORT},
    }
    return SeedWorld(
        organizations=organizations,
        users=users,
        identities=identities,
        memberships=memberships,
        projects=projects,
        sites=sites,
        preferences=preferences,
        membership_roles=membership_roles,
        membership_permissions=membership_permissions,
        project_access=project_access,
    )


def build_dependencies(
    world: SeedWorld | None = None,
    *,
    clock: Callable[[], datetime] | None = None,
    active_store: FakeActiveContextStore | None = None,
    reply_mapping: dict[str, tuple[str | None, str | None]] | None = None,
    workflow_mapping: dict[tuple[str, str], tuple[str | None, str | None]] | None = None,
) -> ContextDependencies:
    """Wire fake repositories from the seed world into ``ContextDependencies``."""
    world = world or build_world()
    store = _AuthorizedStore(
        projects=world.projects,
        sites=world.sites,
        project_access=world.project_access,
    )
    if active_store is None:
        active_store = FakeActiveContextStore(clock=clock) if clock else FakeActiveContextStore()
    return ContextDependencies(
        identities=FakeExternalIdentityRepository(world.identities, world.users),
        memberships=FakeMembershipRepository(world.organizations, world.memberships),
        roles=FakeRolePermissionRepository(world.membership_roles, world.membership_permissions),
        projects=FakeProjectRepository(store),
        sites=FakeSiteRepository(store),
        preferences=FakeContextPreferenceRepository(world.preferences),
        active_context=active_store,
        reply_context=FakeReplyContextProvider(reply_mapping),
        workflow_context=FakeWorkflowContextProvider(workflow_mapping),
        bridge=build_fake_bridge_from_seed(),
    )
