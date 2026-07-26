import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

print("=== Full startup log ===")
out, err = run(client, "cat /tmp/mesiri_uvicorn.log")
print(out[-3000:])

print("=== Test import manually ===")
out, err = run(
    client,
    (
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "/opt/mesiri/.venv/bin/python3 -c 'from runtime.lifecycle import create_app; print(\"OK\")' 2>&1"
    ),
)
print(out)
print(err)

client.close()
