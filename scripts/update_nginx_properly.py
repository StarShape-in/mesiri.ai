import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'
CONFIG = '/etc/nginx/sites-available/mercon'

def fix_nginx():
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    
    sftp = client.open_sftp()
    
    # Download
    sftp.get(CONFIG, 'mercon.conf')
    
    with open('mercon.conf') as f:
        content = f.read()
        
    if 'location ^~ /mesiriadmin' not in content:
        # Find where to insert it (after server_name mercon.tech www.mercon.tech;)
        insert_marker = 'server_name mercon.tech www.mercon.tech;'
        
        block = """
    location ^~ /mesiriadmin {
        alias /var/www/mesiriadmin/;
        try_files $uri $uri/ /mesiriadmin/index.html;
    }
"""
        if insert_marker in content:
            # We want to insert it after the very first occurrence (in the 443 block)
            parts = content.split(insert_marker, 1)
            new_content = parts[0] + insert_marker + '\n' + block + parts[1]
            
            with open('mercon.conf', 'w') as f:
                f.write(new_content)
                
            # Upload
            sftp.put('mercon.conf', CONFIG)
            print("Uploaded new config.")
            
            # Test & Reload
            stdin, stdout, stderr = client.exec_command("nginx -t")
            if "successful" in stderr.read().decode('utf-8'):
                client.exec_command("systemctl reload nginx")
                print("Nginx Reloaded!")
            else:
                print("Nginx Test Failed!")
        else:
            print("Could not find insert marker.")
    else:
        print("Block already exists.")
        
    sftp.close()
    client.close()

if __name__ == "__main__":
    fix_nginx()
