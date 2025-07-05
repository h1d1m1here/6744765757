# USUŃ LUB ZAKOMENTUJ CAŁY PLIK shop_search.py, jeśli nie korzystasz z bazy!
# Ten plik jest niepotrzebny, jeśli korzystasz z wyszukiwania opartego o JSON w handlers/search.py.
# Jeśli chcesz zachować plik na przyszłość, możesz go po prostu zakomentować lub usunąć z rejestracji routerów.

# from aiogram import Router, types, F
# from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
# from aiogram.fsm.context import FSMContext
# from aiogram.fsm.state import State, StatesGroup
# from db import get_shops, get_shop
# import aiosqlite
# import os
# from aiogram.filters import Command

# shop_search_router = Router()

# class ShopSearchStates(StatesGroup):
#     waiting_for_city = State()
#     waiting_for_product = State()

# @shop_search_router.message(Command("szukaj"))
# async def search_start(message: types.Message, state: FSMContext):
#     # Pobierz unikalne miasta z bazy
#     import aiosqlite
#     DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute('SELECT DISTINCT city FROM shop_products ORDER BY city')
#         cities = [row[0] for row in await cursor.fetchall()]
#     if not cities:
#         await message.answer("Brak dostępnych miast w bazie.")
#         return
#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[[InlineKeyboardButton(text=city, callback_data=f"search_city_{city}")] for city in cities]
#     )
#     await message.answer("Wybierz miasto:", reply_markup=kb)
#     await state.set_state(ShopSearchStates.waiting_for_city)

# @shop_search_router.callback_query(F.data.startswith("search_city_"))
# async def search_city(callback: types.CallbackQuery, state: FSMContext):
#     city = callback.data.replace("search_city_", "")
#     await state.update_data(city=city)
#     import aiosqlite
#     DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
#     # Pobierz unikalne produkty dla miasta
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute('SELECT DISTINCT product FROM shop_products WHERE city=? ORDER BY product', (city,))
#         products = [row[0] for row in await cursor.fetchall()]
#     # Dodaj aliasy do listy wyboru
#     from db import get_aliases_for_product
#     aliases_map = {}
#     for prod in products:
#         aliases = await get_aliases_for_product(prod)
#         for alias in aliases:
#             aliases_map[alias] = prod
#     all_options = products + list(aliases_map.keys())
#     if not all_options:
#         await callback.message.answer("Brak produktów w tym mieście.")
#         # Możesz tu dodać losowe sklepy:
#         from db import get_shops
#         shops = await get_shops()
#         import random
#         random_shops = random.sample(shops, min(3, len(shops))) if shops else []
#         if random_shops:
#             text = "Losowe sklepy z bazy:\n" + "\n".join(f"- {s['shop_name']}" for s in random_shops)
#             await callback.message.answer(text)
#         else:
#             await callback.message.answer("Brak sklepów w bazie.")
#         await state.clear()
#         await callback.answer()
#         return
#     kb = InlineKeyboardMarkup(
#         inline_keyboard=[[InlineKeyboardButton(text=opt, callback_data=f"search_product_{opt}")] for opt in all_options]
#     )
#     await callback.message.answer(f"Miasto: {city}\nWybierz produkt:", reply_markup=kb)
#     await state.set_state(ShopSearchStates.waiting_for_product)
#     await callback.answer()

# @shop_search_router.callback_query(F.data.startswith("search_product_"))
# async def search_product(callback: types.CallbackQuery, state: FSMContext):
#     product = callback.data.replace("search_product_", "")
#     data = await state.get_data()
#     city = data.get("city")
#     import aiosqlite
#     DB_PATH = os.path.join(os.path.dirname(__file__), 'shops.db')
#     # Sprawdź czy to alias
#     from db import get_product_by_alias
#     real_product = await get_product_by_alias(product)
#     if real_product:
#         product = real_product
#     # Pobierz sklepy, które mają ten produkt w tym mieście
#     async with aiosqlite.connect(DB_PATH) as db:
#         cursor = await db.execute('''
#             SELECT shop_id FROM shop_products WHERE city=? AND product=?
#         ''', (city, product))
#         shop_ids = [row[0] for row in await cursor.fetchall()]
#     from db import get_shops
#     shops = await get_shops()
#     found_shops = [shop for shop in shops if shop['id'] in shop_ids]
#     if not found_shops:
#         await callback.message.answer("Brak sklepów z tym produktem w wybranym mieście.")
#         # Losowe sklepy jako fallback
#         import random
#         random_shops = random.sample(shops, min(3, len(shops))) if shops else []
#         if random_shops:
#             text = "Losowe sklepy z bazy:\n" + "\n".join(f"- {s['shop_name']}" for s in random_shops)
#             await callback.message.answer(text)
#         else:
#             await callback.message.answer("Brak sklepów w bazie.")
#         await state.clear()
#         await callback.answer()
#         return
#     text = f"<b>Sklepy w {city} z produktem: {product}</b>\n"
#     for shop in found_shops:
#         text += f"- {shop['shop_name']}\n"
#     await callback.message.answer(text, parse_mode="HTML")
#     await state.clear()
#     await callback.answer()
