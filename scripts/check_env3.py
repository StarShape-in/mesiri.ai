import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def inspect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== .whatsapp.env ===")
    stdin, stdout, stderr = client.exec_command("cat /opt/mesiri/.whatsapp.env")
    print(stdout.read().decode())

    print("=== pip list ===")
    stdin, stdout, stderr = client.exec_command("/opt/mesiri/.venv/bin/python3 -m pip list 2>&1 | head -50")
    print(stdout.read().decode())

    print("=== DB access in all python files ===")
    stdin, stdout, stderr = client.exec_command("grep -r 'postgres\\|asyncpg\\|DATABASE\\|psycopg' /opt/mesiri/apps --include='*.py' | head -20")
    print(stdout.read().decode())

    client.close()

if __name__ == "__main__":
    inspect()
