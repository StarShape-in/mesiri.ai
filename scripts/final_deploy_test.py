import time

import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'
REMOTE_SRC = '/opt/mesiri/apps/whatsapp-assistant/src'

def run(client, cmd, block=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    if block:
        return stdout.read().decode('utf-8', errors='replace'), stderr.read().decode('utf-8', errors='replace')
    return "", ""

def upload(client, local_path, remote_path):
    sftp = client.open_sftp()
    with open(local_path, encoding='utf-8') as f:
        content = f.read()
    with sftp.open(remote_path, 'w') as f:
        f.write(content)
    sftp.close()

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Upload files via SFTP (no hex encoding)
print("Uploading files via SFTP...")
upload(client, r'E:\Mesiri.AI\apps\whatsapp-assistant\src\auth\router.py', f'{REMOTE_SRC}/auth/router.py')
upload(client, r'E:\Mesiri.AI\apps\whatsapp-assistant\src\admin\router.py', f'{REMOTE_SRC}/admin/router.py')
print("  OK")

# Kill & restart
print("Restarting uvicorn...")
run(client, "pkill -9 -f 'uvicorn main:app'")
run(client, "pkill -9 -f 'start_api.sh'")
time.sleep(2)
run(client, "nohup /opt/mesiri/start_api.sh > /tmp/mesiri_uvicorn.log 2>&1 &", block=False)
time.sleep(6)

# Re-hash the existing user password correctly
fix_script = r"""
import asyncio, bcrypt as bc, asyncpg

async def fix():
    h = bc.hashpw(b'Acme1234!', bc.gensalt()).decode()
    conn = await asyncpg.connect('postgresql://mesiri:mesiri_local_dev@localhost:5432/mesiri')
    await conn.execute("UPDATE users SET hashed_password=$1 WHERE email='admin@acmeconstruct.com'", h)
    row = await conn.fetchrow("SELECT hashed_password FROM users WHERE email='admin@acmeconstruct.com'")
    print('Verify:', bc.checkpw(b'Acme1234!', row['hashed_password'].encode()))
    await conn.close()

asyncio.run(fix())
"""

sftp = client.open_sftp()
with sftp.open('/tmp/fix_pw.py', 'w') as f:
    f.write(fix_script)
sftp.close()
print("\nRe-hashing existing user password...")
out, err = run(client, "/opt/mesiri/.venv/bin/python3 /tmp/fix_pw.py")
print("OUT:", out)
if err:
    print("ERR:", err[:300])

# Check routes
print("\nRoutes:")
out, _ = run(client, (
    "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
    "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
))
print(out if out.strip() else "(no response)")

# Test login
print("Testing login...")
out, _ = run(client, (
    "curl -s -X POST http://127.0.0.1:8000/auth/login "
    "-H 'Content-Type: application/json' "
    "-d '{\"email\":\"admin@acmeconstruct.com\",\"password\":\"Acme1234!\"}'"
))
print(out)

client.close()
print("\nDone!")
