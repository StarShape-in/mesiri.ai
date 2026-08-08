"""Fix alembic_version on prod and complete M6.5 migration sequence."""

from __future__ import annotations

import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VENV = "/opt/mesiri/.venv/bin"
BACKEND = "/opt/mesiri/backend"
ROOT = "/opt/mesiri"


def run(client: paramiko.SSHClient, cmd: str) -> tuple[str, str]:
    print(f"\n$ {cmd}")
    _, stdout, stderr = client.exec_command(cmd, get_pty=True)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out.strip():
        print(out)
    if err.strip():
        print(err)
    return out, err


def upload(client: paramiko.SSHClient, local: str, remote: str) -> None:
    with open(local, encoding="utf-8") as f:
        content = f.read()
    hex_content = content.encode("utf-8").hex()
    remote_dir = remote.rsplit("/", 1)[0]
    client.exec_command(f"mkdir -p {remote_dir}")
    write_script = (
        f"import binascii; open('{remote}', 'wb').write(binascii.unhexlify('{hex_content}'))"
    )
    _, _, stderr = client.exec_command(f'python3 -c "{write_script}"')
    err = stderr.read().decode()
    if err:
        raise RuntimeError(f"upload failed: {err}")
    print(f"uploaded {os.path.basename(local)}")


def main() -> int:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    upload(
        client,
        os.path.join(REPO, "backend", "migrations", "versions", "0180_material_add_catalog.py"),
        f"{BACKEND}/migrations/versions/0180_material_add_catalog.py",
    )

    run(client, f"cd {BACKEND} && {VENV}/alembic current")
    run(client, f"cd {BACKEND} && {VENV}/alembic upgrade 0180")
    run(client, f"cd {BACKEND} && {VENV}/alembic upgrade 0190")
    run(client, f"cd {ROOT} && {VENV}/python scripts/backfill_identity_bridge.py")
    run(
        client,
        f"docker exec -i mesiri-postgres psql -U mesiri -d mesiri < {ROOT}/scripts/verify_identity_bridge.sql",
    )
    run(client, f"cd {BACKEND} && {VENV}/alembic upgrade 0195")
    run(client, f"cd {BACKEND} && {VENV}/alembic current")

    run(client, "pkill -f 'uvicorn main:app' || true")
    run(client, f"cd {ROOT} && {VENV}/python scripts/restart_whatsapp_assistant.py")

    client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
