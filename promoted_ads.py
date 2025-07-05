
import asyncio
import aiosqlite
import os
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from datetime import datetime

# --- MIGRACJA: dodaj kolumnę promoted_until jeśli nie istnieje ---
async def ensure_promoted_until_column():
    async with aiosqlite.connect(DB_PATH) as db:
        # Sprawdź czy kolumna istnieje
        async with db.execute("PRAGMA table_info(ogloszenia)") as cursor:
            columns = [row[1] async for row in cursor]
        if "promoted_until" not in columns:
            await db.execute("ALTER TABLE ogloszenia ADD COLUMN promoted_until TEXT")
            await db.commit()


DB_PATH = "targ_ogloszenia.db"
CHANNEL_ID = os.getenv("CHANNEL_ID")
BOT_TOKEN = os.getenv("BOT_TOKEN")

async def get_random_promoted_ad():
    await ensure_promoted_until_column()
    async with aiosqlite.connect(DB_PATH) as db:
        now = datetime.now().isoformat()
        async with db.execute("SELECT * FROM ogloszenia WHERE promoted_until IS NOT NULL AND promoted_until > ? ORDER BY RANDOM() LIMIT 1", (now,)) as cursor:
            return await cursor.fetchone()

async def send_promoted_ad(bot: Bot):
    ad = await get_random_promoted_ad()
    if not ad:
        return
    # Rozpakuj ogłoszenie
    (id, user_id, username, typ, cena, opis, photo_id, miejscowosc, bezpieczne, data_dodania, wyswietlenia, promoted_until) = ad
    text = f"<b>{typ}</b> | {cena} zł\n{opis}\nMiejscowość: {miejscowosc}"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Dodaj swoje ogłoszenie", url="https://t.me/nocna24_bot?start=targ")],
        [InlineKeyboardButton(text="✉️Wiadomość", url=f"https://t.me/{username}")]
    ])
    if photo_id:
        await bot.send_photo(CHANNEL_ID, photo=photo_id, caption=text, reply_markup=kb, parse_mode="HTML")
    else:
        await bot.send_message(CHANNEL_ID, text, reply_markup=kb, parse_mode="HTML")

async def promoted_ads_loop(bot: Bot):
    while True:
        try:
            await send_promoted_ad(bot)
        except Exception as e:
            print(f"[PROMO ERROR] {e}")
        await asyncio.sleep(2 * 60 * 60)  # 2h

# Do użycia w main.py:
# from promoted_ads import promoted_ads_loop
# asyncio.create_task(promoted_ads_loop(bot))
