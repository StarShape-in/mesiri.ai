import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def debug_nginx():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    stdin, stdout, stderr = client.exec_command("cat /etc/nginx/sites-available/mercon")
    print(stdout.read().decode('utf-8'))
    
    stdin, stdout, stderr = client.exec_command("ls -la /var/www/mesiriadmin")
    print("\nDir listing:")
    print(stdout.read().decode('utf-8'))

    client.close()

if __name__ == "__main__":
    debug_nginx()
