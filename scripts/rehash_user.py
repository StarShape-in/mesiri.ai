import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Generate the correct bcrypt hash for Acme1234! and update the user
update_script = """
import sys
sys.path.insert(0, '/opt/mesiri/apps/whatsapp-assistant/src')
from passlib.context import CryptContext
ctx = CryptContext(schemes=['bcrypt'], deprecated='auto')
h = ctx.hash('Acme1234!')
print(h)
"""
stdin, stdout, stderr = client.exec_command(
    f'/opt/mesiri/.venv/bin/python3 -c "{update_script.strip()}"'
)
bcrypt_hash = stdout.read().decode("utf-8", errors="replace").strip()
print(f"Generated bcrypt hash: {bcrypt_hash[:30]}...")

# Update the user's password in postgres
stdin, stdout, stderr = client.exec_command(
    f"docker exec mesiri-postgres psql -U mesiri -c "
    f"\"UPDATE users SET hashed_password='{bcrypt_hash}' WHERE email='admin@acmeconstruct.com';\""
)
print("DB update:", stdout.read().decode("utf-8", errors="replace"))

# Now test login again
print("\nTesting login again...")
stdin, stdout, stderr = client.exec_command(
    "curl -s -X POST http://127.0.0.1:8000/auth/login "
    "-H 'Content-Type: application/json' "
    '-d \'{"email":"admin@acmeconstruct.com","password":"Acme1234!"}\''
)
print(stdout.read().decode("utf-8", errors="replace"))

client.close()
