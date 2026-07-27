"""Named-worker promotion workflow — runs after a confirmed labour attendance.

**What it does.** When an attendance report names workers who are not in the
Worker Register (temporary workers, ``worker_id = None``), the attendance is
saved first, then this workflow fires as a follow-up to offer the supervisor a
chance to add those workers to the Register without interrupting the attendance
flow (plan principle P9).

**How it is triggered.** Not by AI planner intent — it has no SemanticType or
WORKFLOW_KEY_BY_EVENT mapping. runtime/inbound_journey.py creates a
WorkflowInstance for it directly after writing a confirmed attendance record,
only when at least one named temporary worker was recorded.

**Why headcount workers are excluded.** A "12 helpers" line has no name to
promote. Only named workers (worker_name non-empty) are offered.

**Principle P1 preserved.** This is the *separate, explicit act* that principle
P1 requires. The attendance itself never writes the Register; this workflow does,
and only on the user's explicit, selective say-so.
"""
