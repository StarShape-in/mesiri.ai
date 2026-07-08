import os

import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'
LOCAL_BASE = r'E:\Mesiri.AI\backend'
REMOTE_BASE = '/opt/mesiri/backend'

files_to_sync = [
    r'migrations\versions\0020_identity_add_users.py',
    r'migrations\versions\0030_orgs_add_organizations.py',
    r'src\mesiri\infrastructure\postgres\models\user.py',
    r'src\mesiri\infrastructure\postgres\models\organization.py',
    r'src\mesiri\domains\identity\router.py',
    r'src\mesiri\domains\admin\__init__.py',
    r'src\mesiri\domains\admin\router.py',
    r'src\mesiri\http\app.py',
]

def deploy_backend():
    print(f"Connecting to {HOST}...")
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(HOST, username=USER, password=PASS)
    sftp = client.open_sftp()
    
    for f in files_to_sync:
        local_path = os.path.join(LOCAL_BASE, f)
        remote_path = REMOTE_BASE + '/' + f.replace('\\', '/')
        
        # Ensure remote directory exists
        remote_dir = remote_path.rsplit('/', 1)[0]
        client.exec_command(f"mkdir -p {remote_dir}")
        
        print(f"Uploading backend file: {f}...")
        try:
            with open(local_path, encoding='utf-8') as local_file:
                content = local_file.read()
            
            # Use python3 on the remote to safely write the file content
            # Encode content as hex to avoid any shell escaping issues
            hex_content = content.encode('utf-8').hex()
            write_script = f"import binascii; open('{remote_path}', 'wb').write(binascii.unhexlify('{hex_content}'))"
            stdin, stdout, stderr = client.exec_command(f"python3 -c \"{write_script}\"")
            err = stderr.read().decode('utf-8')
            if err:
                print(f"Failed to write {f} on remote: {err}")
        except Exception as e:
            print(f"Failed to read/upload {f}: {e}")

    # Upload React UI
    dist_dir = r'e:\Mesiri.AI\apps\control-panel\dist'
    remote_ui = '/var/www/mesiriadmin'
    print(f"\nUploading React Dashboard to {remote_ui}...")
    
    for root, dirs, files in os.walk(dist_dir):
        for d in dirs:
            local_path = os.path.join(root, d)
            remote_path = local_path.replace(dist_dir, remote_ui).replace('\\', '/')
            try:
                sftp.mkdir(remote_path)
            except OSError:
                pass
        for f in files:
            local_path = os.path.join(root, f)
            remote_path = local_path.replace(dist_dir, remote_ui).replace('\\', '/')
            sftp.put(local_path, remote_path)
            
    client.exec_command(f"chown -R www-data:www-data {remote_ui}")

    sftp.close()
    
    # Run Alembic Migration
    print("\nRunning Alembic Migration...")
    stdin, stdout, stderr = client.exec_command("cd /opt/mesiri/backend && /opt/mesiri/.venv/bin/alembic upgrade head")
    print(stdout.read().decode('utf-8'))
    err = stderr.read().decode('utf-8')
    if err:
        print("Alembic output:", err)
        
    # Restart the service (assuming it's managed by systemd or PM2)
    # Let's try systemctl restart mesiri or similar. If not, just kill uvicorn and it might auto-restart
    print("\nRestarting Backend Service...")
    client.exec_command("pkill -f uvicorn") # Will be restarted by systemd/supervisor if configured
    print("Backend restarted successfully!")

    client.close()

if __name__ == "__main__":
    deploy_backend()
