import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"
CONFIG_PATH = "/etc/nginx/sites-available/mercon"


def fix_all():
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # 1. DB Setup
    print("Fixing DB...")
    db_commands = [
        "CREATE DATABASE mesiri_control_plane_db;",
        "CREATE USER mesiriadmin WITH ENCRYPTED PASSWORD 'MesiriAdmin2026!';",
        "GRANT ALL PRIVILEGES ON DATABASE mesiri_control_plane_db TO mesiriadmin;",
        "ALTER DATABASE mesiri_control_plane_db OWNER TO mesiriadmin;",
    ]
    for cmd in db_commands:
        stdin, stdout, stderr = client.exec_command(
            f'docker exec mesiri-postgres psql -U mesiri -c "{cmd}"'
        )
        err = stderr.read().decode("utf-8").strip()
        if not err or "already exists" in err:
            pass  # ignore already exists

    # 2. Fix Nginx 404 Trailing Slash Issue
    print("Fixing Nginx...")
    fix_script = f"""
import sys
content = open('{CONFIG_PATH}').read()
if 'location /mesiriadmin/ {{' in content:
    content = content.replace('location /mesiriadmin/ {{', 'location ^~ /mesiriadmin {{')
    open('{CONFIG_PATH}', 'w').write(content)
"""
    client.exec_command(f'python3 -c "{fix_script}"')

    # Reload
    client.exec_command("systemctl reload nginx")
    print(
        "Done! Tell the user to visit https://mercon.tech/mesiriadmin (it should now redirect/work)."
    )

    client.close()


if __name__ == "__main__":
    fix_all()
