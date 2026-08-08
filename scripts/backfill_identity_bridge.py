"""M6.5 backfill — project control-plane entities into context layer with bridges.

Run after:  alembic upgrade 0190
Run before: alembic upgrade 0195

Usage:
    python scripts/backfill_identity_bridge.py
    python scripts/backfill_identity_bridge.py --dry-run
"""

from __future__ import annotations

import argparse
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for _p in (
    "shared/contracts/src",
    "platform/ai/src",
    "backend/src",
    "apps/whatsapp-assistant/src",
):
    sys.path.insert(0, os.path.join(_ROOT, _p))

from context.identity_projection import IdentityProjectionService  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Backfill M6.5 identity bridge columns.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report entity counts without writing (not yet supported — runs reconcile).",
    )
    args = parser.parse_args()

    if args.dry_run:
        print("dry-run: reconcile_all() is idempotent; running full reconcile.")

    service = IdentityProjectionService()
    report = service.reconcile_all()

    print(
        f"organizations={report.organizations} users={report.users} "
        f"projects={report.projects} sites={report.sites} "
        f"memberships={report.memberships} external_identities={report.external_identities}"
    )
    if report.errors:
        print("errors:")
        for err in report.errors:
            print(f"  - {err}")
        return 1
    print("backfill complete — verify with scripts/verify_identity_bridge.sql")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
