"""Restart whatsapp assistant with correct PYTHONPATH after M6.5 deploy."""

from __future__ import annotations

import time

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"

PYTHONPATH = (
    "/opt/mesiri/shared/contracts/src:"
    "/opt/mesiri/platform/ai/src:"
    "/opt/mesiri/backend/src:"
    "/opt/mesiri/apps/whatsapp-assistant/src"
)


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    client.exec_command("pkill -9 -f 'uvicorn main:app' || true")
    time.sleep(2)

    cmd = (
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        f"export PYTHONPATH={PYTHONPATH} && "
        "set -a && [ -f /opt/mesiri/.env ] && . /opt/mesiri/.env; set +a && "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 "
        "> /tmp/mesiri_uvicorn.log 2>&1 &"
    )
    client.exec_command(cmd)
    time.sleep(5)

    _, stdout, _ = client.exec_command("ps aux | grep 'uvicorn main:app' | grep -v grep")
    proc = stdout.read().decode().strip()
    print("uvicorn:", proc or "(not running)")

    _, stdout, _ = client.exec_command("tail -15 /tmp/mesiri_uvicorn.log")
    print(stdout.read().decode(errors="replace"))

    _, stdout, _ = client.exec_command(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health || true"
    )
    print("health:", stdout.read().decode().strip())

    client.close()


if __name__ == "__main__":
    main()
