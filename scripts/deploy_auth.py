import time

import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'
REMOTE_SRC = '/opt/mesiri/apps/whatsapp-assistant/src'

files = {
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\admin\router.py':   f'{REMOTE_SRC}/admin/router.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\auth\__init__.py':  f'{REMOTE_SRC}/auth/__init__.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\auth\router.py':    f'{REMOTE_SRC}/auth/router.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\users\__init__.py': f'{REMOTE_SRC}/users/__init__.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\users\router.py':   f'{REMOTE_SRC}/users/router.py',
    r'E:\Mesiri.AI\apps\whatsapp-assistant\src\runtime\lifecycle.py': f'{REMOTE_SRC}/runtime/lifecycle.py',
}

def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode()
    err = stderr.read().decode()
    return out, err

def deploy():
    print("Connecting...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    for local_path, remote_path in files.items():
        remote_dir = remote_path.rsplit('/', 1)[0]
        run(client, f"mkdir -p {remote_dir}")
        with open(local_path, encoding='utf-8') as f:
            content = f.read()
        hex_content = content.encode('utf-8').hex()
        write_script = f"import binascii; open('{remote_path}', 'wb').write(binascii.unhexlify('{hex_content}'))"
        out, err = run(client, f"python3 -c \"{write_script}\"")
        status = "ERROR: " + err if err else "OK"
        print(f"  {local_path.split(chr(92))[-1]}: {status}")

    # Kill & restart
    print("\nRestarting uvicorn...")
    run(client, "pkill -9 -f 'uvicorn main:app'")
    time.sleep(2)
    cmd = "/opt/mesiri/start_api.sh"
    run(client, cmd)
    time.sleep(4)

    # Verify routes
    print("\nRegistered routes:")
    out, _ = run(client, (
        "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
        "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
    ))
    print(out)

    # Test login with the Acme user we created earlier
    print("Testing login with provisioned credentials...")
    out, _ = run(client, (
        "curl -s -X POST http://127.0.0.1:8000/auth/login "
        "-H 'Content-Type: application/json' "
        "-d '{\"email\":\"admin@acmeconstruct.com\",\"password\":\"Acme1234!\"}'"
    ))
    print(out)

    client.close()
    print("\nDone!")

if __name__ == "__main__":
    deploy()
