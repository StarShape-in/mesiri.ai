import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def deploy_db():
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        client.connect(HOST, username=USER, password=PASS)

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
            out = stdout.read().decode("utf-8").strip()
            err = stderr.read().decode("utf-8").strip()
            if err and "already exists" not in err.lower() and "already exists" not in out.lower():
                print(f"DB Warning for '{cmd}': {err}")
            else:
                print(f"Executed: {cmd.split()[0]} successfully.")

    finally:
        client.close()


if __name__ == "__main__":
    deploy_db()
