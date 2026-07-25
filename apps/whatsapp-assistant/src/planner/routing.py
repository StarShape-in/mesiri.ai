"""Static routing table from CanonicalEventType to WorkflowKey.

Pure data — no I/O. `GeneralQuestionAsked`, `Unrecognized`, and
`ClarificationRequired` are intentionally absent: they never start a workflow
(the Planner routes them to DIRECT_REPLY / CLARIFY instead of consulting this
table).
"""

from __future__ import annotations

from mesiri_contracts.assistant.canonical_event import CanonicalEventType
from mesiri_contracts.assistant.planner_decision import WorkflowKey

WORKFLOW_KEY_BY_EVENT: dict[CanonicalEventType, WorkflowKey] = {
    CanonicalEventType.MATERIAL_RECEIPT_REQUESTED: WorkflowKey.MATERIAL_RECEIPT,
    CanonicalEventType.MATERIAL_USAGE_REQUESTED: WorkflowKey.MATERIAL_USAGE,
    CanonicalEventType.EXPENSE_REQUESTED: WorkflowKey.EXPENSE_SUBMIT,
    CanonicalEventType.EQUIPMENT_USAGE_REQUESTED: WorkflowKey.EQUIPMENT_USAGE,
    CanonicalEventType.LABOUR_ATTENDANCE_REQUESTED: WorkflowKey.LABOUR_ATTENDANCE,
    CanonicalEventType.GENERAL_SITE_UPDATE_REQUESTED: WorkflowKey.SITE_UPDATE,
    CanonicalEventType.IDENTITY_LOOKUP_REQUESTED: WorkflowKey.WHO_AM_I,
    CanonicalEventType.INVENTORY_QUERY_ASKED: WorkflowKey.MATERIAL_INVENTORY_QUERY,
    CanonicalEventType.ACCOUNT_ADMIN_REQUESTED: WorkflowKey.ACCOUNT_ADMIN,
    CanonicalEventType.ACCOUNT_BALANCE_QUERY_ASKED: WorkflowKey.ACCOUNT_BALANCE_QUERY,
    CanonicalEventType.EXPENSE_QUERY_ASKED: WorkflowKey.EXPENSE_QUERY,
}
