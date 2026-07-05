import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def inspect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # Find all site packages
    print("=== Site packages ===")
    stdin, stdout, stderr = client.exec_command("ls /opt/mesiri/.venv/lib/python3.12/site-packages/ | grep -Ei 'sqlalchemy|asyncpg|psycopg|databases'")
    print(stdout.read().decode())

    print("=== All packages ===")
    stdin, stdout, stderr = client.exec_command("ls /opt/mesiri/.venv/lib/python3.12/site-packages/ | head -60")
    print(stdout.read().decode())

    print("=== Check DB usage in understanding files ===")
    stdin, stdout, stderr = client.exec_command("find /opt/mesiri/apps/whatsapp-assistant/src -name '*.py' -exec grep -l 'execute\\|cursor\\|query\\|INSERT\\|SELECT' {} \\; 2>/dev/null")
    print(stdout.read().decode())

    client.close()

if __name__ == "__main__":
    inspect()
