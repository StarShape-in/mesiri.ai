"""Identifier utilities and correlation conventions (M0).

One user journey carries a single ``correlation_id`` from ingress through every
downstream operation. Downstream layers *propagate* the id; they do not mint a
new one per layer (see the Correlation section in the milestone plan).

Ownership: SHARED ARCHITECTURE.
"""

from __future__ import annotations

import uuid

# Prefixes make ids self-describing in logs / traces.
_CORRELATION_PREFIX = "cor"
_MESSAGE_PREFIX = "msg"
_CAUSATION_PREFIX = "cau"
_REQUEST_PREFIX = "req"
_WORKFLOW_PREFIX = "wf"


def _new(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def new_correlation_id() -> str:
    """Mint a correlation id at the *entry point* of a user journey only."""
    return _new(_CORRELATION_PREFIX)


def new_message_id() -> str:
    return _new(_MESSAGE_PREFIX)


def new_causation_id() -> str:
    return _new(_CAUSATION_PREFIX)


def new_request_id() -> str:
    return _new(_REQUEST_PREFIX)


def new_workflow_instance_id() -> str:
    return _new(_WORKFLOW_PREFIX)


def new_id(prefix: str) -> str:
    """Generic prefixed identifier for module-specific ids."""
    return _new(prefix)
