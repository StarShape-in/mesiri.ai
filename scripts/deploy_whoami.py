"""Deploy the updated whoami reply to the live whatsapp-assistant on the VPS.

Uploads:
  - apps/whatsapp-assistant/src/context/live_identity.py
  - apps/whatsapp-assistant/src/runtime/dependencies.py

Then restarts uvicorn and checks the log for a clean startup (no import errors).
"""

import os
import time

import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

LOCAL_ROOT = r'E:\Mesiri.AI\apps\whatsapp-assistant\src'
REMOTE_SRC = '/opt/mesiri/apps/whatsapp-assistant/src'

# (local relative path, remote relative path)
FILES = [
    (r'context\live_identity.py', f'{REMOTE_SRC}/context/live_identity.py'),
    (r'runtime\dependencies.py', f'{REMOTE_SRC}/runtime/dependencies.py'),
]


def run(client, cmd, block=True):
    stdin, stdout, stderr = client.exec_command(cmd)
    out = stdout.read().decode('utf-8', errors='replace')
    err = stderr.read().decode('utf-8', errors='replace')
    if block:
        return out, err
    return "", ""


def upload(client, local_path, remote_path):
    """Upload a file by writing its bytes as hex (avoids SFTP/quoting pain)."""
    with open(local_path, 'rb') as f:
        data = f.read()
    hex_content = data.hex()
    write_script = (
        f"import binascii; "
        f"open('{remote_path}', 'wb').write(binascii.unhexlify('{hex_content}'))"
    )
    # Use a heredoc to avoid argument-length / quoting issues for bigger files
    heredoc = f"python3 <<'PYEOF'\n{write_script}\nPYEOF"
    out, err = run(client, heredoc)
    if err.strip():
        print(f"  upload stderr: {err.strip()[:300]}")
    return


def deploy():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    print(f"Connected to {HOST}")

    print("\n=== Uploading files ===")
    for rel_local, remote_path in FILES:
        local_path = os.path.join(LOCAL_ROOT, rel_local)
        print(f"  -> {remote_path}")
        upload(client, local_path, remote_path)
        # Confirm shape
        out, _ = run(client, f"head -1 {remote_path}")
        print(f"     first line: {out.strip()[:80]}")

    print("\n=== Restarting uvicorn ===")
    run(client, "pkill -9 -f 'uvicorn main:app'", block=False)
    run(client, "pkill -9 -f 'start_api.sh'", block=False)
    time.sleep(2)
    run(
        client,
        "nohup /opt/mesiri/start_api.sh > /tmp/mesiri_uvicorn.log 2>&1 &",
        block=False,
    )
    time.sleep(7)

    print("\n=== Process check ===")
    out, _ = run(client, "ps aux | grep 'uvicorn main:app' | grep -v grep")
    print(out.strip()[:400] if out.strip() else "  (no uvicorn process found!)")

    print("\n=== Routes ===")
    out, _ = run(
        client,
        "curl -s http://127.0.0.1:8000/openapi.json | python3 -c "
        "\"import sys,json; d=json.load(sys.stdin); print('routes:', len(d.get('paths',{}))); [print(' ', k) for k in d.get('paths',{}).keys()]\"",
    )
    print(out.strip() if out.strip() else "  (no response — server may have crashed)")

    print("\n=== Last 20 log lines ===")
    out, _ = run(client, "tail -20 /tmp/mesiri_uvicorn.log")
    print(out.strip()[-1500:])

    client.close()
    print("\nDeploy done.")


if __name__ == "__main__":
    deploy()
