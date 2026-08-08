"""Set Alan's whatsapp_number to +91 7034926395 in the live DB.

Idempotent — safe to re-run. Matches Alan by email (alan@erp.com) which is unique.
"""
import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
NEW_NUMBER = "+91 7034926395"


def run(client, sql):
    cmd = "docker exec -i mesiri-postgres psql -U mesiri"
    stdin, stdout, stderr = client.exec_command(cmd)
    stdin.write(sql + "\n")
    stdin.channel.shutdown_write()
    out = stdout.read().decode("utf-8", errors="replace")
    err = stderr.read().decode("utf-8", errors="replace")
    return out, err


def main():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    print(f"Setting Alan's whatsapp_number to {NEW_NUMBER} ...")
    out, err = run(
        client,
        f"""
        UPDATE users
        SET whatsapp_number = '{NEW_NUMBER}', updated_at = now()
        WHERE email = 'alan@erp.com'
        RETURNING id, full_name, email, whatsapp_number, organization_id;
    """,
    )
    print(out)
    if err.strip():
        print("ERR:", err)

    print("\nVerify:")
    out, err = run(
        client,
        """
        SELECT u.full_name, u.role, u.whatsapp_number, o.name AS org_name, o.status
        FROM users u JOIN organizations o ON o.id = u.organization_id
        WHERE u.email = 'alan@erp.com';
    """,
    )
    print(out)
    if err.strip():
        print("ERR:", err)

    client.close()


if __name__ == "__main__":
    main()
