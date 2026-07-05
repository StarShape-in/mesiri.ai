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

# Check if the auth module is accessible from the running process
print("=== Check auth module is on VPS ===")
out, err = run(client, "ls /opt/mesiri/apps/whatsapp-assistant/src/auth/")
print(out)

print("=== Check uvicorn startup log ===")
out, err = run(client, "cat /tmp/mesiri_uvicorn.log | head -40")
print(out)
if err:
    print("STDERR:", err)

client.close()
