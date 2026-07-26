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

# Install passlib using python -m ensurepip + pip
print("=== Installing pip + passlib ===")
out, err = run(client, "/opt/mesiri/.venv/bin/python3 -m ensurepip 2>&1 | tail -3")
print(out)
out, err = run(
    client, "/opt/mesiri/.venv/bin/python3 -m pip install passlib[bcrypt] PyJWT 2>&1 | tail -5"
)
print(out)

client.close()
