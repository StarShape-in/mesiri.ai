"""Apply migration 0210 SQL directly to prod via paramiko with timeouts."""

from __future__ import annotations

import sys
import time

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"

SQLS = [
    # G1: RBAC created_at
    "ALTER TABLE roles ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    "ALTER TABLE permissions ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    "ALTER TABLE role_permissions ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    "ALTER TABLE membership_roles ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    "ALTER TABLE project_memberships ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    "ALTER TABLE site_memberships ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    # G2: external_identities
    "ALTER TABLE external_identities ADD COLUMN IF NOT EXISTS created_at timestamptz NOT NULL DEFAULT now();",
    # G3: trigger function
    "CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;",
]

CONTEXT_TABLES = ["context_organizations", "context_users", "context_projects", "context_sites"]

G4_SQL = """CREATE TABLE IF NOT EXISTS inbound_messages (
    id uuid PRIMARY KEY,
    correlation_id varchar NOT NULL,
    sender_wa_id varchar NOT NULL,
    message_type varchar NOT NULL,
    raw_payload jsonb NOT NULL,
    normalized_message jsonb,
    body_text text,
    media_object_key varchar,
    dedup_key varchar NOT NULL UNIQUE,
    received_at timestamptz NOT NULL DEFAULT now(),
    processed_at timestamptz,
    processing_status varchar NOT NULL DEFAULT 'pending',
    error_code varchar
);"""

G5_SQL = """CREATE TABLE IF NOT EXISTS journey_traces (
    id uuid PRIMARY KEY,
    correlation_id varchar NOT NULL,
    stage varchar NOT NULL,
    stage_payload jsonb,
    duration_ms integer,
    succeeded boolean NOT NULL,
    error_code varchar,
    error_message text,
    created_at timestamptz NOT NULL DEFAULT now()
);"""


def exec_sql(client, sql):
    # Use single-quoted heredoc to avoid shell escaping issues
    cmd = (
        f"docker exec mesiri-postgres psql -U mesiri -d mesiri "
        f"-c \"{sql.replace(chr(34), chr(39))}\""
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    return out, err


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    print("Connecting...")
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    print("Connected.")

    # Pull latest code
    print("\n-- git pull --")
    _, stdout, stderr = client.exec_command("cd /opt/mesiri && git fetch origin main && git reset --hard origin/main && git clean -fd", timeout=30)
    print(stdout.read().decode().strip()[-200:])

    # Apply SQLs
    print("\n-- G1+G2+G3 base SQLs --")
    for sql in SQLS:
        out, err = exec_sql(client, sql)
        if out:
            print(f"  {out[:80]}")
        if err and "NOTICE" not in err:
            print(f"  ERR: {err[:100]}")

    # G3: context table columns + triggers
    print("\n-- G3 context updated_at + triggers --")
    for table in CONTEXT_TABLES:
        out, err = exec_sql(client, f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at timestamptz NOT NULL DEFAULT now();")
        if out:
            print(f"  {table}: {out[:60]}")
        out, err = exec_sql(client, f"DROP TRIGGER IF EXISTS trg_{table}_updated ON {table};")
        out, err = exec_sql(client, f"CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION set_updated_at();")
        if out:
            print(f"  {table} trigger: {out[:60]}")

    # G4: inbound_messages
    print("\n-- G4 inbound_messages --")
    out, err = exec_sql(client, G4_SQL.replace("\n", " ").replace("'", "'\"'\"'"))
    # Try a simpler approach
    cmd = (
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        "'CREATE TABLE IF NOT EXISTS inbound_messages ("
        "id uuid PRIMARY KEY, correlation_id varchar NOT NULL, "
        "sender_wa_id varchar NOT NULL, message_type varchar NOT NULL, "
        "raw_payload jsonb NOT NULL, normalized_message jsonb, "
        "body_text text, media_object_key varchar, "
        "dedup_key varchar NOT NULL UNIQUE, "
        "received_at timestamptz NOT NULL DEFAULT now(), "
        "processed_at timestamptz, "
        "processing_status varchar NOT NULL DEFAULT '\'pending\'', "
        "error_code varchar);'"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(f"  {stdout.read().decode().strip()[:80]}")
    err = stderr.read().decode().strip()
    if err and "NOTICE" not in err and "already exists" not in err:
        print(f"  ERR: {err[:100]}")

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS ix_inbound_messages_correlation_id ON inbound_messages (correlation_id);",
        "CREATE INDEX IF NOT EXISTS ix_inbound_messages_sender_wa_id ON inbound_messages (sender_wa_id);",
        "CREATE INDEX IF NOT EXISTS ix_inbound_messages_received_at ON inbound_messages (received_at);",
    ]:
        out, err = exec_sql(client, idx_sql)
        if out:
            print(f"  {out[:60]}")

    # G5: journey_traces
    print("\n-- G5 journey_traces --")
    cmd = (
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        "'CREATE TABLE IF NOT EXISTS journey_traces ("
        "id uuid PRIMARY KEY, correlation_id varchar NOT NULL, "
        "stage varchar NOT NULL, stage_payload jsonb, "
        "duration_ms integer, succeeded boolean NOT NULL, "
        "error_code varchar, error_message text, "
        "created_at timestamptz NOT NULL DEFAULT now());'"
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=15)
    print(f"  {stdout.read().decode().strip()[:80]}")

    for idx_sql in [
        "CREATE INDEX IF NOT EXISTS ix_journey_traces_correlation_id ON journey_traces (correlation_id);",
        "CREATE INDEX IF NOT EXISTS ix_journey_traces_correlation_stage ON journey_traces (correlation_id, stage);",
    ]:
        out, err = exec_sql(client, idx_sql)
        if out:
            print(f"  {out[:60]}")

    # Update alembic version
    print("\n-- Update alembic_version to 0210 --")
    out, err = exec_sql(client, "UPDATE alembic_version SET version_num = '0210' WHERE version_num = '0200';")
    print(f"  {out}")

    # Verify
    print("\n-- Verify --")
    out, err = exec_sql(client, "SELECT version_num FROM alembic_version;")
    print(f"  alembic: {out}")
    out, err = exec_sql(client, "SELECT COUNT(*) FROM information_schema.tables WHERE table_name IN ('inbound_messages','journey_traces');")
    print(f"  new tables: {out}")
    out, err = exec_sql(client, "SELECT column_name FROM information_schema.columns WHERE table_name='context_organizations' AND column_name='updated_at';")
    print(f"  context updated_at: {out}")
    out, err = exec_sql(client, "SELECT column_name FROM information_schema.columns WHERE table_name='roles' AND column_name='created_at';")
    print(f"  roles created_at: {out}")

    # Restart uvicorn
    print("\n-- Restart uvicorn --")
    client.exec_command("pkill -9 -f 'uvicorn main:app' || true", timeout=5)
    time.sleep(2)
    cmd = (
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "PYTHONPATH=/opt/mesiri/apps/whatsapp-assistant/src:/opt/mesiri/backend/src:"
        "/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 "
        "--env-file /opt/mesiri/.env > /tmp/mesiri_uvicorn.log 2>&1 &"
    )
    client.exec_command(cmd, timeout=5)
    time.sleep(3)
    _, stdout, _ = client.exec_command("ps aux | grep 'uvicorn main:app' | grep -v grep", timeout=5)
    proc = stdout.read().decode().strip()
    print(f"  uvicorn: {proc[:80] if proc else '(not running)'}")

    client.close()
    print("\n[OK] Done.")


if __name__ == "__main__":
    main()
