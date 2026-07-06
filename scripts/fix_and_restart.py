import time

import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def run(client, cmd, block=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    if block:
        return stdout.read().decode(), stderr.read().decode()
    return "", ""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Kill old
print("Stopping old uvicorn...")
run(client, "pkill -9 -f 'uvicorn main:app'")
time.sleep(2)

# Write a systemd-like startup script so PYTHONPATH is always set correctly
startup_script = """#!/bin/bash
export $(cat /opt/mesiri/.whatsapp.env | xargs)
export PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/backend/src:/opt/mesiri/apps/whatsapp-assistant/src
cd /opt/mesiri/apps/whatsapp-assistant/src
exec /opt/mesiri/.venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
"""
run(client, f"cat > /opt/mesiri/start_api.sh << 'SCRIPT'\n{startup_script}\nSCRIPT")
run(client, "chmod +x /opt/mesiri/start_api.sh")

# Start with nohup using the script
print("Starting with correct PYTHONPATH...")
run(client, "nohup /opt/mesiri/start_api.sh > /tmp/mesiri_uvicorn.log 2>&1 &", block=False)
time.sleep(6)

# Verify
print("Checking routes...")
out, _ = run(client, (
    "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
    "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
))
print(out if out.strip() else "(no response)")

if not out.strip():
    out, _ = run(client, "tail -30 /tmp/mesiri_uvicorn.log")
    print("Log:", out)

# Test login if routes are up
if "/auth/login" in out:
    print("Testing login...")
    out, _ = run(client, (
        "curl -s -X POST http://127.0.0.1:8000/auth/login "
        "-H 'Content-Type: application/json' "
        "-d '{\"email\":\"admin@acmeconstruct.com\",\"password\":\"Acme1234!\"}'"
    ))
    print(out)

client.close()
print("Done!")
