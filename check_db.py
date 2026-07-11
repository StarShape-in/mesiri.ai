import asyncio

from sqlalchemy import text

from mesiri.bootstrap.settings import Settings
from mesiri.infrastructure.postgres.database import PostgresDatabase


async def check_db():
    settings = Settings()
    db = PostgresDatabase(settings.postgres)
    await db.connect()
    
    try:
        async with db.transaction() as conn:
            result = await conn.execute(text("SELECT * FROM material_receipts ORDER BY occurred_date DESC LIMIT 5"))
            rows = result.mappings().all()
            print("--- MATERIAL RECEIPTS ---")
            for row in rows:
                print(dict(row))
                
            result = await conn.execute(text("SELECT * FROM idempotency_keys ORDER BY completed_at DESC LIMIT 5"))
            rows = result.mappings().all()
            print("\n--- IDEMPOTENCY KEYS ---")
            for row in rows:
                print(dict(row))
                
    finally:
        await db.disconnect()

if __name__ == "__main__":
    asyncio.run(check_db())
