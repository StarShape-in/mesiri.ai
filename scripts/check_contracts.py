import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def run(client, cmd, block=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    if block:
        return stdout.read().decode(), stderr.read().decode()
    return "", ""


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# First, check git status to get the clean receiver.py
print("=== Check git log ===")
out, _ = run(client, "cd /opt/mesiri && git log --oneline -5 2>/dev/null || echo 'no git'")
print(out)

print("=== Check mesiri_contracts ===")
out, _ = run(client, "ls /opt/mesiri/.venv/lib/python3.12/site-packages/ | grep mesiri")
print(out)

print("=== Check editable installs ===")
out, _ = run(
    client,
    "cat /opt/mesiri/.venv/lib/python3.12/site-packages/__editable__.mesiri_runtime-0.1.0.pth",
)
print(out)

print("=== Check if mesiri_contracts is in the monorepo ===")
out, _ = run(client, "find /opt/mesiri -name 'mesiri_contracts' -type d 2>/dev/null | head -5")
print(out)

client.close()
