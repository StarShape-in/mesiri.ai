"""Check all tables on prod + row counts for domain tables + material schema details."""

from __future__ import annotations

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def run(client: paramiko.SSHClient, sql: str) -> str:
    cmd = f'docker exec mesiri-postgres psql -U mesiri -d mesiri -c "{sql}"'
    _, stdout, _ = client.exec_command(cmd)
    return stdout.read().decode()


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== ALL TABLES ===")
    print(run(
        client,
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' ORDER BY table_name;",
    ))

    print("=== ROW COUNTS PER TABLE ===")
    tables_query = (
        "SELECT table_name FROM information_schema.tables "
        "WHERE table_schema='public' AND table_name != 'alembic_version' "
        "ORDER BY table_name;"
    )
    _, stdout, _ = client.exec_command(
        f'docker exec mesiri-postgres psql -U mesiri -d mesiri -t -A -c "{tables_query}"'
    )
    tables = [t.strip() for t in stdout.read().decode().splitlines() if t.strip()]
    for t in tables:
        count = run(client, f"SELECT COUNT(*) AS {t} FROM {t};")
        print(count.strip())

    print("\n=== MATERIAL RECEIPTS SCHEMA ===")
    print(run(
        client,
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_name='material_receipts' ORDER BY ordinal_position;",
    ))

    print("=== MATERIAL USAGE SCHEMA ===")
    print(run(
        client,
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_name='material_usage' ORDER BY ordinal_position;",
    ))

    print("=== MATERIALS CATALOG SCHEMA ===")
    print(run(
        client,
        "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
        "WHERE table_name='materials_catalog' ORDER BY ordinal_position;",
    ))

    print("=== MATERIALS CATALOG ROWS ===")
    print(run(client, "SELECT * FROM materials_catalog LIMIT 10;"))

    print("=== MATERIAL RECEIPTS ROWS ===")
    print(run(client, "SELECT * FROM material_receipts LIMIT 5;"))

    client.close()


if __name__ == "__main__":
    main()
