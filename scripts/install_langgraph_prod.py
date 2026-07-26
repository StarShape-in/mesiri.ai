"""Install langgraph on prod venv via ensurepip."""
import os
import time

import paramiko

c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect(
    os.environ["MESIRI_VPS_HOST"],
    username=os.environ["MESIRI_VPS_USER"],
    password=os.environ["MESIRI_VPS_PASSWORD"],
)

cmds = [
    "/opt/mesiri/.venv/bin/python -m ensurepip --upgrade",
    "/opt/mesiri/.venv/bin/python -m pip install 'langgraph>=0.2' langgraph-checkpoint",
    "cd /opt/mesiri && export PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/platform/ai/src:/opt/mesiri/backend/src:/opt/mesiri/apps/whatsapp-assistant/src && /opt/mesiri/.venv/bin/python -c 'import langgraph; print(langgraph.__version__)'",
]
for cmd in cmds:
    print("===", cmd)
    _, o, e = c.exec_command(cmd, get_pty=True)
    print(o.read().decode(errors="replace"))
    err = e.read().decode(errors="replace")
    if err:
        print(err)

c.exec_command(
    "cd /opt/mesiri && /opt/mesiri/.venv/bin/python scripts/restart_whatsapp_assistant.py"
)
time.sleep(5)
c.close()
