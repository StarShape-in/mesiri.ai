"""Check prod migration head + which application tables exist, to find un-run migrations/tables."""

from __future__ import annotations

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def run(client: paramiko.SSHClient, sql: str) -> str:
    cmd = f'docker exec mesiri-postgres psql -U mesiri -d mesiri -t -A -c "{sql}"'
    _, stdout, _ = client.exec_command(cmd)
    return stdout.read().decode()


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== alembic_version ===")
    print(run(client, "SELECT version_num FROM alembic_version;"))

    print("=== all tables (excluding system) ===")
    tables = run(
        client,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name;",
    )
    print(tables)

    print("=== workflow_instances columns ===")
    cols = run(
        client,
        "SELECT column_name, data_type, is_nullable "
        "FROM information_schema.columns WHERE table_name='workflow_instances' "
        "ORDER BY ordinal_position;",
    )
    print(cols)

    client.close()


if __name__ == "__main__":
    main()
