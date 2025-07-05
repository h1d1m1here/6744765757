import aiosqlite
from db_targ import DB_PATH

async def ensure_wyswietlenia_column():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("PRAGMA table_info(ogloszenia)") as cursor:
            columns = [row[1] async for row in cursor]
        if "wyswietlenia" not in columns:
            await db.execute("ALTER TABLE ogloszenia ADD COLUMN wyswietlenia INTEGER DEFAULT 0")
            await db.commit()

# Automatyczna migracja przy imporcie modułu
import asyncio
asyncio.get_event_loop().run_until_complete(ensure_wyswietlenia_column())

async def increment_wyswietlenia(ogloszenie_id, value=1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            'UPDATE ogloszenia SET wyswietlenia = COALESCE(wyswietlenia, 0) + ? WHERE id = ?',
            (value, ogloszenie_id)
        )
        await db.commit()
