import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def inspect_db():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    stdin, stdout, stderr = client.exec_command(
        "docker inspect mesiri-postgres | grep POSTGRES_USER"
    )
    print("User Env:", stdout.read().decode("utf-8").strip())

    client.close()


if __name__ == "__main__":
    inspect_db()
