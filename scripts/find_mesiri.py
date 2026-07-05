import paramiko, time

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

# Find where mesiri package lives on VPS
print("=== Find mesiri package ===")
out, _ = run(client, "find /opt/mesiri -name 'mesiri' -type d 2>/dev/null | grep -v venv | grep -v __pycache__")
print(out)

print("=== The editable finder ===")
out, _ = run(client, "cat /opt/mesiri/.venv/lib/python3.12/site-packages/__editable___mesiri_runtime_0_1_0_finder.py")
print(out)

client.close()
