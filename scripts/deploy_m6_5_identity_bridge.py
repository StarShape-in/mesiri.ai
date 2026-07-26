"""Deploy M6.5 Canonical Identity Bridge — code sync + migration sequence.

Uploads migrations, contracts, assistant M6.5 code, then runs:
  alembic current
  alembic stamp 0060   (only if still on legacy revision)
  alembic upgrade 0180
  alembic upgrade 0190
  python scripts/backfill_identity_bridge.py
  psql verify
  alembic upgrade 0195
  restart uvicorn

Usage:
    python scripts/deploy_m6_5_identity_bridge.py
"""

from __future__ import annotations

import os
import time

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REMOTE_ROOT = "/opt/mesiri"
VENV = f"{REMOTE_ROOT}/.venv/bin"
BACKEND = f"{REMOTE_ROOT}/backend"
WA_SRC = f"{REMOTE_ROOT}/apps/whatsapp-assistant/src"


def _upload_file(client: paramiko.SSHClient, local: str, remote: str) -> None:
    remote_dir = remote.rsplit("/", 1)[0]
    client.exec_command(f"mkdir -p {remote_dir}")
    with open(local, encoding="utf-8") as f:
        content = f.read()
    hex_content = content.encode("utf-8").hex()
    write_script = (
        f"import binascii; open('{remote}', 'wb').write(binascii.unhexlify('{hex_content}'))"
    )
    _, stdout, stderr = client.exec_command(f'python3 -c "{write_script}"')
    err = stderr.read().decode()
    if err:
        raise RuntimeError(f"upload failed {local} -> {remote}: {err}")
    print(f"  OK {os.path.relpath(local, REPO)}")


def _run(client: paramiko.SSHClient, cmd: str, *, label: str | None = None) -> tuple[str, str]:
    if label:
        print(f"\n=== {label} ===")
    print(f"$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out)
    if err.strip():
        print(err)
    return out, err


def _sync_tree(client: paramiko.SSHClient, local_dir: str, remote_dir: str, suffix: str) -> None:
    if not os.path.isdir(local_dir):
        return
    for root, _, files in os.walk(local_dir):
        for name in files:
            if not name.endswith(suffix):
                continue
            local_path = os.path.join(root, name)
            rel = os.path.relpath(local_path, local_dir).replace("\\", "/")
            remote_path = f"{remote_dir}/{rel}"
            _upload_file(client, local_path, remote_path)


def deploy() -> int:
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("\n=== Upload migrations ===")
    migrations_local = os.path.join(REPO, "backend", "migrations", "versions")
    _sync_tree(client, migrations_local, f"{BACKEND}/migrations/versions", ".py")

    print("\n=== Upload shared contracts v2 ===")
    contracts_local = os.path.join(REPO, "shared", "contracts", "src", "mesiri_contracts")
    _sync_tree(
        client, contracts_local, f"{REMOTE_ROOT}/shared/contracts/src/mesiri_contracts", ".py"
    )

    print("\n=== Upload whatsapp-assistant M6.5 code ===")
    wa_local = os.path.join(REPO, "apps", "whatsapp-assistant", "src")
    for rel in (
        "context/identity_bridge.py",
        "context/identity_projection.py",
        "context/resolver.py",
        "context/runtime.py",
        "context/seed.py",
        "context/ports.py",
        "context/errors.py",
        "canonicalization/builder.py",
        "planner/planner.py",
        "workflows/runtime.py",
        "workflows/ports.py",
        "workflows/fakes.py",
        "workflows/material/nodes.py",
        "backend/postgres/workflow_instance.py",
        "runtime/inbound_journey.py",
    ):
        local = os.path.join(wa_local, rel.replace("/", os.sep))
        remote = f"{WA_SRC}/{rel}"
        if os.path.isfile(local):
            _upload_file(client, local, remote)

    print("\n=== Upload scripts ===")
    for rel in ("scripts/backfill_identity_bridge.py", "scripts/verify_identity_bridge.sql"):
        _upload_file(client, os.path.join(REPO, rel), f"{REMOTE_ROOT}/{rel}")

    out, _ = _run(client, f"cd {BACKEND} && {VENV}/alembic current", label="Alembic current")

    if "0060" not in out and "0070" not in out and "0180" not in out and "0190" not in out:
        # Legacy hash revision on prod — stamp to semantic 0060 first.
        if "f7g8h9i0j1k2" in out or len(out.strip()) < 5:
            _run(client, f"cd {BACKEND} && {VENV}/alembic stamp 0060", label="Stamp 0060")

    _run(client, f"cd {BACKEND} && {VENV}/alembic upgrade 0180", label="Upgrade 0180")
    _run(client, f"cd {BACKEND} && {VENV}/alembic upgrade 0190", label="Upgrade 0190")

    _run(
        client,
        f"cd {REMOTE_ROOT} && {VENV}/python scripts/backfill_identity_bridge.py",
        label="Backfill identity bridge",
    )

    _run(
        client,
        "docker exec -i mesiri-postgres psql -U mesiri -d mesiri "
        f"< {REMOTE_ROOT}/scripts/verify_identity_bridge.sql",
        label="Verify bridge SQL",
    )

    _run(client, f"cd {BACKEND} && {VENV}/alembic upgrade 0195", label="Upgrade 0195")
    _run(client, f"cd {BACKEND} && {VENV}/alembic current", label="Final alembic revision")

    print("\n=== Restart uvicorn ===")
    client.exec_command("pkill -f 'uvicorn main:app'")
    time.sleep(2)
    _run(
        client,
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        f"nohup {VENV}/uvicorn main:app --host 127.0.0.1 --port 8000 "
        f"--env-file {REMOTE_ROOT}/.env > /tmp/mesiri_uvicorn.log 2>&1 &",
        label="Start uvicorn",
    )
    time.sleep(3)
    _run(client, "ps aux | grep 'uvicorn main:app' | grep -v grep", label="Process check")

    client.close()
    print("\nM6.5 deploy complete.")
    return 0


if __name__ == "__main__":
    raise SystemExit(deploy())
