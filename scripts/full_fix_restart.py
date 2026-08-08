import os
import time

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def run(client, cmd, block=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    if block:
        out = stdout.read().decode("utf-8", errors="replace")
        err = stderr.read().decode("utf-8", errors="replace")
        return out, err
    return "", ""


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

print("=== Installing passlib, PyJWT ===")
out, err = run(
    client, "/opt/mesiri/.venv/bin/python3 -m pip install passlib[bcrypt] PyJWT 2>&1 | tail -5"
)
print(out[:500])

# Now kill and restart with full PYTHONPATH including mesiri_ai and all necessary paths
print("\n=== Restarting with full PYTHONPATH ===")
run(client, "pkill -9 -f 'uvicorn main:app'")
run(client, "pkill -9 -f 'start_api.sh'")
time.sleep(2)

# Write the final startup script
startup = (
    "#!/bin/bash\n"
    "export $(cat /opt/mesiri/.whatsapp.env | xargs)\n"
    "export PYTHONPATH="
    "/opt/mesiri/shared/contracts/src"
    ":/opt/mesiri/backend/src"
    ":/opt/mesiri/platform/ai/src"
    ":/opt/mesiri/apps/whatsapp-assistant/src\n"
    "cd /opt/mesiri/apps/whatsapp-assistant/src\n"
    "exec /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000\n"
)
run(client, f"printf '%s' '{startup}' > /opt/mesiri/start_api.sh")
run(client, "chmod +x /opt/mesiri/start_api.sh")

run(client, "nohup /opt/mesiri/start_api.sh > /tmp/mesiri_uvicorn.log 2>&1 &", block=False)
time.sleep(7)

print("=== Routes ===")
out, _ = run(
    client,
    (
        "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
        "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
    ),
)
print(out if out.strip() else "No response")

if not out.strip():
    out, _ = run(client, "tail -25 /tmp/mesiri_uvicorn.log")
    print("Log:", out[:2000])

if "/auth/login" in out:
    print("\n=== Testing login ===")
    out2, _ = run(
        client,
        (
            "curl -s -X POST http://127.0.0.1:8000/auth/login "
            "-H 'Content-Type: application/json' "
            '-d \'{"email":"admin@acmeconstruct.com","password":"Acme1234!"}\''
        ),
    )
    print(out2)

client.close()
print("Done!")
