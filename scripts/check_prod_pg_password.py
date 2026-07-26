"""Fetch the prod postgres password from the .env file on the VPS."""
from __future__ import annotations

import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Check the .env file for postgres settings
cmds = [
    "cat /opt/mesiri/.env 2>/dev/null | grep -i postgres",
    "cat /opt/mesiri/.whatsapp.env 2>/dev/null | grep -i postgres",
    "docker inspect mesiri-postgres 2>/dev/null | grep -i POSTGRES_PASSWORD",
    "docker exec mesiri-postgres env 2>/dev/null | grep -i POSTGRES",
]

for cmd in cmds:
    print(f"\n>>> {cmd}")
    _, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err and "No such file" not in err:
        print("STDERR:", err[:200])

client.close()
