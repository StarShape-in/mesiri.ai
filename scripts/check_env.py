import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def inspect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== .env file ===")
    stdin, stdout, stderr = client.exec_command(
        "cat /opt/mesiri/apps/whatsapp-assistant/src/.env 2>/dev/null || cat /opt/mesiri/.env 2>/dev/null"
    )
    print(stdout.read().decode())

    print("=== Packages installed ===")
    stdin, stdout, stderr = client.exec_command(
        "/opt/mesiri/.venv/bin/pip list | grep -Ei 'sqlalchemy|asyncpg|psycopg|databases'"
    )
    print(stdout.read().decode())

    print("=== All python files in src ===")
    stdin, stdout, stderr = client.exec_command(
        "find /opt/mesiri/apps/whatsapp-assistant/src -name '*.py' | head -30"
    )
    print(stdout.read().decode())

    client.close()


if __name__ == "__main__":
    inspect()
