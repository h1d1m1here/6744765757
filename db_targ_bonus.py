import aiosqlite
import os
from datetime import datetime, timedelta

DB_PATH = "targ_ogloszenia.db"

async def ensure_bonus_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_promo_bonus (
                user_id INTEGER PRIMARY KEY,
                count INTEGER DEFAULT 0
            )
        ''')
        await db.commit()

async def add_promo_bonus(user_id, amount=1):
    await ensure_bonus_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO user_promo_bonus (user_id, count) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET count = count + ?
        ''', (user_id, amount, amount))
        await db.commit()

async def get_promo_bonus(user_id):
    await ensure_bonus_table()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT count FROM user_promo_bonus WHERE user_id = ?', (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def use_promo_bonus(user_id):
    await ensure_bonus_table()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            UPDATE user_promo_bonus SET count = count - 1 WHERE user_id = ? AND count > 0
        ''', (user_id,))
        await db.commit()
