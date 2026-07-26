import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
DIST_DIR = r"e:\Mesiri.AI\apps\control-panel\dist"
REMOTE_DIR = "/var/www/mesiriadmin"


def deploy():
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(HOST, username=USER, password=PASS)
        print("Connected successfully!")

        # 1. Setup Database
        print("\n--- Provisioning PostgreSQL Database ---")
        db_commands = [
            "CREATE DATABASE mesiri_control_plane_db;",
            "CREATE USER mesiriadmin WITH ENCRYPTED PASSWORD 'MesiriAdmin2026!';",
            "GRANT ALL PRIVILEGES ON DATABASE mesiri_control_plane_db TO mesiriadmin;",
            "ALTER DATABASE mesiri_control_plane_db OWNER TO mesiriadmin;",
        ]

        for cmd in db_commands:
            stdin, stdout, stderr = client.exec_command(f'sudo -u postgres psql -c "{cmd}"')
            out = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            if err and "already exists" not in err.lower() and "already exists" not in out.lower():
                print(f"DB Warning for '{cmd}': {err}")
            else:
                print(f"Executed: {cmd.split()[0]} successfully.")

        # 2. Setup Nginx Directory
        print("\n--- Preparing Nginx Directory ---")
        client.exec_command(f"rm -rf {REMOTE_DIR}")
        client.exec_command(f"mkdir -p {REMOTE_DIR}")

        # 3. SFTP Upload
        print(f"\n--- Uploading React Dashboard to {REMOTE_DIR} ---")
        sftp = client.open_sftp()

        for root, dirs, files in os.walk(DIST_DIR):
            for d in dirs:
                local_path = os.path.join(root, d)
                remote_path = local_path.replace(DIST_DIR, REMOTE_DIR).replace("\\", "/")
                try:
                    sftp.mkdir(remote_path)
                except OSError:
                    pass
            for f in files:
                local_path = os.path.join(root, f)
                remote_path = local_path.replace(DIST_DIR, REMOTE_DIR).replace("\\", "/")
                print(f"Uploading {f}...")
                sftp.put(local_path, remote_path)

        sftp.close()
        client.exec_command(f"chown -R www-data:www-data {REMOTE_DIR}")
        print("Upload complete!")

        # 4. Nginx Configuration
        print("\n--- Configuring Nginx ---")
        nginx_block = """
location /mesiriadmin/ {
    alias /var/www/mesiriadmin/;
    try_files $uri $uri/ /mesiriadmin/index.html;
}
"""
        # Try to find the config file
        stdin, stdout, stderr = client.exec_command("ls /etc/nginx/sites-available/")
        sites = stdout.read().decode("utf-8").split()

        target_site = "mercon.tech" if "mercon.tech" in sites else "default"
        config_path = f"/etc/nginx/sites-available/{target_site}"
        print(f"Targeting Nginx config: {config_path}")

        # Check if block already exists
        stdin, stdout, stderr = client.exec_command(
            f"grep -q 'location /mesiriadmin/' {config_path} && echo 'EXISTS' || echo 'MISSING'"
        )
        status = stdout.read().decode("utf-8").strip()

        if status == "MISSING":
            print("Adding location block to Nginx config...")
            # We insert the block right before the last closing brace of the server block
            # This is a bit risky with sed, so let's use python on the remote
            insert_script = f"""
import sys
content = open('{config_path}').read()
if 'server {{' in content:
    # Find the last closing brace
    last_brace_idx = content.rfind('}}')
    if last_brace_idx != -1:
        new_content = content[:last_brace_idx] + '''{nginx_block}''' + content[last_brace_idx:]
        open('{config_path}', 'w').write(new_content)
"""
            client.exec_command(f'python3 -c "{insert_script}"')
            print("Block injected.")

            # Reload Nginx
            print("Testing Nginx config...")
            stdin, stdout, stderr = client.exec_command("nginx -t")
            if "successful" in stderr.read().decode("utf-8"):
                client.exec_command("systemctl reload nginx")
                print("Nginx reloaded successfully!")
            else:
                print("WARNING: Nginx config test failed! Did not reload.")
        else:
            print("Nginx location block already exists. No config changes made.")

        print("\n✅ Deployment Complete! Visit https://mercon.tech/mesiriadmin")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        client.close()


if __name__ == "__main__":
    deploy()
