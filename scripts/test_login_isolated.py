import paramiko

HOST = '187.127.180.98'
USER = 'root'
PASS = 'Mercondatabase1234@'

client = paramiko.SSHClient()
client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
client.connect(HOST, username=USER, password=PASS)

# Test the login logic in isolation
test_script = """
import asyncio, sys
sys.path.insert(0, '/opt/mesiri/apps/whatsapp-assistant/src')
sys.path.insert(0, '/opt/mesiri/shared/contracts/src')
sys.path.insert(0, '/opt/mesiri/backend/src')
sys.path.insert(0, '/opt/mesiri/platform/ai/src')

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=['bcrypt'], deprecated='auto')

users_table = sa.Table(
    'users',
    sa.MetaData(),
    sa.Column('id', sa.UUID, primary_key=True),
    sa.Column('organization_id', sa.UUID),
    sa.Column('email', sa.String),
    sa.Column('hashed_password', sa.String),
    sa.Column('full_name', sa.String),
    sa.Column('role', sa.String),
    sa.Column('whatsapp_number', sa.String),
)

async def test():
    engine = create_async_engine('postgresql+asyncpg://mesiri:mesiri_local_dev@localhost:5432/mesiri')
    async with engine.connect() as conn:
        result = await conn.execute(
            sa.select(users_table).where(users_table.c.email == 'admin@acmeconstruct.com')
        )
        row = result.first()
        if not row:
            print('USER NOT FOUND')
            return
        print(f'Found user: {row.email}, role: {row.role}')
        print(f'Hash starts: {row.hashed_password[:20]}')
        ok = pwd_context.verify('Acme1234!', row.hashed_password)
        print(f'Password verify: {ok}')

asyncio.run(test())
"""

stdin, stdout, stderr = client.exec_command(
    f"/opt/mesiri/.venv/bin/python3 -c \"{test_script}\""
)
out = stdout.read().decode('utf-8', errors='replace')
err = stderr.read().decode('utf-8', errors='replace')
print("OUT:", out)
if err:
    print("ERR:", err[:1000])

client.close()
