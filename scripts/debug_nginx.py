import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

def debug_nginx():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    # Find which file actually serves mercon.tech
    stdin, stdout, stderr = client.exec_command("grep -rl 'mercon.tech' /etc/nginx/")
    files = stdout.read().decode('utf-8').strip().split('\n')
    print("Files containing mercon.tech:")
    for f in files:
        print(f" - {f}")
        
    # Let's read the content of the most likely file
    if files and files[0]:
        stdin, stdout, stderr = client.exec_command(f"cat {files[0]}")
        content = stdout.read().decode('utf-8')
        print(f"\n--- Content of {files[0]} ---")
        # Print first 20 lines and last 20 lines to avoid spam
        lines = content.split('\n')
        for line in lines:
            print(line)

    client.close()

if __name__ == "__main__":
    debug_nginx()
