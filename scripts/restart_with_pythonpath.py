import paramiko, time

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def run(client, cmd, block=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    if block:
        return stdout.read().decode(), stderr.read().decode()
    return "", ""

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Kill old uvicorn
print("Killing old uvicorn...")
run(client, "pkill -9 -f 'uvicorn main:app'")
time.sleep(2)

# Start with PYTHONPATH set to include mesiri_contracts
print("Restarting with PYTHONPATH fixed...")
cmd = (
    "cd /opt/mesiri/apps/whatsapp-assistant/src && "
    "export $(cat /opt/mesiri/.whatsapp.env | xargs) && "
    "export PYTHONPATH=/opt/mesiri/shared/contracts/src:/opt/mesiri/apps/whatsapp-assistant/src && "
    "nohup /opt/mesiri/.venv/bin/uvicorn main:app "
    "--host 127.0.0.1 --port 8000 "
    "> /tmp/mesiri_uvicorn.log 2>&1 &"
)
run(client, cmd, block=False)
time.sleep(5)

# Verify routes
print("Checking routes...")
out, _ = run(client, (
    "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
    "\"import sys,json; d=json.load(sys.stdin); [print(k) for k in d.get('paths',{}).keys()]\""
))
print(out)

if not out.strip():
    print("App may still be starting. Checking log...")
    out, _ = run(client, "tail -20 /tmp/mesiri_uvicorn.log")
    print(out)

client.close()
