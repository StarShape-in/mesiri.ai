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

print("=== Installing passlib and PyJWT ===")
out, err = run(client, "/opt/mesiri/.venv/bin/pip install passlib[bcrypt] PyJWT 2>&1 | tail -5")
print(out)
if err:
    print("ERR:", err)

# Find mesiri_ai
print("=== Find mesiri_ai ===")
out, _ = run(client, "find /opt/mesiri -name 'mesiri_ai' -type d 2>/dev/null | grep -v __pycache__")
print(out if out.strip() else "NOT FOUND")

client.close()
