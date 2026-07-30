"""Scheduler step: make `projects.auto_generate_dpr` actually send a DPR.

Sibling to automation_runner.py's `_queue_due_automations` -- same shape
(find due rows, generate/build a payload, claim one `notifications` row per
recipient, mark the row run), called from the SAME tick
(automation_runner.py's `run_tick`) so it shares that module's advisory
lock, 60s-interval loop, and `_drain_and_send` delivery step rather than
running a second scheduler process.

Not implemented as a synthetic `automations` row on purpose: an automation
is always owned by a user (`created_by`), but a project's own standing DPR
schedule isn't anyone's personal automation -- it's a property of the
project itself, set by whoever last edited the dashboard's reporting tab.
Giving it a fake owner would mean picking one arbitrarily and having that
person's automation silently vanish/misbehave if they leave the project.
"""

from __future__ import annotations

import datetime
import logging
import uuid
from typing import Any

logger = logging.getLogger("mesiri.project_auto_dpr")


async def _project_dpr_recipients(
    db: Any, *, organization_id: str, project_id: str
) -> list[str]:
    """ADMIN + PROJECT_MANAGER reachable from this project -- the same
    audience an automation's ROLE resolution would compute for either role
    individually (see runtime/automation_audience.py's
    `_active_users_with_role`), just for two roles instead of one. Site
    engineers aren't included: a project-wide daily rollup is a management
    report, not something every site engineer needs pushed to them."""
    from .automation_audience import _active_users_with_role

    admins = await _active_users_with_role(
        db, organization_id=organization_id, project_id=project_id, role="ADMIN"
    )
    managers = await _active_users_with_role(
        db, organization_id=organization_id, project_id=project_id, role="PROJECT_MANAGER"
    )
    return sorted(set(admins) | set(managers))


async def _build_project_dpr_payload(
    dpr_query: Any, *, organization_id: str, project_id: str, report_date: datetime.date
) -> dict[str, Any]:
    """Mirrors automation_actions.py's `_build_send_dpr_payload` shape
    exactly (same two conventional keys, same three statuses) -- kept as a
    separate copy rather than a shared import since that function is
    automation-row-shaped (reads `automation["site_id"]`/`automation["project_id"]`)
    and this caller has no automation row at all, just a project."""
    result = await dpr_query.find_report(
        organization_id=organization_id,
        project_id=project_id,
        site_id=None,
        report_date=report_date,
    )
    status = result["status"]
    if status == "ready":
        return {
            "message": f"Today's DPR ({result.get('code') or ''}) is attached.",
            "document_object_key": result["object_key"],
        }
    if status == "pending_render":
        return {
            "message": (
                f"Today's DPR ({result.get('code') or ''}) is generated but "
                "not yet rendered as a PDF."
            )
        }
    return {"message": f"No DPR has been generated yet for {report_date.isoformat()}."}


async def queue_due_project_auto_dprs(conn: Any, *, db: Any) -> int:
    """Finds every project whose own auto-DPR schedule is due, generates
    today's report for it (SITE-level drafts + PROJECT-level rollup), and
    claims one notifications row per ADMIN/PROJECT_MANAGER recipient.
    Returns the count of projects that fired.

    Every project is handled independently and best-effort: one project's
    generation or recipient-resolution failure is logged and skipped, never
    allowed to abort the rest of the scan (same "a bad row can't take down
    the tick" principle automation_runner.py's own loop applies)."""
    from mesiri.application.automations.scheduling import local_now
    from mesiri.application.projects.auto_dpr import (
        due_projects_for_auto_dpr,
        generate_project_dpr,
        mark_project_auto_dpr_run,
    )
    from mesiri.infrastructure.postgres.repositories.notifications import (
        PostgresNotificationRepository,
    )

    from .dpr_request_query import DprRequestQueryService

    notifications_repo = PostgresNotificationRepository(conn)
    dpr_query = DprRequestQueryService(db)

    now_utc = datetime.datetime.now(datetime.UTC)
    fired = 0

    for project in await due_projects_for_auto_dpr(conn, now_utc=now_utc):
        project_id = str(project["id"])
        organization_id = str(project["organization_id"])
        report_date = local_now(
            timezone_name=project["reporting_timezone"] or "UTC", now_utc=now_utc
        ).date()

        try:
            await generate_project_dpr(
                conn,
                organization_id=project["organization_id"],
                project_id=project["id"],
                report_date=report_date,
            )
        except Exception:  # noqa: BLE001
            logger.exception("project_auto_dpr.generate_failed project_id=%s", project_id)
            continue

        try:
            recipients = await _project_dpr_recipients(
                db, organization_id=organization_id, project_id=project_id
            )
            payload = await _build_project_dpr_payload(
                dpr_query,
                organization_id=organization_id,
                project_id=project_id,
                report_date=report_date,
            )
        except Exception:  # noqa: BLE001
            logger.exception("project_auto_dpr.build_failed project_id=%s", project_id)
            continue

        for recipient_id in recipients:
            try:
                await notifications_repo.claim(
                    organization_id=project["organization_id"],
                    rule_key=f"project_auto_dpr:{project_id}",
                    subject_id=project_id,
                    occurred_on=report_date,
                    recipient_user_id=uuid.UUID(recipient_id),
                    project_id=project["id"],
                    site_id=None,
                    payload=payload,
                )
            except Exception:  # noqa: BLE001
                logger.exception(
                    "project_auto_dpr.claim_failed project_id=%s recipient=%s",
                    project_id,
                    recipient_id,
                )

        try:
            await mark_project_auto_dpr_run(conn, project_id=project["id"], ran_on=report_date)
        except Exception:  # noqa: BLE001
            logger.exception("project_auto_dpr.mark_run_failed project_id=%s", project_id)
        fired += 1

    return fired
