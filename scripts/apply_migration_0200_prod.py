"""Apply migration 0200 to prod: clean working tree, pull, migrate, verify, restart."""

from __future__ import annotations

import time

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def run(client: paramiko.SSHClient, cmd: str) -> str:
    print(f"\n>>> {cmd[:120]}")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print("STDERR:", err)
    return out


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # 1. Reset prod working tree to match origin/main (hard reset removes local mods)
    run(client, "cd /opt/mesiri && git fetch origin main")
    run(client, "cd /opt/mesiri && git reset --hard origin/main")
    run(client, "cd /opt/mesiri && git clean -fd")

    # 2. Verify we have migration 0200 file present
    run(client, "ls -la /opt/mesiri/backend/migrations/versions/0200*")

    # 3. Find alembic.ini
    run(client, "find /opt/mesiri -name alembic.ini -maxdepth 4 2>/dev/null")

    # 4. Run alembic upgrade to 0200 (try common config locations)
    # First try: alembic.ini at repo root or backend/
    run(
        client,
        "cd /opt/mesiri && /opt/mesiri/.venv/bin/alembic -c backend/alembic.ini upgrade 0200 2>&1 || "
        "/opt/mesiri/.venv/bin/alembic -c alembic.ini upgrade 0200 2>&1 || "
        "cd /opt/mesiri/apps/whatsapp-assistant && /opt/mesiri/.venv/bin/python -m alembic -c ../../../backend/alembic.ini upgrade 0200 2>&1",
    )

    # 5. If alembic doesn't work, apply the SQL directly
    print("\n=== Applying 0200 via direct SQL as fallback ===")
    sql_statements = [
        "ALTER TABLE workflow_instances ADD COLUMN IF NOT EXISTS version integer NOT NULL DEFAULT 0;",
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_workflow_instances_one_awaiting_per_user "
        "ON workflow_instances (user_id) WHERE phase = 'awaiting_confirmation';",
        "UPDATE alembic_version SET version_num = '0200' WHERE version_num = '0195';",
    ]
    for sql in sql_statements:
        escaped = sql.replace("'", "'\\''")
        run(
            client,
            f"docker exec mesiri-postgres psql -U mesiri -d mesiri -c '{escaped}'",
        )

    # 6. Verify
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT version_num FROM alembic_version;"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT column_name, data_type, is_nullable, column_default '
        "FROM information_schema.columns WHERE table_name='workflow_instances' "
        "AND column_name='version';\"",
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT indexname FROM pg_indexes '
        "WHERE tablename='workflow_instances' AND indexname LIKE 'uq_workflow%';\"",
    )

    # 7. Restart uvicorn
    run(client, "pkill -9 -f 'uvicorn main:app' || true")
    time.sleep(2)
    run(
        client,
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 "
        "--env-file /opt/mesiri/.env > /tmp/mesiri_uvicorn.log 2>&1 &",
    )
    time.sleep(3)
    run(client, "ps aux | grep 'uvicorn main:app' | grep -v grep")

    client.close()
    print("\n[OK] Done.")


if __name__ == "__main__":
    main()
