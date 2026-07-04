"""Correlation propagation (M1).

A single user journey carries one ``correlation_id`` end to end. It is minted
once at the entry point and then *propagated* — every layer reads it from the
ambient context (``contextvars``, so it survives across ``await`` boundaries and
is isolated per task) rather than minting a new one.

The structured logger reads these values automatically, so any log emitted
inside a bound context is stamped with the journey's ids without the caller
passing them explicitly.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token

from mesiri_contracts.common.ids import new_correlation_id

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_message_id: ContextVar[str | None] = ContextVar("message_id", default=None)
_workflow_instance_id: ContextVar[str | None] = ContextVar("workflow_instance_id", default=None)


def get_correlation_id() -> str | None:
    return _correlation_id.get()


def get_request_id() -> str | None:
    return _request_id.get()


def get_message_id() -> str | None:
    return _message_id.get()


def get_workflow_instance_id() -> str | None:
    return _workflow_instance_id.get()


def current_context() -> dict[str, str]:
    """Snapshot of the correlation fields that are currently set."""
    out: dict[str, str] = {}
    for key, var in (
        ("correlation_id", _correlation_id),
        ("request_id", _request_id),
        ("message_id", _message_id),
        ("workflow_instance_id", _workflow_instance_id),
    ):
        val = var.get()
        if val is not None:
            out[key] = val
    return out


@contextmanager
def correlation_scope(
    *,
    correlation_id: str | None = None,
    request_id: str | None = None,
    message_id: str | None = None,
    workflow_instance_id: str | None = None,
    generate_missing_correlation: bool = True,
) -> Iterator[str]:
    """Bind correlation ids for the duration of the block.

    If no ``correlation_id`` is supplied and one is not already bound, a new one
    is minted (this is the *only* place ids are created downstream of ingress).
    An existing bound ``correlation_id`` is never overwritten with a fresh one.
    """
    resolved = correlation_id or _correlation_id.get()
    if resolved is None and generate_missing_correlation:
        resolved = new_correlation_id()

    tokens: list[tuple[ContextVar[str | None], Token]] = []
    if resolved is not None:
        tokens.append((_correlation_id, _correlation_id.set(resolved)))
    if request_id is not None:
        tokens.append((_request_id, _request_id.set(request_id)))
    if message_id is not None:
        tokens.append((_message_id, _message_id.set(message_id)))
    if workflow_instance_id is not None:
        tokens.append((_workflow_instance_id, _workflow_instance_id.set(workflow_instance_id)))
    try:
        yield resolved or ""
    finally:
        for var, token in reversed(tokens):
            var.reset(token)
