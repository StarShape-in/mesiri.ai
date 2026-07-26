"""Dump full schema (all columns) for every table on prod, plus any indexes."""
from __future__ import annotations

import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
TABLES = [
    "users",
    "organizations",
    "external_identities",
    "organization_memberships",
    "roles",
    "permissions",
    "role_permissions",
    "membership_roles",
    "projects",
    "project_memberships",
    "sites",
    "site_memberships",
    "context_organizations",
    "context_users",
    "context_projects",
    "context_sites",
    "user_context_preferences",
    "material_receipts",
    "material_usage",
    "materials_catalog",
    "finance_accounts",
    "finance_account_transactions",
    "expenses",
    "equipment_events",
    "labour_attendance",
    "labour_attendance_entries",
    "workflow_instances",
    "outbox_events",
    "idempotency_keys",
    "interactions",
    "timeline_entries",
    "infra_heartbeat",
]


def run(client: paramiko.SSHClient, sql: str) -> str:
    cmd = f'docker exec mesiri-postgres psql -U mesiri -d mesiri -c "{sql}"'
    _, stdout, _ = client.exec_command(cmd)
    return stdout.read().decode()


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    for table in TABLES:
        print(f"\n{'=' * 70}")
        print(f"  {table}")
        print(f"{'=' * 70}")
        print(
            run(
                client,
                f"SELECT column_name, data_type, is_nullable, column_default "
                f"FROM information_schema.columns WHERE table_name='{table}' "
                f"ORDER BY ordinal_position;",
            )
        )
        print(
            run(
                client,
                f"SELECT indexname, indexdef FROM pg_indexes "
                f"WHERE tablename='{table}' ORDER BY indexname;",
            )
        )

    client.close()


if __name__ == "__main__":
    main()
