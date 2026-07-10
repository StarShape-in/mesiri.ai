import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def inspect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== Real uvicorn command ===")
    stdin, stdout, stderr = client.exec_command(
        "cat /proc/$(pgrep -f 'uvicorn main:app' | head -1)/cmdline | tr '\\0' ' '"
    )
    print(stdout.read().decode())

    print("=== CWD of uvicorn ===")
    stdin, stdout, stderr = client.exec_command(
        "ls -la /proc/$(pgrep -f 'uvicorn main:app' | head -1)/cwd"
    )
    print(stdout.read().decode())

    print("=== Content of actual main.py ===")
    stdin, stdout, stderr = client.exec_command(
        "cat $(readlink /proc/$(pgrep -f 'uvicorn main:app' | head -1)/cwd)/main.py"
    )
    print(stdout.read().decode())

    client.close()


if __name__ == "__main__":
    inspect()
