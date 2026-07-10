import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def inspect_backend():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # Let's find where app.py or uvicorn is running
    print("Checking running processes...")
    stdin, stdout, stderr = client.exec_command("ps aux | grep -i uvicorn")
    print(stdout.read().decode("utf-8"))

    # Check for mesiri directory
    stdin, stdout, stderr = client.exec_command(
        "find / -type d -name 'mesiri' -not -path '*/\.*' 2>/dev/null | head -n 5"
    )
    print("Found 'mesiri' directories:")
    print(stdout.read().decode("utf-8"))

    client.close()


if __name__ == "__main__":
    inspect_backend()
