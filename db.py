async def increment_shop_clicks(shop_id, value=1):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE shops SET clicks = COALESCE(clicks, 0) + ? WHERE id = ?', (value, shop_id))
        await db.commit()
async def migrate_user_items_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS user_items (
                user_id INTEGER,
                item_name TEXT,
                found_at TEXT,
                PRIMARY KEY(user_id, item_name)
            )
        ''')
        await db.commit()

async def add_user_item(user_id: int, item_name: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR IGNORE INTO user_items (user_id, item_name, found_at) VALUES (?, ?, ?)
        ''', (user_id, item_name, datetime.now().isoformat()))
        await db.commit()

async def get_user_items(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS user_items (
            user_id INTEGER,
            item_name TEXT,
            found_at TEXT,
            PRIMARY KEY(user_id, item_name)
        )''')
        cursor = await db.execute('SELECT item_name FROM user_items WHERE user_id=?', (user_id,))
        return [row[0] for row in await cursor.fetchall()]

async def migrate_all():
    await full_migrate_db()
    await migrate_product_aliases_table()
    await migrate_notification_subs_table()
    await migrate_user_items_table()
async def unmute_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM mutes WHERE user_id=?', (user_id,))
        await db.commit()

async def del_warn(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS warns (
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        # Usuwa najstarszy warn
        await db.execute('DELETE FROM warns WHERE rowid IN (SELECT rowid FROM warns WHERE user_id=? ORDER BY created_at ASC LIMIT 1)', (user_id,))
        await db.commit()
import aiosqlite
import os
from datetime import datetime, timedelta
from aiogram import types
import random

DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')

# --- SYSTEM BANÓW/WARN/MUTE ---
async def ban_user(user_id: int, admin_id: int = None, reason: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        await db.execute('''INSERT OR REPLACE INTO bans (user_id, admin_id, reason, created_at) VALUES (?, ?, ?, ?)''',
            (user_id, admin_id, reason or '', datetime.now().isoformat()))
        await db.commit()

async def is_banned(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS bans (
            user_id INTEGER PRIMARY KEY,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        cursor = await db.execute('SELECT 1 FROM bans WHERE user_id=?', (user_id,))
        return await cursor.fetchone() is not None

async def unban_user(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM bans WHERE user_id=?', (user_id,))
        await db.commit()

async def warn_user(user_id: int, admin_id: int = None, reason: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS warns (
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        await db.execute('''INSERT INTO warns (user_id, admin_id, reason, created_at) VALUES (?, ?, ?, ?)''',
            (user_id, admin_id, reason or '', datetime.now().isoformat()))
        await db.commit()

async def get_warns(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS warns (
            user_id INTEGER,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        cursor = await db.execute('SELECT * FROM warns WHERE user_id=?', (user_id,))
        return await cursor.fetchall()

async def mute_user(user_id: int, until: datetime, admin_id: int = None, reason: str = None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS mutes (
            user_id INTEGER PRIMARY KEY,
            until TEXT,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        await db.execute('''INSERT OR REPLACE INTO mutes (user_id, until, admin_id, reason, created_at) VALUES (?, ?, ?, ?, ?)''',
            (user_id, until.isoformat(), admin_id, reason or '', datetime.now().isoformat()))
        await db.commit()

async def is_muted(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS mutes (
            user_id INTEGER PRIMARY KEY,
            until TEXT,
            admin_id INTEGER,
            reason TEXT,
            created_at TEXT
        )''')
        cursor = await db.execute('SELECT until FROM mutes WHERE user_id=?', (user_id,))
        row = await cursor.fetchone()
        if row:
            until = datetime.fromisoformat(row[0])
            if until > datetime.now():
                return until
            else:
                # automatyczne odciszenie po czasie
                await db.execute('DELETE FROM mutes WHERE user_id=?', (user_id,))
                await db.commit()
        return False
import aiosqlite
import os
from datetime import datetime
from aiogram import types
import random

DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')

# Sprawdza, czy użytkownik dodał opinię do danego sklepu w ciągu ostatnich 24h
from datetime import timedelta
async def user_opinion_last_24h(shop_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            'SELECT created_at FROM opinions WHERE shop_id = ? AND user_id = ? ORDER BY created_at DESC LIMIT 1',
            (shop_id, user_id)
        )
        row = await cursor.fetchone()
        if row:
            try:
                last_time = datetime.fromisoformat(row[0])
            except Exception:
                # fallback na format bez mikrosekund
                last_time = datetime.strptime(row[0], "%Y-%m-%dT%H:%M:%S")
            if datetime.now() - last_time < timedelta(hours=24):
                return True
        return False

async def migrate_olx_ads_table():
    async with aiosqlite.connect(DB_PATH) as db:
        # Sprawdź czy kolumna location istnieje
        cursor = await db.execute("PRAGMA table_info(olx_ads)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "location" not in columns:
            await db.execute("ALTER TABLE olx_ads ADD COLUMN location TEXT")
        if "delivery_method" not in columns:
            await db.execute("ALTER TABLE olx_ads ADD COLUMN delivery_method TEXT")
        if "secure_payment" not in columns:
            await db.execute("ALTER TABLE olx_ads ADD COLUMN secure_payment INTEGER DEFAULT 0")
        await db.commit()

async def migrate_shop_products_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shop_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                city TEXT,
                product TEXT,
                FOREIGN KEY(shop_id) REFERENCES shops(id)
            )
        ''')
        await db.commit()

async def migrate_promoted_column():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute("PRAGMA table_info(shops)")
        columns = [row[1] for row in await cursor.fetchall()]
        if "promoted" not in columns:
            await db.execute("ALTER TABLE shops ADD COLUMN promoted INTEGER DEFAULT 0")
            await db.commit()

async def migrate_users_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                created_at TEXT
            )
        ''')
        await db.commit()

async def migrate_product_aliases_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS product_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                alias TEXT NOT NULL
            )
        ''')
        await db.commit()

async def full_migrate_db():
    async with aiosqlite.connect(DB_PATH) as db:
        # shops
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shops (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_name TEXT,
                description TEXT,
                bot_link TEXT,
                operator_link TEXT,
                chat_link TEXT,
                www TEXT,
                photo TEXT,
                created_at TEXT,
                clicks INTEGER DEFAULT 0,
                flag TEXT DEFAULT '🇵🇱',
                promoted INTEGER DEFAULT 0
            )
        ''')
        # shop_products
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shop_products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                city TEXT,
                product TEXT,
                FOREIGN KEY(shop_id) REFERENCES shops(id)
            )
        ''')
        # ratings
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ratings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                user_id INTEGER,
                rating INTEGER,
                created_at TEXT,
                FOREIGN KEY(shop_id) REFERENCES shops(id)
            )
        ''')
        # opinions
        await db.execute('''
            CREATE TABLE IF NOT EXISTS opinions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                user_id INTEGER,
                opinion TEXT,
                photo_id TEXT,
                user_name TEXT,
                user_username TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(shop_id) REFERENCES shops(id)
            )
        ''')
        # olx_ads
        await db.execute('''
            CREATE TABLE IF NOT EXISTS olx_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                title TEXT,
                description TEXT,
                price TEXT,
                photo_id TEXT,
                sold INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                location TEXT,
                delivery_method TEXT,
                secure_payment INTEGER DEFAULT 0
            )
        ''')
        # users
        await db.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER UNIQUE,
                first_name TEXT,
                last_name TEXT,
                username TEXT,
                created_at TEXT
            )
        ''')
        # shop_countries
        await db.execute('''
            CREATE TABLE IF NOT EXISTS shop_countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                shop_id INTEGER,
                country_code TEXT,
                FOREIGN KEY(shop_id) REFERENCES shops(id)
            )
        ''')
        # countries
        await db.execute('''
            CREATE TABLE IF NOT EXISTS countries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code TEXT,
                name TEXT
            )
        ''')
        # product_aliases
        await db.execute('''
            CREATE TABLE IF NOT EXISTS product_aliases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product TEXT NOT NULL,
                alias TEXT NOT NULL
            )
        ''')
        await db.commit()

async def init_db():
    await full_migrate_db()
    await migrate_product_aliases_table()
    await migrate_notification_subs_table()
    await migrate_user_items_table()

async def add_shop(shop):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO shops (shop_name, description, bot_link, operator_link, chat_link, www, photo, created_at, clicks, flag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            shop.get('shop_name'),
            shop.get('description'),
            shop.get('bot_link'),
            shop.get('operator_link'),
            shop.get('chat_link'),
            shop.get('www', ''),
            shop.get('photo', ''),
            shop.get('created_at', datetime.now().isoformat()),
            int(shop.get('clicks', 0)),
            shop.get('flag', '🇵🇱')
        ))
        await db.commit()

async def get_shops():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM shops')
        rows = await cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

async def get_shop(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM shops WHERE id = ?', (shop_id,))
        row = await cursor.fetchone()
        if row:
            return dict(zip([column[0] for column in cursor.description], row))
        return None

async def add_rating(shop_id, user_id, rating):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO ratings (shop_id, user_id, rating, created_at)
            VALUES (?, ?, ?, ?)
        ''', (shop_id, user_id, rating, datetime.now().isoformat()))
        await db.commit()

async def get_ratings(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT rating FROM ratings WHERE shop_id = ?', (shop_id,))
        return [row[0] for row in await cursor.fetchall()]

async def add_opinion(shop_id, user_id, opinion, photo_id=None, user_name=None, user_username=None):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO opinions (shop_id, user_id, opinion, photo_id, user_name, user_username, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (shop_id, user_id, opinion, photo_id, user_name, user_username, datetime.now().isoformat()))
        await db.commit()
        # --- AKTUALIZUJ ŚREDNIĄ OCENĘ SKLEPU ---
        cursor = await db.execute('SELECT AVG(rating) FROM ratings WHERE shop_id = ?', (shop_id,))
        avg_row = await cursor.fetchone()
        avg_rating = avg_row[0] if avg_row and avg_row[0] is not None else None
        if avg_rating is not None:
            # Dodaj pole "average_rating" do tabeli shops jeśli nie istnieje
            await db.execute('''
                CREATE TABLE IF NOT EXISTS shops (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    shop_name TEXT,
                    description TEXT,
                    bot_link TEXT,
                    operator_link TEXT,
                    chat_link TEXT,
                    www TEXT,
                    photo TEXT,
                    created_at TEXT,
                    clicks INTEGER DEFAULT 0,
                    flag TEXT DEFAULT '🇵🇱',
                    promoted INTEGER DEFAULT 0,
                    average_rating REAL DEFAULT NULL
                )
            ''')
            # Sprawdź czy kolumna istnieje
            cursor2 = await db.execute("PRAGMA table_info(shops)")
            columns = [row[1] async for row in cursor2]
            if "average_rating" not in columns:
                await db.execute('ALTER TABLE shops ADD COLUMN average_rating REAL DEFAULT NULL')
            await db.execute('UPDATE shops SET average_rating = ? WHERE id = ?', (avg_rating, shop_id))
            await db.commit()

async def get_opinions(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT opinion FROM opinions WHERE shop_id = ?', (shop_id,))
        return [row[0] for row in await cursor.fetchall()]

async def get_opinions_full(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT id, user_id, opinion, photo_id FROM opinions WHERE shop_id = ?', (shop_id,))
        return [dict(zip([column[0] for column in cursor.description], row)) for row in await cursor.fetchall()]

async def update_opinion(opinion_id, new_text):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE opinions SET opinion = ? WHERE id = ?', (new_text, opinion_id))
        await db.commit()

async def delete_opinion(opinion_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM opinions WHERE id = ?', (opinion_id,))
        await db.commit()

async def update_shop_photo(shop_id, photo_path):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE shops SET photo = ? WHERE id = ?', (photo_path, shop_id))
        await db.commit()

async def init_olx_table():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS olx_ads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                title TEXT,
                description TEXT,
                price TEXT,
                photo_id TEXT,
                sold INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        await db.commit()

async def add_olx_ad(user_id, username, title, description, price, location, delivery_method, photo_id=None, secure_payment=0):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO olx_ads (user_id, username, title, description, price, location, delivery_method, photo_id, secure_payment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, title, description, price, location, delivery_method, photo_id, secure_payment))
        await db.commit()

async def get_olx_ads(offset=0, limit=5):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT * FROM olx_ads WHERE sold=0 ORDER BY created_at DESC LIMIT ? OFFSET ?
        ''', (limit, offset))
        rows = await cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

async def count_olx_ads():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT COUNT(*) FROM olx_ads WHERE sold=0')
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_user_olx_ads(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('''
            SELECT * FROM olx_ads WHERE user_id=? ORDER BY created_at DESC
        ''', (user_id,))
        rows = await cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

async def delete_olx_ad(ad_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM olx_ads WHERE id=? AND user_id=?', (ad_id, user_id))
        await db.commit()

async def update_olx_ad(ad_id, user_id, title=None, description=None, price=None, location=None, delivery_method=None, photo_id=None, secure_payment=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if title:
            await db.execute('UPDATE olx_ads SET title=? WHERE id=? AND user_id=?', (title, ad_id, user_id))
        if description:
            await db.execute('UPDATE olx_ads SET description=? WHERE id=? AND user_id=?', (description, ad_id, user_id))
        if price:
            await db.execute('UPDATE olx_ads SET price=? WHERE id=? AND user_id=?', (price, ad_id, user_id))
        if location:
            await db.execute('UPDATE olx_ads SET location=? WHERE id=? AND user_id=?', (location, ad_id, user_id))
        if delivery_method:
            await db.execute('UPDATE olx_ads SET delivery_method=? WHERE id=? AND user_id=?', (delivery_method, ad_id, user_id))
        if photo_id:
            await db.execute('UPDATE olx_ads SET photo_id=? WHERE id=? AND user_id=?', (photo_id, ad_id, user_id))
        if secure_payment is not None:
            await db.execute('UPDATE olx_ads SET secure_payment=? WHERE id=? AND user_id=?', (secure_payment, ad_id, user_id))
        await db.commit()

async def set_olx_ad_sold(ad_id, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE olx_ads SET sold=1 WHERE id=? AND user_id=?', (ad_id, user_id))
        await db.commit()

async def migrate_add_flag():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            ALTER TABLE shops ADD COLUMN flag TEXT DEFAULT '🇵🇱'
        ''')
        await db.commit()

async def set_shop_flag(shop_id, flag):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE shops SET flag = ? WHERE id = ?", (flag, shop_id))
        await db.commit()

async def get_shop_flag(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT flag FROM shops WHERE id = ?", (shop_id,)) as cursor:
            row = await cursor.fetchone()
            return row[0] if row else '🇵🇱'

async def clear_shop_ratings_and_opinions(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM ratings WHERE shop_id = ?", (shop_id,))
        await db.execute("DELETE FROM opinions WHERE shop_id = ?", (shop_id,))
        await db.commit()

async def update_shop_field(shop_id, field, value):
    allowed = ["bot_link", "operator_link", "chat_link", "www", "description", "shop_name", "flag"]
    if field not in allowed:
        raise ValueError("Niedozwolone pole do edycji!")
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f'UPDATE shops SET {field} = ? WHERE id = ?', (value, shop_id))
        await db.commit()

async def get_shop_countries(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT country_code FROM shop_countries WHERE shop_id = ?', (shop_id,))
        return [row[0] for row in await cursor.fetchall()]

async def set_shop_countries(shop_id, country_codes):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM shop_countries WHERE shop_id = ?', (shop_id,))
        for code in country_codes:
            await db.execute('INSERT INTO shop_countries (shop_id, country_code) VALUES (?, ?)', (shop_id, code))
        await db.commit()

async def get_all_countries():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT code, name FROM countries')
        return [dict(zip([column[0] for column in cursor.description], row)) for row in await cursor.fetchall()]

async def set_shop_promoted(shop_id, promoted: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('UPDATE shops SET promoted = ? WHERE id = ?', (1 if promoted else 0, shop_id))
        await db.commit()

async def get_promoted_shops():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM shops WHERE promoted = 1')
        rows = await cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

async def save_user(user: types.User):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT OR IGNORE INTO users (user_id, first_name, last_name, username, created_at)
            VALUES (?, ?, ?, ?, datetime('now'))
        ''', (
            user.id,
            user.first_name or '',
            user.last_name or '',
            user.username or ''
        ))
        await db.commit()

async def get_all_users():
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT user_id, first_name, last_name, username FROM users')
        rows = await cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

# --- ALIASY PRODUKTÓW ---
async def add_product_alias(product, alias):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT INTO product_aliases (product, alias) VALUES (?, ?)', (product, alias))
        await db.commit()

async def get_product_by_alias(alias):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT product FROM product_aliases WHERE alias = ?', (alias,))
        row = await cursor.fetchone()
        if row:
            return row[0]
        return None

async def get_aliases_for_product(product):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT alias FROM product_aliases WHERE product = ?', (product,))
        return [row[0] for row in await cursor.fetchall()]

# --- NIGHT COIN (NC) ---
import aiosqlite

async def add_nc(user_id: int, amount: int, reason: str = None):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS night_coin (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        ''')
        await db.execute('''
            CREATE TABLE IF NOT EXISTS night_coin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at TEXT
            )
        ''')
        await db.execute('''
            INSERT INTO night_coin (user_id, balance) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET balance = balance + excluded.balance
        ''', (user_id, amount))
        await db.execute('''
            INSERT INTO night_coin_history (user_id, amount, reason, created_at) VALUES (?, ?, ?, ?)
        ''', (user_id, amount, reason or '', datetime.now().isoformat()))
        await db.commit()

async def get_nc(user_id: int) -> int:
    DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS night_coin (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        ''')
        cursor = await db.execute('SELECT balance FROM night_coin WHERE user_id=?', (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

async def get_nc_history(user_id: int, limit: int = 10):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS night_coin_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                amount INTEGER,
                reason TEXT,
                created_at TEXT
            )
        ''')
        cursor = await db.execute('''
            SELECT amount, reason, created_at FROM night_coin_history WHERE user_id=? ORDER BY id DESC LIMIT ?
        ''', (user_id, limit))
        return await cursor.fetchall()

async def get_nc_top(limit: int = 10):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS night_coin (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER DEFAULT 0
            )
        ''')
        cursor = await db.execute('''
            SELECT user_id, balance FROM night_coin ORDER BY balance DESC LIMIT ?
        ''', (limit,))
        return await cursor.fetchall()

async def get_shop_with_random_clicks(shop_id):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM shops WHERE id = ?', (shop_id,))
        row = await cursor.fetchone()
        if not row:
            return None
        columns = [column[0] for column in cursor.description]
        shop = dict(zip(columns, row))
        if shop.get('clicks', 0) == 0:
            clicks = random.randint(400, 900)
            await db.execute('UPDATE shops SET clicks = ? WHERE id = ?', (clicks, shop_id))
            await db.commit()
            shop['clicks'] = clicks
        return shop

# --- SYSTEM POLECEŃ ---
async def add_referral(referrer_id: int, referred_id: int):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                created_at TEXT
            )
        ''')
        await db.execute('''
            INSERT INTO referrals (referrer_id, referred_id, created_at) VALUES (?, ?, ?)
        ''', (referrer_id, referred_id, datetime.now().isoformat()))
        await db.commit()

async def get_referral_count(user_id: int):
    DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id INTEGER,
                referred_id INTEGER,
                created_at TEXT
            )
        ''')
        cursor = await db.execute('SELECT COUNT(*) FROM referrals WHERE referrer_id=?', (user_id,))
        row = await cursor.fetchone()
        return row[0] if row else 0

import aiosqlite

async def create_favorites_table():
    async with aiosqlite.connect('shops.db') as db:
        await db.execute('''CREATE TABLE IF NOT EXISTS user_favorites (
            user_id INTEGER,
            shop_id INTEGER,
            PRIMARY KEY (user_id, shop_id)
        )''')
        await db.commit()

async def add_favorite(user_id, shop_id):
    await create_favorites_table()
    async with aiosqlite.connect('shops.db') as db:
        await db.execute('INSERT OR IGNORE INTO user_favorites (user_id, shop_id) VALUES (?, ?)', (user_id, shop_id))
        await db.commit()

async def remove_favorite(user_id, shop_id):
    await create_favorites_table()
    async with aiosqlite.connect('shops.db') as db:
        await db.execute('DELETE FROM user_favorites WHERE user_id=? AND shop_id=?', (user_id, shop_id))
        await db.commit()

async def is_favorite(user_id, shop_id):
    await create_favorites_table()
    async with aiosqlite.connect('shops.db') as db:
        cursor = await db.execute('SELECT 1 FROM user_favorites WHERE user_id=? AND shop_id=?', (user_id, shop_id))
        return await cursor.fetchone() is not None

async def get_user_favorites(user_id):
    await create_favorites_table()
    async with aiosqlite.connect('shops.db') as db:
        cursor = await db.execute('SELECT shop_id FROM user_favorites WHERE user_id=?', (user_id,))
        return [row[0] for row in await cursor.fetchall()]

async def get_favorite_users(shop_id):
    await create_favorites_table()
    async with aiosqlite.connect('shops.db') as db:
        cursor = await db.execute('SELECT user_id FROM user_favorites WHERE shop_id=?', (shop_id,))
        return [row[0] for row in await cursor.fetchall()]

# --- OLX: pobieranie ogłoszenia po ID ---
async def get_olx_ad_by_id(ad_id):
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM olx_ads WHERE id=?', (ad_id,))
        row = await cursor.fetchone()
        if row:
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return None

# --- OLX: pobieranie wszystkich ogłoszeń (dla admina) ---
async def get_all_olx_ads():
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT * FROM olx_ads ORDER BY created_at DESC')
        rows = await cursor.fetchall()
        return [dict(zip([column[0] for column in cursor.description], row)) for row in rows]

# --- NOTYFIKACJE: subskrypcje powiadomień ---

async def migrate_notification_subs_table():
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS notification_subs (
                user_id INTEGER PRIMARY KEY
            )
        ''')
        await db.commit()

async def add_notification_sub(user_id):
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('INSERT OR IGNORE INTO notification_subs (user_id) VALUES (?)', (user_id,))
        await db.commit()

async def remove_notification_sub(user_id):
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('DELETE FROM notification_subs WHERE user_id=?', (user_id,))
        await db.commit()

async def get_notification_subs():
    import aiosqlite
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute('SELECT user_id FROM notification_subs')
        rows = await cursor.fetchall()
        return [row[0] for row in rows]
