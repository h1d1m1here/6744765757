from aiogram import Router, types
from aiogram.fsm.context import FSMContext
from db import add_opinion, add_rating, get_opinions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from aiogram import F
from aiogram.fsm.state import State, StatesGroup
import os
from handlers.search import search_router

main_router = Router()


USERS_FILE = os.path.join(os.path.dirname(__file__), "users.txt")

def log_user(user_id):
    try:
        if not os.path.exists(USERS_FILE):
            with open(USERS_FILE, "w") as f:
                f.write("")
        with open(USERS_FILE, "r+") as f:
            users = set(line.strip() for line in f if line.strip())
            if str(user_id) not in users:
                f.write(f"{user_id}\n")
    except Exception as e:
        print(f"[LOG_USER ERROR] {e}")

# --- DEBUG: Komendy admina ---
@main_router.message(Command("link1"))
async def cmd_link1(message: types.Message, state: FSMContext):
    print(f"[DEBUG] cmd_link1: {message.text} | from_user: {message.from_user.id}")
    # await start_edit_shop_field(message, "bot_link", "linku do bota")

@main_router.message(Command("link2"))
async def cmd_link2(message: types.Message, state: FSMContext):
    print(f"[DEBUG] cmd_link2: {message.text} | from_user: {message.from_user.id}")
    # await start_edit_shop_field(message, "operator_link", "linku do operatora")

@main_router.message(Command("link3"))
async def cmd_link3(message: types.Message, state: FSMContext):
    print(f"[DEBUG] cmd_link3: {message.text} | from_user: {message.from_user.id}")
    # await start_edit_shop_field(message, "chat_link", "linku do chatu")

@main_router.message(Command("link4"))
async def cmd_link4(message: types.Message, state: FSMContext):
    print(f"[DEBUG] cmd_link4: {message.text} | from_user: {message.from_user.id}")
    # await start_edit_shop_field(message, "www", "linku do www")

@main_router.message(Command("edytuj_opis"))
async def cmd_edit_desc(message: types.Message, state: FSMContext):
    print(f"[DEBUG] cmd_edit_desc: {message.text} | from_user: {message.from_user.id}")
    # await start_edit_shop_field(message, "description", "opisu")

@main_router.message(Command("edytuj_nazwe"))
async def cmd_edit_name(message: types.Message, state: FSMContext):
    print(f"[DEBUG] cmd_edit_name: {message.text} | from_user: {message.from_user.id}")
    # await start_edit_shop_field(message, "shop_name", "nazwy")

# --- FSM do opiniowania sklepu ---
class RateShopStates(StatesGroup):
    waiting_for_oferta = State()
    waiting_for_obsluga = State()
    waiting_for_odbior = State()
    waiting_for_opinion = State()
    waiting_for_photo = State()

# Handler przycisku "Oceń ten sklep"
@main_router.callback_query(lambda c: c.data.startswith("rate_shop_"))
async def rate_shop_start(callback: types.CallbackQuery, state: FSMContext):
    shop_id = callback.data.split("_", 2)[2]
    await state.update_data(shop_id=shop_id)
    # Oferta
    kb = InlineKeyboardBuilder()
    for i in range(1, 11):
        kb.button(text=str(i), callback_data=f"oferta_{i}")
    kb.adjust(5)
    text = (
        "<b>Oceń Ofertę tego sklepu (1-10):</b>\n"
        "1️⃣ Oferta jest słaba, sklep nie ma wiele do zaoferowania.\n"
        "🔟 Oferta Cię zadowoliła, sklep ma wiele atrakcyjnych produktów."
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(RateShopStates.waiting_for_oferta)
    await callback.answer()

@main_router.callback_query(lambda c: c.data.startswith("oferta_"), RateShopStates.waiting_for_oferta)
async def rate_shop_oferta(callback: types.CallbackQuery, state: FSMContext):
    oferta = int(callback.data.split("_", 1)[1])
    await state.update_data(oferta=oferta)
    # Obsługa
    kb = InlineKeyboardBuilder()
    for i in range(1, 11):
        kb.button(text=str(i), callback_data=f"obsluga_{i}")
    kb.adjust(5)
    text = (
        "<b>Oceń jakość obsługi (1-10):</b>\n"
        "1️⃣ Bardzo słabo, problem z kontaktem, niemiła obsługa.\n"
        "🔟 Perfekcyjnie, świetna atmosfera, szybki kontakt."
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(RateShopStates.waiting_for_obsluga)
    await callback.answer()

@main_router.callback_query(lambda c: c.data.startswith("obsluga_"), RateShopStates.waiting_for_obsluga)
async def rate_shop_obsluga(callback: types.CallbackQuery, state: FSMContext):
    obsluga = int(callback.data.split("_", 1)[1])
    await state.update_data(obsluga=obsluga)
    # Odbiór
    kb = InlineKeyboardBuilder()
    for i in range(1, 11):
        kb.button(text=str(i), callback_data=f"odbior_{i}")
    kb.adjust(5)
    text = (
        "<b>Oceń odbiór zamówienia (1-10):</b>\n"
        "1️⃣😡 Bardzo trudny, problemy z lokalizacją, brak wsparcia.\n"
        "🔟😃 Bardzo łatwy, idealnie oznaczony, wsparcie operatora."
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(RateShopStates.waiting_for_odbior)
    await callback.answer()

@main_router.callback_query(lambda c: c.data.startswith("odbior_"), RateShopStates.waiting_for_odbior)
async def rate_shop_odbior(callback: types.CallbackQuery, state: FSMContext):
    odbior = int(callback.data.split("_", 1)[1])
    await state.update_data(odbior=odbior)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Wróć", callback_data="rate_shop_back")
    kb.button(text="🏠 HOME", callback_data="home_0")
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Napisz swoją opinię o sklepie (min. 10 znaków):", reply_markup=kb.as_markup())
    await state.set_state(RateShopStates.waiting_for_opinion)
    await callback.answer()

# Handler przycisku Pomiń zdjęcie
@main_router.callback_query(lambda c: c.data == "rate_skip_photo", RateShopStates.waiting_for_photo)
async def rate_shop_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Dziękujemy za opinię! Twoja ocena została zapisana.")
    await state.clear()
    await callback.answer()

# Handler przycisku Wstecz podczas opiniowania (poprawiony układ przycisków)
@main_router.callback_query(lambda c: c.data == "rate_shop_back", RateShopStates.waiting_for_opinion)
async def rate_shop_back_opinion(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    shop_id = data.get("shop_id")
    kb = InlineKeyboardBuilder()
    for i in range(1, 6):
        kb.button(text=str(i), callback_data=f"setrate_{i}")
    kb.adjust(5)
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"shop_{shop_id}"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0")
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Wybierz ocenę sklepu (1-5):", reply_markup=kb.as_markup())
    await state.set_state(RateShopStates.waiting_for_rating)
    await callback.answer()

# Handler przyjmujący zdjęcie do opinii
@main_router.message(RateShopStates.waiting_for_photo, F.photo)
async def rate_shop_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    shop_id = data.get("shop_id")
    rating = data.get("rating")
    # Pobierz ostatnią opinię użytkownika do tego sklepu (opcjonalnie)
    photo_id = message.photo[-1].file_id
    # Dodaj opinię ze zdjęciem (możesz rozwinąć o update, jeśli już istnieje tekst)
    await add_opinion(shop_id, message.from_user.id, None, photo_id=photo_id, user_name=message.from_user.full_name, user_username=message.from_user.username)
    await message.answer("Dziękujemy za opinię i zdjęcie! Twoja ocena została zapisana.")
    await state.clear()

@main_router.message(RateShopStates.waiting_for_opinion)
async def rate_shop_opinion(message: types.Message, state: FSMContext):
    print(f"[NIGHTLIST DEBUG] Otrzymano opinię od {message.from_user.id}: {message.text}")
    opinion = message.text.strip()
    if len(opinion) < 10:
        await message.answer("Opinia musi mieć minimum 10 znaków. Spróbuj ponownie.")
        return
    data = await state.get_data()
    shop_id = data.get("shop_id")
    oferta = data.get("oferta")
    obsluga = data.get("obsluga")
    odbior = data.get("odbior")
    # --- BLOKADA 24H PER SKLEP ---
    from db import aiosqlite
    import datetime
    async with aiosqlite.connect(os.path.join(os.path.dirname(__file__), 'shops.db')) as db:
        cursor = await db.execute('SELECT created_at FROM opinions WHERE user_id = ? AND shop_id = ? ORDER BY created_at DESC LIMIT 1', (message.from_user.id, shop_id))
        row = await cursor.fetchone()
        if row:
            last = datetime.datetime.fromisoformat(row[0])
            if (datetime.datetime.now() - last).total_seconds() < 24*3600:
                await message.answer("Możesz dodać opinię do tego sklepu tylko raz na 24h!")
                return
    # --- ZAPIS OPINII ---
    await add_opinion(shop_id, message.from_user.id, opinion, user_name=message.from_user.full_name, user_username=message.from_user.username)
    # --- 5NC ---
    from db import add_nc
    import random
    await add_nc(message.from_user.id, random.randint(10, 20), reason="opinia")
    # --- WIADOMOŚĆ NA GRUPĘ ---
    import os
    GROUP_ID = os.getenv("GROUP_ID")
    if GROUP_ID:
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        url = f"https://t.me/{message.bot.username}?start=shop_{shop_id}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Zobacz sklep", url=url)]]
        )
        await message.bot.send_message(GROUP_ID, f"🆕 Dodano nową opinię do sklepu!", reply_markup=kb)
    await message.answer("Dziękujemy za Twoją opinię i ocenę! Otrzymujesz 5 NC!")
    await state.set_state(RateShopStates.waiting_for_photo)
