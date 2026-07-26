import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def run(client, cmd):
    stdin, stdout, stderr = client.exec_command(cmd)
    return stdout.read().decode(), stderr.read().decode()


client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

print("=== Last 30 lines of uvicorn log ===")
out, _ = run(client, "tail -30 /tmp/mesiri_uvicorn.log")
print(out)

client.close()
