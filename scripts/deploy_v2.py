import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
CONFIG_PATH = "/etc/nginx/sites-available/mercon"


def deploy_v2():
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(HOST, username=USER, password=PASS)
        print("Connected successfully!")

        # 1. Setup Database inside Docker
        print("\n--- Provisioning PostgreSQL Database inside Docker ---")
        db_commands = [
            "CREATE DATABASE mesiri_control_plane_db;",
            "CREATE USER mesiriadmin WITH ENCRYPTED PASSWORD 'MesiriAdmin2026!';",
            "GRANT ALL PRIVILEGES ON DATABASE mesiri_control_plane_db TO mesiriadmin;",
            "ALTER DATABASE mesiri_control_plane_db OWNER TO mesiriadmin;",
        ]

        for cmd in db_commands:
            # We use docker exec to run psql inside the mesiri-postgres container
            stdin, stdout, stderr = client.exec_command(
                f'docker exec mesiri-postgres psql -U postgres -c "{cmd}"'
            )
            out = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            if err and "already exists" not in err.lower() and "already exists" not in out.lower():
                print(f"DB Warning for '{cmd}': {err}")
            else:
                print(f"Executed: {cmd.split()[0]} successfully.")

        # 2. Nginx Configuration
        print(f"\n--- Configuring Nginx in {CONFIG_PATH} ---")
        nginx_block = """
    location /mesiriadmin/ {
        alias /var/www/mesiriadmin/;
        try_files $uri $uri/ /mesiriadmin/index.html;
    }
"""
        # Check if block already exists
        stdin, stdout, stderr = client.exec_command(
            f"grep -q 'location /mesiriadmin/' {CONFIG_PATH} && echo 'EXISTS' || echo 'MISSING'"
        )
        status = stdout.read().decode("utf-8").strip()

        if status == "MISSING":
            print("Adding location block to Nginx config...")
            insert_script = f"""
import sys
content = open('{CONFIG_PATH}').read()
if 'location / {{' in content:
    # Insert right after the location / block
    parts = content.split('location / {{')
    new_content = parts[0] + 'location / {{' + parts[1].split('}}', 1)[0] + '}}\\n' + '''{nginx_block}''' + parts[1].split('}}', 1)[1]
    open('{CONFIG_PATH}', 'w').write(new_content)
else:
    print("Could not find location / block")
"""
            client.exec_command(f'python3 -c "{insert_script}"')
            print("Block injected.")

            # Reload Nginx
            print("Testing Nginx config...")
            stdin, stdout, stderr = client.exec_command("nginx -t")
            err_out = stderr.read().decode("utf-8")
            if "successful" in err_out:
                client.exec_command("systemctl reload nginx")
                print("Nginx reloaded successfully!")
            else:
                print(f"WARNING: Nginx config test failed! {err_out}")
        else:
            print("Nginx location block already exists. No config changes made.")

        print("\nDeployment Complete! Visit https://mercon.tech/mesiriadmin")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    deploy_v2()
