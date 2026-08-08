import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def inspect():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("=== Find main.py ===")
    stdin, stdout, stderr = client.exec_command("find /opt/mesiri -name 'main.py' 2>/dev/null")
    print(stdout.read().decode())

    print("=== Content of main.py ===")
    stdin, stdout, stderr = client.exec_command("cat /opt/mesiri/main.py")
    print(stdout.read().decode())

    print("=== Systemd unit ===")
    stdin, stdout, stderr = client.exec_command(
        "cat /etc/systemd/system/mesiri.service 2>/dev/null || cat /etc/systemd/system/mesiri-assistant.service 2>/dev/null || systemctl status mesiri --no-pager 2>&1 | head -30"
    )
    print(stdout.read().decode())

    client.close()


if __name__ == "__main__":
    inspect()
