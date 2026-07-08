"""Deploy M6.5 smoke prerequisites: langgraph + canonicalization fix."""

from __future__ import annotations

import os

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"
REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def upload(client: paramiko.SSHClient, local: str, remote: str) -> None:
    with open(local, encoding="utf-8") as f:
        content = f.read()
    hex_content = content.encode("utf-8").hex()
    remote_dir = remote.rsplit("/", 1)[0]
    client.exec_command(f"mkdir -p {remote_dir}")
    write_script = (
        f"import binascii; open('{remote}', 'wb').write(binascii.unhexlify('{hex_content}'))"
    )
    client.exec_command(f"python3 -c \"{write_script}\"")


def main() -> None:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print("Installing langgraph...")
    _, o, e = client.exec_command("/opt/mesiri/.venv/bin/pip install 'langgraph>=0.2' -q")
    print(o.read().decode())
    print(e.read().decode())

    upload(
        client,
        os.path.join(REPO, "apps", "whatsapp-assistant", "src", "canonicalization", "builder.py"),
        "/opt/mesiri/apps/whatsapp-assistant/src/canonicalization/builder.py",
    )
    print("Uploaded builder.py")

    client.exec_command("cd /opt/mesiri && /opt/mesiri/.venv/bin/python scripts/restart_whatsapp_assistant.py")
    client.close()


if __name__ == "__main__":
    main()
