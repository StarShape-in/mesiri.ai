import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def check_status():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== Backend Process ===")
    stdin, stdout, stderr = client.exec_command("ps aux | grep uvicorn | grep -v grep")
    print(stdout.read().decode())

    print("=== Last 50 lines of backend logs ===")
    stdin, stdout, stderr = client.exec_command(
        "journalctl -u mesiri --no-pager -n 50 2>/dev/null || journalctl --no-pager -n 50 2>/dev/null | tail -50"
    )
    print(stdout.read().decode())

    print("=== Test /admin/organizations/provision endpoint directly ===")
    stdin, stdout, stderr = client.exec_command(
        "curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/admin/organizations/provision -X POST "
        "-H 'Content-Type: application/json' "
        '-d \'{"name":"test","deployment_type":"SaaS","db_route":"shared","admin_name":"test","admin_email":"test@test.com","admin_password":"test1234"}\''
    )
    code = stdout.read().decode()
    print(f"HTTP Status: {code}")
    err = stderr.read().decode()
    if err:
        print(f"Error: {err}")

    print("=== Check routes registered ===")
    stdin, stdout, stderr = client.exec_command(
        "curl -s http://127.0.0.1:8000/openapi.json | python3 -c \"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
    )
    print(stdout.read().decode())

    client.close()


if __name__ == "__main__":
    check_status()
