import asyncio
import json
from db import init_db, add_shop

async def import_shops():
    await init_db()
    with open('shops.json', 'r', encoding='utf-8') as f:
        shops = json.load(f)
        for shop in shops:
            await add_shop(shop)
    print('Import zakończony!')

if __name__ == '__main__':
    asyncio.run(import_shops())
