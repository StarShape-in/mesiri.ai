import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Quick verbose curl to see 500 error detail
stdin, stdout, stderr = client.exec_command(
    "curl -sv -X POST http://127.0.0.1:8000/auth/login "
    "-H 'Content-Type: application/json' "
    '-d \'{"email":"admin@acmeconstruct.com","password":"Acme1234!"}\' 2>&1'
)
print(stdout.read().decode("utf-8", errors="replace")[:2000])

# Also check the DB to see if the user exists
stdin, stdout, stderr = client.exec_command(
    "docker exec mesiri-postgres psql -U mesiri -c "
    '"SELECT id, email, role, organization_id, LEFT(hashed_password,20) FROM users;" 2>/dev/null '
    "|| docker exec $(docker ps --format '{{.Names}}' | grep postgres) psql -U mesiri -c "
    '"SELECT id, email, role FROM users;"'
)
print("\nDB users:")
print(stdout.read().decode("utf-8", errors="replace"))

client.close()
