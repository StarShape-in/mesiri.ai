import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def check():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # Quick test of the provision endpoint
    print("=== Testing provision endpoint ===")
    stdin, stdout, stderr = client.exec_command(
        "curl -s -X POST http://127.0.0.1:8000/admin/organizations/provision "
        "-H 'Content-Type: application/json' "
        '-d \'{"name":"Test Co","deployment_type":"SaaS","db_route":"shared-cluster-01",'
        '"admin_name":"Test Admin","admin_email":"testadmin@test.com","admin_password":"Test1234!"}\''
    )
    print(stdout.read().decode())
    print(stderr.read().decode())

    # Check env vars for DB
    print("\n=== Env vars set for uvicorn process ===")
    stdin, stdout, stderr = client.exec_command(
        "cat /proc/$(pgrep -f 'uvicorn main:app' | head -1)/environ | tr '\\0' '\\n' | grep -Ei 'MESIRI_POSTGRES|POSTGRES|DATABASE'"
    )
    print(stdout.read().decode())

    client.close()


if __name__ == "__main__":
    check()
