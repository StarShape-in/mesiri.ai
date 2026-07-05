import os
import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

REMOTE_SRC = '/opt/mesiri/apps/whatsapp-assistant/src'

# Files to deploy — local path -> remote path
files_to_deploy = {
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\admin\__init__.py': f'{REMOTE_SRC}/admin/__init__.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\admin\router.py': f'{REMOTE_SRC}/admin/router.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\runtime\lifecycle.py': f'{REMOTE_SRC}/runtime/lifecycle.py',
}

def deploy():
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    for local_path, remote_path in files_to_deploy.items():
        remote_dir = remote_path.rsplit('/', 1)[0]
        client.exec_command(f"mkdir -p {remote_dir}")

        print(f"Uploading {local_path} -> {remote_path}")
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
            hex_content = content.encode('utf-8').hex()
            write_script = f"import binascii; open('{remote_path}', 'wb').write(binascii.unhexlify('{hex_content}'))"
            stdin, stdout, stderr = client.exec_command(f"python3 -c \"{write_script}\"")
            err = stderr.read().decode()
            if err:
                print(f"  ERROR: {err}")
            else:
                print(f"  OK")
        except Exception as e:
            print(f"  FAILED: {e}")

    # Also deploy the alembic migration files
    migration_files = {
        r'E:\Mesiri.AI\backend\migrations\versions\c4936d8bcaec_add_users_table.py': '/opt/mesiri/backend/migrations/versions/c4936d8bcaec_add_users_table.py',
        r'E:\Mesiri.AI\backend\migrations\versions\d5a47e9cdbfd_add_organizations_table.py': '/opt/mesiri/backend/migrations/versions/d5a47e9cdbfd_add_organizations_table.py',
    }
    for local_path, remote_path in migration_files.items():
        remote_dir = remote_path.rsplit('/', 1)[0]
        client.exec_command(f"mkdir -p {remote_dir}")
        try:
            with open(local_path, 'r', encoding='utf-8') as f:
                content = f.read()
            hex_content = content.encode('utf-8').hex()
            write_script = f"import binascii; open('{remote_path}', 'wb').write(binascii.unhexlify('{hex_content}'))"
            client.exec_command(f"python3 -c \"{write_script}\"")
        except Exception as e:
            print(f"  Migration upload failed: {e}")

    # Run Alembic migration
    print("\nRunning Alembic migration...")
    stdin, stdout, stderr = client.exec_command(
        "cd /opt/mesiri/backend && /opt/mesiri/.venv/bin/alembic upgrade head"
    )
    out = stdout.read().decode()
    err = stderr.read().decode()
    if out:
        print(out)
    if err:
        print("Alembic:", err)

    # Restart uvicorn
    print("\nRestarting uvicorn...")
    # Kill current and let it restart via nohup/supervisor — or re-launch it
    stdin, stdout, stderr = client.exec_command("pkill -f 'uvicorn main:app'")
    stdout.read()  # wait
    import time
    time.sleep(2)
    # Re-launch
    stdin, stdout, stderr = client.exec_command(
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app "
        "--host 127.0.0.1 --port 8000 "
        f"--env-file /opt/mesiri/.whatsapp.env "
        "> /tmp/mesiri_uvicorn.log 2>&1 &"
    )
    stdout.read()
    time.sleep(3)

    # Verify it's running
    print("Verifying restart...")
    stdin, stdout, stderr = client.exec_command("ps aux | grep 'uvicorn main:app' | grep -v grep")
    print(stdout.read().decode())

    # Verify routes
    print("Checking registered routes...")
    stdin, stdout, stderr = client.exec_command(
        "curl -s http://127.0.0.1:8000/openapi.json | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
    )
    print(stdout.read().decode())

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    deploy()
