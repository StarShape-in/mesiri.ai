import os

import paramiko

HOST = os.environ["MESIRI_VPS_HOST"]
USER = os.environ["MESIRI_VPS_USER"]
PASS = os.environ["MESIRI_VPS_PASSWORD"]
def debug_nginx():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)

    stdin, stdout, stderr = client.exec_command("cat /etc/nginx/sites-available/mercon")
    print(stdout.read().decode("utf-8"))

    stdin, stdout, stderr = client.exec_command("ls -la /var/www/mesiriadmin")
    print("\nDir listing:")
    print(stdout.read().decode("utf-8"))

    client.close()


if __name__ == "__main__":
    debug_nginx()
