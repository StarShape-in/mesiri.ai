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

print("=== Log tail ===")
out, _ = run(client, "tail -20 /tmp/mesiri_uvicorn.log")
print(out)

print("\n=== All routes ===")
out, _ = run(client, (
    "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
    "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
))
print(out)

client.close()
