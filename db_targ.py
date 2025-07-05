import aiosqlite
import datetime

DB_PATH = "targ_ogloszenia.db"

async def init_targ_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            CREATE TABLE IF NOT EXISTS ogloszenia (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                username TEXT,
                typ TEXT,
                cena TEXT,
                opis TEXT,
                photo_id TEXT,
                miejscowosc TEXT,
                bezpieczne INTEGER,
                data_dodania TEXT
            )
        ''')
        await db.commit()

async def add_ogloszenie(user_id, username, typ, cena, opis, photo_id, miejscowosc, bezpieczne):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute('''
            INSERT INTO ogloszenia (user_id, username, typ, cena, opis, photo_id, miejscowosc, bezpieczne, data_dodania)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (user_id, username, typ, cena, opis, photo_id, miejscowosc, int(bezpieczne), datetime.datetime.now().isoformat()))
        await db.commit()

async def get_ogloszenia():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM ogloszenia ORDER BY id DESC') as cursor:
            return await cursor.fetchall()

async def get_ogloszenie_by_id(ogloszenie_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM ogloszenia WHERE id = ?', (ogloszenie_id,)) as cursor:
            return await cursor.fetchone()

async def get_ogloszenia_by_user(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute('SELECT * FROM ogloszenia WHERE user_id = ? ORDER BY id DESC', (user_id,)) as cursor:
            return await cursor.fetchall()

async def delete_ogloszenie(ogloszenie_id, user_id=None):
    async with aiosqlite.connect(DB_PATH) as db:
        if user_id:
            await db.execute('DELETE FROM ogloszenia WHERE id = ? AND user_id = ?', (ogloszenie_id, user_id))
        else:
            await db.execute('DELETE FROM ogloszenia WHERE id = ?', (ogloszenie_id,))
        await db.commit()

async def update_ogloszenie(ogloszenie_id, **kwargs):
    async with aiosqlite.connect(DB_PATH) as db:
        fields = []
        values = []
        for k, v in kwargs.items():
            fields.append(f"{k} = ?")
            values.append(v)
        values.append(ogloszenie_id)
        await db.execute(f'UPDATE ogloszenia SET {", ".join(fields)} WHERE id = ?', values)
        await db.commit()

async def ensure_schema():
    # Definicja wymaganych kolumn: nazwa -> SQL typ
    required_columns = {
        'id': 'INTEGER PRIMARY KEY AUTOINCREMENT',
        'user_id': 'INTEGER',
        'username': 'TEXT',
        'typ': 'TEXT',
        'cena': 'TEXT',
        'opis': 'TEXT',
        'photo_id': 'TEXT',
        'miejscowosc': 'TEXT',
        'bezpieczne': 'INTEGER',
        'data_dodania': 'TEXT',
        'wyswietlenia': 'INTEGER DEFAULT 0',
        'promoted_until': 'TEXT'  # data do kiedy ogłoszenie jest promowane
    }
    async with aiosqlite.connect(DB_PATH) as db:
        # Tworzenie tabeli jeśli nie istnieje
        await db.execute(f"""
            CREATE TABLE IF NOT EXISTS ogloszenia (
                {', '.join([f'{k} {v}' for k, v in required_columns.items()])}
            )
        """)
        # Sprawdzenie istniejących kolumn
        async with db.execute("PRAGMA table_info(ogloszenia)") as cursor:
            existing = {row[1] async for row in cursor}
        # Dodanie brakujących kolumn
        for col, sqltype in required_columns.items():
            if col not in existing:
                await db.execute(f"ALTER TABLE ogloszenia ADD COLUMN {col} {sqltype}")
        await db.commit()
