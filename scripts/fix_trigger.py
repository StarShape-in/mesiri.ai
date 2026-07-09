"""Fix the set_updated_at trigger function + verify all triggers on prod."""

from __future__ import annotations

import sys

import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS, timeout=15)
    print("Connected.")

    # Create the function using a heredoc to avoid quoting issues
    cmd = r"""docker exec mesiri-postgres psql -U mesiri -d mesiri -c 'CREATE OR REPLACE FUNCTION set_updated_at() RETURNS trigger AS $$ BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;'"""
    _, stdout, stderr = client.exec_command(cmd, timeout=15)
    out = stdout.read().decode().strip()
    err = stderr.read().decode().strip()
    print(f"Function: {out}")
    if err and "NOTICE" not in err:
        print(f"ERR: {err}")

    # Create triggers for each context table
    for table in ["context_organizations", "context_users", "context_projects", "context_sites"]:
        cmd = f"docker exec mesiri-postgres psql -U mesiri -d mesiri -c 'DROP TRIGGER IF EXISTS trg_{table}_updated ON {table}; CREATE TRIGGER trg_{table}_updated BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION set_updated_at();'"
        _, stdout, stderr = client.exec_command(cmd, timeout=15)
        out = stdout.read().decode().strip()
        err = stderr.read().decode().strip()
        print(f"{table}: {out}")
        if err and "NOTICE" not in err:
            print(f"  ERR: {err}")

    # Verify triggers exist
    cmd = "docker exec mesiri-postgres psql -U mesiri -d mesiri -c \"SELECT tgname, tgrelid::regclass FROM pg_trigger WHERE tgname LIKE 'trg_context%' ORDER BY tgname;\""
    _, stdout, _ = client.exec_command(cmd, timeout=15)
    print(f"\nTriggers:\n{stdout.read().decode().strip()}")

    # Test: update a context_organizations row and check updated_at changes
    cmd = "docker exec mesiri-postgres psql -U mesiri -d mesiri -c \"SELECT id, created_at, updated_at FROM context_organizations LIMIT 2;\""
    _, stdout, _ = client.exec_command(cmd, timeout=15)
    print(f"\nBefore update:\n{stdout.read().decode().strip()}")

    cmd = "docker exec mesiri-postgres psql -U mesiri -d mesiri -c \"UPDATE context_organizations SET name = name WHERE id = (SELECT id FROM context_organizations LIMIT 1);\""
    client.exec_command(cmd, timeout=15)
    import time
    time.sleep(0.5)

    cmd = "docker exec mesiri-postgres psql -U mesiri -d mesiri -c \"SELECT id, created_at, updated_at FROM context_organizations LIMIT 2;\""
    _, stdout, _ = client.exec_command(cmd, timeout=15)
    print(f"\nAfter update (updated_at should differ from created_at):\n{stdout.read().decode().strip()}")

    client.close()
    print("\n[OK] Done.")


if __name__ == "__main__":
    main()
