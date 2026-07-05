import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Write a python script to the VPS that does the update directly via asyncpg
fix_script = r"""
import asyncio
import asyncpg
from passlib.context import CryptContext

async def fix():
    ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
    h = ctx.hash('Acme1234!')
    conn = await asyncpg.connect('postgresql://mesiri:mesiri_local_dev@localhost:5432/mesiri')
    result = await conn.execute("UPDATE users SET hashed_password=$1 WHERE email='admin@acmeconstruct.com'", h)
    print(f'Updated: {result}')
    # Verify
    row = await conn.fetchrow("SELECT hashed_password FROM users WHERE email='admin@acmeconstruct.com'")
    print(f'Hash ok: {ctx.verify("Acme1234!", row["hashed_password"])}')
    await conn.close()

asyncio.run(fix())
"""

# Write to a temp file on VPS
sftp = client.open_sftp()
with sftp.open('/tmp/fix_password.py', 'w') as f:
    f.write(fix_script)
sftp.close()

stdin, stdout, stderr = client.exec_command("/opt/mesiri/.venv/bin/python3 /tmp/fix_password.py")
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("OUT:", out)
if err:
    print("ERR:", err[:500])

# Test login
stdin, stdout, stderr = client.exec_command(
    "curl -s -X POST http://127.0.0.1:8000/auth/login "
    "-H 'Content-Type: application/json' "
    "-d '{\"email\":\"admin@acmeconstruct.com\",\"password\":\"Acme1234!\"}'"
)
print("\nLogin response:", stdout.read().decode('utf-8', errors='replace'))

client.close()
