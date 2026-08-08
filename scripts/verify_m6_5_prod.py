"""Post-M6.5 prod verification queries."""

from __future__ import annotations

import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def run(client: paramiko.SSHClient, sql: str) -> None:
    cmd = f'docker exec mesiri-postgres psql -U mesiri -d mesiri -c "{sql}"'
    print(f"\n--- {sql[:80]}...")
    _, stdout, _ = client.exec_command(cmd)
    print(stdout.read().decode())


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    run(client, "SELECT version_num FROM alembic_version;")
    run(client, "SELECT COUNT(*) AS context_orgs FROM context_organizations;")
    run(client, "SELECT COUNT(*) AS external_ids FROM external_identities;")
    run(client, "SELECT COUNT(*) AS memberships FROM organization_memberships;")
    run(client, "SELECT id, whatsapp_number, status FROM users LIMIT 6;")
    run(
        client,
        "SELECT column_name, udt_name FROM information_schema.columns "
        "WHERE table_name='workflow_instances' AND column_name IN ('organization_id','user_id');",
    )
    run(
        client,
        "SELECT id, canonical_organization_id::text FROM context_organizations LIMIT 3;",
    )

    client.exec_command("pkill -9 -f 'uvicorn main:app' || true")
    import time

    time.sleep(2)
    client.exec_command(
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 "
        "--env-file /opt/mesiri/.env > /tmp/mesiri_uvicorn.log 2>&1 &"
    )
    time.sleep(3)
    _, stdout, _ = client.exec_command("ps aux | grep 'uvicorn main:app' | grep -v grep")
    proc = stdout.read().decode().strip()
    print("\nuvicorn:", proc or "(not running — check /tmp/mesiri_uvicorn.log)")

    client.close()


if __name__ == "__main__":
    main()
