"""Verify and fix workflow_instance.py on prod."""

import os
import time

import paramiko

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def main() -> None:
    local = os.path.join(
        REPO, "apps", "whatsapp-assistant", "src", "backend", "postgres", "workflow_instance.py"
    )
    remote = "/opt/mesiri/apps/whatsapp-assistant/src/backend/postgres/workflow_instance.py"

    with open(local, encoding="utf-8") as f:
        content = f.read()

    c = paramiko.SSHClient()
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    c.connect(HOST, username=USER, password=PASS)

    sftp = c.open_sftp()
    with sftp.file(remote, "w") as rf:
        rf.write(content)
    sftp.close()

    _, o, _ = c.exec_command(f"grep -n CAST {remote}")
    print("remote grep:", o.read().decode())

    c.exec_command("pkill -9 -f 'uvicorn main:app'")
    time.sleep(2)
    c.exec_command(
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "export PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:"
        "/opt/mesiri/backend/src:/opt/mesiri/apps/whatsapp-assistant/src && "
        "set -a && . /opt/mesiri/.env && set +a && "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000 "
        "> /tmp/mesiri_uvicorn.log 2>&1 &"
    )
    time.sleep(4)
    _, o, _ = c.exec_command("curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/health")
    print("health:", o.read().decode())
    c.close()


if __name__ == "__main__":
    main()
