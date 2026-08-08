"""Fake Context port adapters (tests only)."""

from context.adapters.fake_identity import FakeIdentityLookupPort
from context.adapters.fake_scope import FakeScopeLookupPort
from context.adapters.fake_workflow_state import FakeWorkflowStateReadPort

__all__ = [
    "FakeIdentityLookupPort",
    "FakeScopeLookupPort",
    "FakeWorkflowStateReadPort",
]
