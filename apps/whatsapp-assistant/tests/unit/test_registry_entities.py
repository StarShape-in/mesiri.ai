"""Unit tests for the registry's provides/requires declarations and
workflow_that_provides -- the shared spine both the composite-request plan
layer and the entity-resolution layer read
(docs/execution/COMPOSITE_REQUEST_PLAN_LAYER.md §4.1,
docs/execution/ENTITY_RESOLUTION_PLAN.md §3.2)."""

from __future__ import annotations

from mesiri_contracts.assistant.planner_decision import WorkflowKey
from workflows.entities import EntityType
from workflows.registry import get_definition, workflow_that_provides


def test_project_create_provides_project():
    assert get_definition(WorkflowKey.PROJECT_CREATE).provides == frozenset({EntityType.PROJECT})


def test_site_create_requires_project_and_provides_site():
    definition = get_definition(WorkflowKey.SITE_CREATE)
    assert definition.requires == frozenset({EntityType.PROJECT})
    assert definition.provides == frozenset({EntityType.SITE})


def test_create_user_provides_user():
    assert get_definition(WorkflowKey.CREATE_USER).provides == frozenset({EntityType.USER})


def test_add_project_member_requires_user_and_project_provides_membership():
    definition = get_definition(WorkflowKey.ADD_PROJECT_MEMBER)
    assert definition.requires == frozenset({EntityType.USER, EntityType.PROJECT})
    assert definition.provides == frozenset({EntityType.MEMBERSHIP})


def test_site_update_requires_project_and_site_provides_activity():
    definition = get_definition(WorkflowKey.SITE_UPDATE)
    assert definition.requires == frozenset({EntityType.PROJECT, EntityType.SITE})
    assert definition.provides == frozenset({EntityType.ACTIVITY})


def test_most_workflows_declare_neither_provides_nor_requires():
    # Sanity check that the default stays empty for an ordinary workflow
    # that neither produces nor consumes a plan-level entity.
    definition = get_definition(WorkflowKey.EXPENSE_SUBMIT)
    assert definition.provides == frozenset()
    assert definition.requires == frozenset()


def test_workflow_that_provides_finds_the_declared_provider():
    assert workflow_that_provides(EntityType.USER) is WorkflowKey.CREATE_USER
    assert workflow_that_provides(EntityType.PROJECT) is WorkflowKey.PROJECT_CREATE
    assert workflow_that_provides(EntityType.SITE) is WorkflowKey.SITE_CREATE
    assert workflow_that_provides(EntityType.MEMBERSHIP) is WorkflowKey.ADD_PROJECT_MEMBER
    assert workflow_that_provides(EntityType.ACTIVITY) is WorkflowKey.SITE_UPDATE
