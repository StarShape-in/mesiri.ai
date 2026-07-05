import paramiko, time

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

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
