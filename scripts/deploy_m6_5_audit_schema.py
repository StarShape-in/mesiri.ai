"""Deploy migration 0210 to prod: apply schema, restart uvicorn, verify debug tables."""
from __future__ import annotations

import os
import time

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def run(client: paramiko.SSHClient, cmd: str) -> str:
    print(f"\n>>> {cmd[:120]}")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err and "No such file" not in err and "warning" not in err.lower():
        print("STDERR:", err[:300])
    return out


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # 1. Pull latest code
    run(client, "cd /opt/mesiri && git fetch origin main")
    run(client, "cd /opt/mesiri && git reset --hard origin/main")
    run(client, "cd /opt/mesiri && git clean -fd")

    # 2. Verify migration file exists
    run(client, "ls -la /opt/mesiri/backend/migrations/versions/0210*")

    # 3. Apply migration 0210 via direct SQL (alembic config is broken on prod)
    print("\n=== Applying 0210 via direct SQL ===")

    # G1: created_at on RBAC tables
    rbac_tables = [
        "roles",
        "permissions",
        "role_permissions",
        "membership_roles",
        "project_memberships",
        "site_memberships",
    ]
    for table in rbac_tables:
        run(
            client,
            f"docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
            f'"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS created_at '
            f'timestamptz NOT NULL DEFAULT now();"',
        )

    # G2: created_at on external_identities
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"ALTER TABLE external_identities ADD COLUMN IF NOT EXISTS created_at '
        'timestamptz NOT NULL DEFAULT now();"',
    )

    # G3: updated_at + trigger on context_* tables
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$ '
        "BEGIN NEW.updated_at = now(); RETURN NEW; END; "
        '$$ LANGUAGE plpgsql;"',
    )
    context_tables = [
        "context_organizations",
        "context_users",
        "context_projects",
        "context_sites",
    ]
    for table in context_tables:
        run(
            client,
            f"docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
            f'"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS updated_at '
            f'timestamptz NOT NULL DEFAULT now();"',
        )
        run(
            client,
            f"docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
            f'"DROP TRIGGER IF EXISTS trg_{table}_updated ON {table};',
        )
        run(
            client,
            f"docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
            f'"CREATE TRIGGER trg_{table}_updated '
            f"BEFORE UPDATE ON {table} "
            f'FOR EACH ROW EXECUTE FUNCTION set_updated_at();"',
        )

    # G4: inbound_messages table
    run(
        client,
        r'docker exec mesiri-postgres psql -U mesiri -d mesiri -c "'
        "CREATE TABLE IF NOT EXISTS inbound_messages ("
        "id uuid PRIMARY KEY,"
        "correlation_id varchar NOT NULL,"
        "sender_wa_id varchar NOT NULL,"
        "message_type varchar NOT NULL,"
        "raw_payload jsonb NOT NULL,"
        "normalized_message jsonb,"
        "body_text text,"
        "media_object_key varchar,"
        "dedup_key varchar NOT NULL UNIQUE,"
        "received_at timestamptz NOT NULL DEFAULT now(),"
        "processed_at timestamptz,"
        "processing_status varchar NOT NULL DEFAULT 'pending',"
        "error_code varchar"
        ");"
        '"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"CREATE INDEX IF NOT EXISTS ix_inbound_messages_correlation_id '
        'ON inbound_messages (correlation_id);"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"CREATE INDEX IF NOT EXISTS ix_inbound_messages_sender_wa_id '
        'ON inbound_messages (sender_wa_id);"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"CREATE INDEX IF NOT EXISTS ix_inbound_messages_received_at '
        'ON inbound_messages (received_at);"',
    )

    # G5: journey_traces table
    run(
        client,
        r'docker exec mesiri-postgres psql -U mesiri -d mesiri -c "'
        "CREATE TABLE IF NOT EXISTS journey_traces ("
        "id uuid PRIMARY KEY,"
        "correlation_id varchar NOT NULL,"
        "stage varchar NOT NULL,"
        "stage_payload jsonb,"
        "duration_ms integer,"
        "succeeded boolean NOT NULL,"
        "error_code varchar,"
        "error_message text,"
        "created_at timestamptz NOT NULL DEFAULT now()"
        ");"
        '"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"CREATE INDEX IF NOT EXISTS ix_journey_traces_correlation_id '
        'ON journey_traces (correlation_id);"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"CREATE INDEX IF NOT EXISTS ix_journey_traces_correlation_stage '
        'ON journey_traces (correlation_id, stage);"',
    )

    # Update alembic_version
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        "\"UPDATE alembic_version SET version_num = '0210' WHERE version_num = '0200';\"",
    )

    # 4. Verify
    print("\n=== Verification ===")
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT version_num FROM alembic_version;"',
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT table_name FROM information_schema.tables WHERE table_name IN '
        "('inbound_messages', 'journey_traces') ORDER BY table_name;\"",
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT column_name FROM information_schema.columns '
        "WHERE table_name='context_organizations' AND column_name='updated_at';\"",
    )
    run(
        client,
        "docker exec mesiri-postgres psql -U mesiri -d mesiri -c "
        '"SELECT column_name FROM information_schema.columns '
        "WHERE table_name='roles' AND column_name='created_at';\"",
    )

    # 5. Restart uvicorn
    print("\n=== Restarting uvicorn ===")
    run(client, "pkill -9 -f 'uvicorn main:app' || true")
    time.sleep(2)
    run(
        client,
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "PYTHONPATH=/opt/mesiri/apps/whatsapp-assistant/src:/opt/mesiri/backend/src:"
        "/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 "
        "--env-file /opt/mesiri/.env > /tmp/mesiri_uvicorn.log 2>&1 &",
    )
    time.sleep(3)
    run(client, "ps aux | grep 'uvicorn main:app' | grep -v grep || echo 'uvicorn not running'")

    client.close()
    print("\n[OK] Deploy complete.")


if __name__ == "__main__":
    main()
