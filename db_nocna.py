import aiosqlite
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')

async def get_last_chest_open(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS night_chest (
                user_id INTEGER PRIMARY KEY,
                last_open TEXT
            )
        ''')
        cursor = await db.execute('SELECT last_open FROM night_chest WHERE user_id=?', (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else None

async def set_chest_open(user_id, date_str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO night_chest (user_id, last_open) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET last_open=excluded.last_open
        ''', (user_id, date_str))
        await db.commit()
