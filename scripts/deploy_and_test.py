import paramiko, time

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'
REMOTE_SRC = '/opt/mesiri/apps/whatsapp-assistant/src'

def deploy():
    print("Connecting...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # Upload fixed router
    local_path = r'E:\Mesiri.AI\apps\whatsapp-assistant\src\admin\router.py'
    remote_path = f'{REMOTE_SRC}/admin/router.py'
    with open(local_path, 'r', encoding='utf-8') as f:
        content = f.read()
    hex_content = content.encode('utf-8').hex()
    write_script = f"import binascii; open('{remote_path}', 'wb').write(binascii.unhexlify('{hex_content}'))"
    stdin, stdout, stderr = client.exec_command(f"python3 -c \"{write_script}\"")
    stdout.read()
    print("Uploaded router.py")

    # Kill uvicorn
    print("Killing uvicorn...")
    client.exec_command("pkill -9 -f 'uvicorn main:app'")
    time.sleep(2)

    # Restart using env file
    print("Restarting uvicorn...")
    cmd = (
        "cd /opt/mesiri/apps/whatsapp-assistant/src && "
        "export $(cat /opt/mesiri/.whatsapp.env | xargs) && "
        "nohup /opt/mesiri/.venv/bin/uvicorn main:app "
        "--host 127.0.0.1 --port 8000 "
        "> /tmp/mesiri_uvicorn.log 2>&1 &"
    )
    client.exec_command(cmd)
    time.sleep(3)

    # Verify
    print("Verifying process...")
    stdin, stdout, stderr = client.exec_command("ps aux | grep 'uvicorn main:app' | grep -v grep")
    print(stdout.read().decode())

    # Verify routes
    print("Checking routes...")
    stdin, stdout, stderr = client.exec_command(
        "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
        "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
    )
    print(stdout.read().decode())

    # Quick test
    print("Testing provision...")
    stdin, stdout, stderr = client.exec_command(
        "curl -s -X POST http://127.0.0.1:8000/admin/organizations/provision "
        "-H 'Content-Type: application/json' "
        "-d '{\"name\":\"Acme Construction\",\"deployment_type\":\"SaaS\",\"db_route\":\"shared-cluster-01\","
        "\"admin_name\":\"Acme Admin\",\"admin_email\":\"admin@acmeconstruct.com\",\"admin_password\":\"Acme1234!\"}'"
    )
    print(stdout.read().decode())

    client.close()
    print("Done!")

if __name__ == "__main__":
    deploy()
