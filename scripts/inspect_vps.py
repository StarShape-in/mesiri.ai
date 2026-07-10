import paramiko

HOST = "187.127.180.98"
USER = "root"
PASS = "Mercondatabase1234@"


def inspect_vps():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    # 1. Check if they use Docker for Nginx (Nginx Proxy Manager, traefik, etc.)
    print("--- Running Docker Containers ---")
    stdin, stdout, stderr = client.exec_command("docker ps --format '{{.Names}} - {{.Image}}'")
    print(stdout.read().decode("utf-8").strip())

    # 2. Check native Nginx config files for 'mercon.tech'
    print("\n--- Searching for mercon.tech in /etc/nginx/ ---")
    stdin, stdout, stderr = client.exec_command("grep -rl 'mercon.tech' /etc/nginx/")
    files = stdout.read().decode("utf-8").strip().split("\n")
    for f in files:
        if f:
            print(f"Found in: {f}")
            stdin, stdout, stderr = client.exec_command(f"cat {f}")
            print(stdout.read().decode("utf-8").strip()[:500] + "\n...")

    # 3. Check NPM (Nginx Proxy Manager) configs if present
    print("\n--- Searching for mercon.tech in /data/nginx/ (Nginx Proxy Manager) ---")
    stdin, stdout, stderr = client.exec_command("grep -rl 'mercon.tech' /data/nginx/ 2>/dev/null")
    npm_files = stdout.read().decode("utf-8").strip().split("\n")
    for f in npm_files:
        if f:
            print(f"Found in: {f}")

    client.close()


if __name__ == "__main__":
    inspect_vps()
