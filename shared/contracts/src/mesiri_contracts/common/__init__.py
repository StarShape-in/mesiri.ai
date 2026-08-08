"""Shared cross-cutting contracts (M0 common)."""

from .clock import Clock, FixedClock, SystemClock
from .errors import ErrorCategory, ErrorCode, MesiriError
from .health import DependencyState, DependencyStatus, HealthReport
from .ids import (
    new_causation_id,
    new_correlation_id,
    new_id,
    new_message_id,
    new_request_id,
    new_workflow_instance_id,
)
from .result import Result
from .storage import ObjectMetadata, ObjectStoragePort, StoredObject

__all__ = [
    "Clock",
    "SystemClock",
    "FixedClock",
    "ErrorCategory",
    "ErrorCode",
    "MesiriError",
    "DependencyState",
    "DependencyStatus",
    "HealthReport",
    "Result",
    "ObjectMetadata",
    "ObjectStoragePort",
    "StoredObject",
    "new_correlation_id",
    "new_message_id",
    "new_causation_id",
    "new_request_id",
    "new_workflow_instance_id",
    "new_id",
]
