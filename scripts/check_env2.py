import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def inspect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== All env files ===")
    stdin, stdout, stderr = client.exec_command("find /opt/mesiri -name '*.env' -o -name '.env' 2>/dev/null | head -20")
    print(stdout.read().decode())
    
    print("=== Pip list (all) ===")
    stdin, stdout, stderr = client.exec_command("/opt/mesiri/.venv/bin/pip list 2>/dev/null | head -40")
    print(stdout.read().decode())
    
    print("=== Database access patterns in src ===")
    stdin, stdout, stderr = client.exec_command("grep -r 'DATABASE\\|postgres\\|psycopg\\|asyncpg\\|sqlalchemy' /opt/mesiri/apps/whatsapp-assistant/src --include='*.py' -l")
    print(stdout.read().decode())

    client.close()

if __name__ == "__main__":
    inspect()
