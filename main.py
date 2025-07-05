# --- Funkcja sprawdzająca czy użytkownik jest operatorem ---
def is_operator_user(user):
    if user.id in OPERATORS:
        return True
    if user.username and ("@" + user.username.lower()) in OPERATORS:
        return True
    return False

from nocna_offer import nocna_offer_router
from nocny_targ import nocny_targ_router
import logging
import sqlite3
import threading
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile, BufferedInputFile
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.enums import ParseMode
from aiogram.utils.markdown import hbold
import asyncio
from db import init_db, get_shops, get_shop, get_ratings, add_rating, get_opinions, add_opinion, get_opinions_full, set_shop_promoted, get_promoted_shops, save_user, add_nc, get_nc, add_favorite, remove_favorite, is_favorite, get_user_favorites, get_favorite_users, user_opinion_last_24h, add_user_item
from db_nocna import get_last_chest_open, set_chest_open
from dotenv import load_dotenv
import os
from math import ceil
from aiogram.client.default import DefaultBotProperties
import datetime
from datetime import timedelta
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram import Bot, Dispatcher, types
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from olx import AddAdStates
from main_router import main_router
from aiogram.types import Message
from zoneinfo import ZoneInfo
from handlers.addproduct import add_product_router
from aiogram.fsm.state import State, StatesGroup, default_state
from aiogram import Router
from aiogram import F
import random
from handlers.search import search_router
from kasyno import kasyno_router
import aiosqlite
import requests
from ui_search import (
    SearchStates,
    search_menu_start,
    search_sklep_selected,
    search_city_selected,
    search_phrase_entered
)
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.command import CommandObject
from produkty_sklepy.produkty_zabka import produkty_zabka
from funkcje.stats_panel import stats_router
from funkcje.users_panel import cmd_user_panel
BONUS_ITEMS = [
    "Ubita lufka",
    "Plastikowa butelka z odciętym dnem",
    "Mały pakunek owinięty żółto-zieloną taśmą",
    "Widelec do wykopek"
]

# Szansa na znalezienie przedmiotu (np. 1%)
BONUS_ITEM_CHANCE = 0.01

async def try_give_random_item(user_id, message_or_callback):
    import random
    if random.random() < BONUS_ITEM_CHANCE:
        item = random.choice(BONUS_ITEMS)
        # Sprawdź czy użytkownik już ma ten przedmiot
        from db import get_user_items
        items = await get_user_items(user_id)
        if item not in items:
            await add_user_item(user_id, item)
            await message_or_callback.answer(f"🎉 Znalazłeś wyjątkowy przedmiot: <b>{item}</b>!", parse_mode="HTML", show_alert=True)
            return True
    return False
from funkcje.olx_panel import olx_panel_router
from aiogram.filters import Command
from funkcje.notifications import notifications_router
from db import ban_user, is_banned, unban_user, warn_user, get_warns, mute_user, is_muted, unmute_user, del_warn
from aiogram.filters import CommandObject
import re

load_dotenv()
# Obsługa wielu adminów
ADMIN_IDS = set(os.getenv("ADMIN_ID", "").split(","))
ADMIN_IDS.add("8132494878")  # Dodany drugi admin na sztywno, można też dodać do .env jako ADMIN_ID=7572862671,8132494878
ADMIN_ID = os.getenv("ADMIN_ID", "").split(",")[0] if os.getenv("ADMIN_ID", "") else "8132494878"  # Użyj pierwszego admina jako głównego

API_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = os.getenv("CHANNEL_ID")
GROUP_ID = os.getenv("GROUP_ID")

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
# Poprawna rejestracja routerów:
main_router.include_router(nocny_targ_router)
dp.include_router(main_router)

SHOPS_PER_PAGE_FIRST = 6   # pierwsza strona po TOP3
SHOPS_PER_PAGE_NEXT = 12   # kolejne strony
addphoto_state = {}

_OPERATORS_DB_PATH = "operators.db"
_OPERATORS_DB_LOCK = threading.Lock()

class TestFSMStates(StatesGroup):
    waiting_for_test = State()

@dp.message(Command("testfsm"))
async def testfsm_start(message: types.Message, state: FSMContext):
    print("[DEBUG] testfsm_start handler WYWOŁANY!")
    await message.answer("Podaj dowolny tekst (test FSM):")
    await state.set_state(TestFSMStates.waiting_for_test)

@dp.message(TestFSMStates.waiting_for_test)
async def testfsm_waiting(message: types.Message, state: FSMContext):
    print(f"[DEBUG] testfsm_waiting handler WYWOŁANY! text={message.text}")
    await message.answer(f"Odebrano: {message.text}\nFSM DZIAŁA! (stan: {await state.get_state()})")
    await state.clear()

# Pomocnicza funkcja do wyliczania średniej oceny
async def get_average_rating(shop_id):
    from db import get_shop
    shop = await get_shop(shop_id)
    if shop and shop.get('average_rating') is not None:
        return round(shop['average_rating'], 2)
    ratings = await get_ratings(shop_id)
    if not ratings:
        return 0
    return round(sum(ratings) / len(ratings), 2)

# Pomocnicza funkcja do pobierania i sortowania sklepów wg średniej oceny
async def get_sorted_shops():
    shops = await get_shops()
    shops_with_avg = []
    for shop in shops:
        avg = await get_average_rating(shop['id'])
        shop['avg_rating'] = avg
        shops_with_avg.append(shop)
    return sorted(shops_with_avg, key=lambda s: s['avg_rating'], reverse=True)

# Pomocnicza funkcja do generowania paginacji
async def get_shops_page(page: int):
    shops = await get_sorted_shops()
    top3 = shops[:3]
    rest = shops[3:]
    total = len(rest)
    # Wylicz liczbę stron: pierwsza strona ma 6, kolejne po 10
    if total <= SHOPS_PER_PAGE_FIRST:
        pages = 1
    else:
        # 1 strona po 6, reszta po 10
        pages = 1 + ((total - SHOPS_PER_PAGE_FIRST + SHOPS_PER_PAGE_NEXT - 1) // SHOPS_PER_PAGE_NEXT)
    page = page % pages  # zawijanie
    if page == 0:
        start = 0
        end = SHOPS_PER_PAGE_FIRST
        return top3, rest[start:end], page, pages
    else:
        start = SHOPS_PER_PAGE_FIRST + (page - 1) * SHOPS_PER_PAGE_NEXT
        end = start + SHOPS_PER_PAGE_NEXT
        return [], rest[start:end], page, pages


@dp.message(Command("unmute"))
async def cmd_unmute(message: types.Message, command: CommandObject):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("⛔ Brak uprawnień.")
        return
    # Pobierz argumenty komendy (np. ID użytkownika)
    args = message.text.split()[1:]
    user_id = await extract_user_id(message, args)
    if not user_id:
        await message.answer("Podaj ID lub odpowiedz na wiadomość użytkownika.")
        return
    await unmute_user(user_id)
    if message.chat and message.chat.type in ("group", "supergroup"):
        try:
            await message.bot.restrict_chat_member(message.chat.id, user_id, permissions=types.ChatPermissions(can_send_messages=True))
        except Exception:
            pass
    await message.answer(f"Użytkownik {user_id} został odciszony.")

@dp.message(Command("delwarn"))
async def cmd_delwarn(message: types.Message, command: CommandObject):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split()[1:]
    user_id = await extract_user_id(message, args)
    if not user_id:
        await message.answer("Podaj ID lub odpowiedz na wiadomość użytkownika.")
        return
    await del_warn(user_id)
    await message.answer(f"Usunięto jedno ostrzeżenie dla użytkownika {user_id}.")


# Helper: extract user_id from reply, @nick, or argument
async def extract_user_id(message, args):
    if message.reply_to_message:
        return message.reply_to_message.from_user.id
    if args:
        # Try ID
        if args[0].isdigit():
            return int(args[0])
        # Try @nick
        if args[0].startswith("@"):
            username = args[0][1:]
            try:
                user = await message.bot.get_chat(username)
                return user.id
            except Exception:
                return None
    return None

@dp.message(Command("ban"))
async def cmd_ban(message: types.Message, command: CommandObject):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split()[1:]
    user_id = await extract_user_id(message, args)
    if not user_id:
        await message.answer("Podaj ID lub odpowiedz na wiadomość użytkownika.")
        return
    await ban_user(user_id, message.from_user.id, reason="manual ban")
    # Spróbuj usunąć z grupy jeśli to grupa
    if message.chat and message.chat.type in ("group", "supergroup"):
        try:
            await message.bot.ban_chat_member(message.chat.id, user_id)
        except Exception:
            pass
    await message.answer(f"Użytkownik {user_id} został zbanowany.")

@dp.message(Command("unban"))
async def cmd_unban(message: types.Message, command: CommandObject):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split()[1:]
    user_id = await extract_user_id(message, args)
    if not user_id:
        await message.answer("Podaj ID lub odpowiedz na wiadomość użytkownika.")
        return
    await unban_user(user_id)
    await message.answer(f"Użytkownik {user_id} został odbanowany.")

@dp.message(Command("warn"))
async def cmd_warn(message: types.Message, command: CommandObject):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split()[1:]
    user_id = await extract_user_id(message, args)
    if not user_id:
        await message.answer("Podaj ID lub odpowiedz na wiadomość użytkownika.")
        return
    await warn_user(user_id, message.from_user.id, reason="manual warn")
    warns = await get_warns(user_id)
    if len(warns) >= 3:
        # Ban na 14 dni
        until = datetime.now() + timedelta(days=14)
        await ban_user(user_id, message.from_user.id, reason="3 warny = ban na 14 dni")
        await mute_user(user_id, until, message.from_user.id, reason="ban za 3 warny")
        await message.answer(f"Użytkownik {user_id} otrzymał 3 ostrzeżenia i został zbanowany na 14 dni.")
    else:
        await message.answer(f"Użytkownik {user_id} otrzymał ostrzeżenie. ({len(warns)}/3)")

@dp.message(Command("mute"))
async def cmd_mute(message: types.Message, command: CommandObject):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split()[1:]
    user_id = await extract_user_id(message, args)
    if not user_id:
        await message.answer("Podaj ID lub odpowiedz na wiadomość użytkownika.")
        return
    # domyślnie 10 minut
    mute_time = 10
    mute_unit = 'm'
    if len(args) > 1:
        match = re.match(r"(\d+)([mh])", args[1])
        if match:
            mute_time = int(match.group(1))
            mute_unit = match.group(2)
    until = datetime.now() + (timedelta(minutes=mute_time) if mute_unit == 'm' else timedelta(hours=mute_time))
    await mute_user(user_id, until, message.from_user.id, reason="manual mute")
    # Spróbuj wyciszyć w grupie
    if message.chat and message.chat.type in ("group", "supergroup"):
        try:
            await message.bot.restrict_chat_member(message.chat.id, user_id, permissions=types.ChatPermissions(can_send_messages=False), until_date=until)
        except Exception:
            pass
    await message.answer(f"Użytkownik {user_id} został wyciszony do {until:%Y-%m-%d %H:%M}.")

# BLOKADA DOSTĘPU DO BOTA DLA ZBANOWANYCH

async def send_shops_page(message, page: int, edit=False, filter_flag=None):
    # Usuwanie poprzedniej wiadomości jeśli to możliwe (efekt znikania)
    try:
        await message.delete()
    except Exception:
        pass
    # Pobierz sklepy i przefiltruj po fladze jeśli trzeba
    all_shops = await get_sorted_shops()
    if filter_flag:
        # Zamień kod na emoji
        flag_map = {"PL": "🇵🇱", "UA": "🇺🇦", "DE": "🇩🇪"}
        flag_emoji = flag_map.get(filter_flag, filter_flag)
        all_shops = [s for s in all_shops if (s.get('flag') or '').startswith(flag_emoji)]
    top3 = all_shops[:3]
    rest = all_shops[3:]
    total = len(rest)
    SHOPS_PER_PAGE_FIRST = 6
    SHOPS_PER_PAGE_NEXT = 12
    if total <= SHOPS_PER_PAGE_FIRST:
        pages = 1
    else:
        pages = 1 + ((total - SHOPS_PER_PAGE_FIRST + SHOPS_PER_PAGE_NEXT - 1) // SHOPS_PER_PAGE_NEXT)
    page = page % pages if pages > 0 else 0
    kb = InlineKeyboardBuilder()
    # Przycisk Night_Shop na samej górze
    kb.row(InlineKeyboardButton(text="🌘Night_Shop", callback_data="noc_menu_offer"))
    # Pierwsza strona: TOP3 + 6 kolejnych sklepów
    if page == 0:
        # TOP3
        for idx, shop in enumerate(top3):
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            flag = shop.get('flag', '') or ''
            btn = InlineKeyboardButton(
                text=f"🏆 {flag} {shop['shop_name']}  ⭐{avg} ({count})",
                callback_data=f"shop_{shop['id']}"
            )
            kb.row(btn)
        # 6 kolejnych sklepów (jeśli są)
        shops = rest[:SHOPS_PER_PAGE_FIRST]
        row = []
        for i, shop in enumerate(shops):
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            flag = shop.get('flag', '') or ''
            btn = InlineKeyboardButton(
                text=f"{flag} {shop['shop_name']}  ⭐{avg} ({count})",
                callback_data=f"shop_{shop['id']}"
            )
            row.append(btn)
            if len(row) == 2:
                kb.row(*row)
                row = []
        if row:
            kb.row(*row)
    else:
        # Kolejne strony: po 12 sklepów, po 2 w wierszu
        start = SHOPS_PER_PAGE_FIRST + (page - 1) * SHOPS_PER_PAGE_NEXT
        end = start + SHOPS_PER_PAGE_NEXT
        shops = rest[start:end]
        row = []
        for shop in shops:
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            flag = shop.get('flag', '') or ''
            btn = InlineKeyboardButton(
                text=f"{flag} {shop['shop_name']}  ⭐{avg} ({count})",
                callback_data=f"shop_{shop['id']}"
            )
            row.append(btn)
            if len(row) == 2:
                kb.row(*row)
                row = []
        if row:
            kb.row(*row)
    # Przyciski nawigacyjne
    nav = [
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="go_back"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
        InlineKeyboardButton(text="➡️ Dalej", callback_data=f"page_{(page+1)%pages}")
    ]
    kb.row(*nav)
    text = (
        f"<b>──────────── LISTA SKLEPÓW ────────────</b>\n"
        f"<i>Strona {page+1} z {pages}</i>\n"
        "────────────────────────"
    )
    photo_path = "noc2.png" if page == 0 else "noc4.png"
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo=photo, caption=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    if message.chat.type != "private":
        await message.reply("Bot działa tylko w prywatnej wiadomości! Napisz do mnie na priv.")
        return
    print(f"[LOG] START: {message.from_user.id} ({message.from_user.username})")
    print(f"[DEBUG] cmd_start: text={message.text}")
    # ZAPISZ UŻYTKOWNIKA DO BAZY
    from db import save_user
    await save_user(message.from_user)
    # Pobierz argumenty startowe z message.text (aiogram v3)
    args = None
    if message.text:
        parts = message.text.split(maxsplit=1)
        if len(parts) > 1:
            args = parts[1]
    if args and args.startswith("shop_"):
        try:
            shop_id = int(args.split("shop_")[1])
            shop = await get_shop(shop_id)
            if shop:
                avg = await get_average_rating(shop_id)
                opinions = await get_opinions(shop_id)
                count = len(opinions)
                text = f"<b>{shop['shop_name']}</b>\n⭐️{avg} ({count} opinii)\n"
                if shop.get('description'):
                    text += f"\n{shop['description']}\n"
                await message.answer(text, parse_mode="HTML")
                # Po wyświetleniu sklepu pokaż nocną listę (menu główne)
                await show_main_menu(await message.as_reply())
                return
        except Exception:
            pass
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ WCHODZĘ", callback_data="accept_rules")]
        ]
    )
    try:
        photo = FSInputFile("nocny111.png")
        await message.answer_photo(photo=photo, reply_markup=kb)
    except Exception:
        await message.answer("Witaj!", reply_markup=kb)

from typing import Callable

def callback_item_wrapper(handler: Callable):
    async def wrapper(callback: types.CallbackQuery, *args, **kwargs):
        await try_give_random_item(callback.from_user.id, callback)
        return await handler(callback, *args, **kwargs)
    return wrapper

@dp.callback_query(lambda c: c.data == "accept_rules")
@callback_item_wrapper
async def show_main_menu(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    # await safe_delete(callback.message)
    print(f"[LOG] MENU: {callback.from_user.id} ({callback.from_user.username})")
    await callback.answer()
    user = callback.from_user
    name = user.first_name or user.username or "Użytkowniku"
    powitania = [
        f"🌑 <b>Nocna24</b> - Witaj, {name}!",
        f"🌙 {name}, cieszymy się, że jesteś z nami!",
        f"⭐ {name}, życzymy udanych i bezpiecznych zakupów!",
        f"👋 Hej {name}! Gotowy na nocne okazje?"
    ]
    text = random.choice(powitania) + "\nWybierz opcję z menu poniżej:"
    kb = InlineKeyboardBuilder()
    # kb.row(InlineKeyboardButton(text="🔎Szukaj🔎", callback_data="search_menu"))  # USUNIĘTO z menu głównego
    # Nowe przyciski na górze
    kb.row(InlineKeyboardButton(text="🌑NIGHT_LIST🌑", callback_data="nocna_lista"))
    kb.row(InlineKeyboardButton(text="⭐️PROMOWANE SKLEPY⭐️", callback_data="promowane_sklepy"))
 # PANEL zamiast TOP 3
    kb.row(
        InlineKeyboardButton(text="  PANEL", callback_data="user_panel")
    )
    kb.row(
        InlineKeyboardButton(text="ℹ️Nocna_Info", callback_data="nocna_info"),
        InlineKeyboardButton(text="🛒 Nocny Targ", callback_data="nocny_targ")
    )
    kb.row(
        InlineKeyboardButton(text="🎁 Nocna Skrzynka", callback_data="nocna_skrzynka")
    )
    kb.row(
        InlineKeyboardButton(text="🎲 Kasyno NC", callback_data="kasyno_menu")
    )
    try:
        photo = FSInputFile("noc2.png")
        await callback.message.answer_photo(photo=photo, caption=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

# Obsługa przycisku PANEL
@dp.callback_query(lambda c: c.data == "user_panel")
async def show_user_panel(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    await try_give_random_item(callback.from_user.id, callback)
    await cmd_user_panel(callback.message)

# Obsługa przycisku PROMOWANE SKLEPY
@dp.callback_query(lambda c: c.data == "promowane_sklepy")
async def show_promoted_shops(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    # await safe_delete(callback.message)
    print(f"[LOG] PROMOWANE: {callback.from_user.id} ({callback.from_user.username})")
    shops = await get_promoted_shops()
    kb = InlineKeyboardBuilder()
    for shop in shops:
        if shop:
            op = shop.get('operator_link')
            op_nick = None
            if op:
                if op.startswith("https://t.me/"):
                    op_nick = "@" + op.split("https://t.me/")[-1].split("/")[0]
                elif op.startswith("@"):
                    op_nick = op
            flag = shop.get('flag', '') or ''
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            btn_text = f"{flag} {shop['shop_name']}  ⭐{avg} ({count})"
            if op_nick:
                btn_text += f" | {op_nick}"
            kb.row(InlineKeyboardButton(text=btn_text, callback_data=f"shop_{shop['id']}"))
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="home_0"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
        InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
    )
    try:
        photo = FSInputFile("promo.png")
        await callback.message.answer_photo(photo=photo, caption="<b>⭐️PROMOWANE SKLEPY⭐️</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer("<b>⭐️PROMOWANE SKLEPY⭐️</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

# Obsługa przycisku TOP 3
@dp.callback_query(lambda c: c.data == "top3_sklepy")
async def show_top3_shops(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    if callback.message.chat.type != "private":
        await callback.answer("TOP3 dostępne tylko w prywatnej wiadomości z botem!", show_alert=True)
        return
    # await safe_delete(callback.message)
    print(f"[LOG] TOP3: {callback.from_user.id} ({callback.from_user.username})")
    await callback.answer()
    top3, _, _, _ = await get_shops_page(0)
    top3 = top3[:3]  # Gwarantuje, że są tylko 3 sklepy
    kb = InlineKeyboardBuilder()
    for shop in top3:
        avg = shop.get('avg_rating', 0)
        opinions = await get_opinions(shop['id'])
        count = len(opinions)
        op = shop.get('operator_link')
        op_nick = None
        if op:
            if op.startswith("https://t.me/"):
                op_nick = "@" + op.split("https://t.me/")[-1].split("/")[0]
            elif op.startswith("@"):
                op_nick = op
        btn_text = f"{shop['shop_name']}  ⭐{avg} ({count})"
        if op_nick:
            btn_text += f" | {op_nick}"
        kb.row(InlineKeyboardButton(text=btn_text, callback_data=f"shop_{shop['id']}"))
    # Przyciski nawigacyjne
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="home_0"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
        InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
    )
    await callback.message.answer("<b>🏆WASZE TOP 3🏆</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data == "nocna_lista")
async def show_night_list(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    await send_night_list_menu(callback.message)
    await callback.answer()

async def send_night_list_menu(message):
    # Usuwanie poprzedniej wiadomości jeśli to możliwe (efekt znikania)
    try:
        await message.delete()
    except Exception:
        pass
    kb = InlineKeyboardBuilder()
    # Pierwsza linia: Show All (z emoji)
    kb.row(InlineKeyboardButton(text="🌍 Show All", callback_data="show_all_shops"))
    # Druga linia: flagi
    kb.row(
        InlineKeyboardButton(text="🇵🇱 PL", callback_data="filter_flag_PL"),
        InlineKeyboardButton(text="🇺🇦 UA", callback_data="filter_flag_UA"),
        InlineKeyboardButton(text="🇩🇪 DE", callback_data="filter_flag_DE")
    )
    # DODAJEMY PRZYCISK SZUKAJ pod flagami
    kb.row(InlineKeyboardButton(text="🔎Szukaj🔎", callback_data="search_menu"))
    # Trzecia linia: powrót do home
    kb.row(InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"))
    text = (
        "<b>──────────── NIGHT LIST ────────────</b>\n"
        "Wybierz opcję:\n"
        "- 🌍 Show All: pokaż wszystkie sklepy\n"
        "- Flaga: filtruj sklepy wg kraju"
    )
    photo_path = "noc2.png"
    try:
        photo = FSInputFile(photo_path)
        await message.answer_photo(photo=photo, caption=text, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")

@dp.callback_query(lambda c: c.data == "show_all_shops")
async def show_all_shops(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    await send_shops_page(callback.message, 0)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("filter_flag_"))
async def filter_by_flag(callback: types.CallbackQuery, state: FSMContext, **kwargs):
    await callback.answer()
    flag_code = callback.data.split("_")[-1]
    await send_shops_page(callback.message, 0, filter_flag=flag_code)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "go_back")
async def go_back(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    await safe_delete(callback.message)
    # Domyślnie wraca do menu głównego
    await show_main_menu(callback)

@dp.callback_query(lambda c: c.data.startswith("shop_"))
async def show_shop_menu(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    if callback.message.chat.type != "private":
        return
    print(f"[LOG] SZCZEGÓŁY SKLEPU: {callback.from_user.id} ({callback.from_user.username}) -> {callback.data}")
    shop_id = int(callback.data.split("_")[1])
    from db import get_shop_with_random_clicks, get_ratings, get_opinions_full, increment_shop_clicks
    await increment_shop_clicks(shop_id, 3)
    shop = await get_shop_with_random_clicks(shop_id)
    if not shop:
        await callback.message.answer("Nie znaleziono sklepu.")
        return
    avg = await get_average_rating(shop_id)
    ratings = await get_ratings(shop_id)
    opinions = await get_opinions_full(shop_id)
    def valid_url(url):
        return url and (url.startswith("http://") or url.startswith("https://") or url.startswith("t.me/") or url.startswith("@"))
    def valid_url_or_mention(val):
        return val and (val.startswith("http://") or val.startswith("https://") or val.startswith("t.me/") or val.startswith("@"))

    def format_link_button(link, label, emoji=None):
        if not link:
            return None
        # Wyciągamy username lub domenę, ale nie ma to znaczenia dla etykiety
        username = None
        if link.startswith("https://t.me/"):
            username = link.split("https://t.me/")[-1].split("/")[0].split("?")[0]
        elif link.startswith("http://t.me/"):
            username = link.split("http://t.me/")[-1].split("/")[0].split("?")[0]
        elif link.startswith("t.me/"):
            username = link.split("t.me/")[-1].split("/")[0].split("?")[0]
        elif link.startswith("@"):  # czysty @nazwa
            username = link[1:].split(" ")[0].split("/")[0].split("?")[0]
        elif link.startswith("http://") or link.startswith("https://"):
            # dla www
            return {"text": f"{emoji or ''} {label}".strip(), "url": link}
        else:
            return None
        url = f"https://t.me/{username}" if username else link
        return {"text": f"{emoji or ''} {label}".strip(), "url": url}

    buttons = []
    row1 = []
    btn = format_link_button(shop.get("bot_link"), "BOT", "🤖")
    if btn:
        row1.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    btn = format_link_button(shop.get("operator_link"), "Operator", "👤")
    if btn:
        row1.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    if row1:
        buttons.append(row1)
    row2 = []
    btn = format_link_button(shop.get("chat_link"), "Chat", "💬")
    if btn:
        row2.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    btn = format_link_button(shop.get("www"), "Website", "🌐")
    if btn:
        row2.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    btn = format_link_button(shop.get("support_link"), "Support", "🛟")
    if btn:
        row2.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    btn = format_link_button(shop.get("channel_link"), "Kanał", "📢")
    if btn:
        row2.append(InlineKeyboardButton(text=btn["text"], url=btn["url"]))
    if row2:
        buttons.append(row2)
    # --- ULUBIONE ---
    fav = await is_favorite(callback.from_user.id, shop_id)
    if fav:
        buttons.append([InlineKeyboardButton(text="💔 Usuń z ulubionych", callback_data=f"unfav_{shop_id}")])
    else:
        buttons.append([InlineKeyboardButton(text="❤️ Dodaj do ulubionych", callback_data=f"fav_{shop_id}")])
    buttons.append([InlineKeyboardButton(text="😈Twoja opinia😇", callback_data=f"recenzja_{shop['id']}")])
    buttons.append([InlineKeyboardButton(text="📝 Zobacz opinie", callback_data=f"opinions_{shop['id']}")])
    bot_username = await get_bot_username()
    share_url = f"https://t.me/{bot_username}/?start=shop_{shop_id}"
    buttons.append([InlineKeyboardButton(text="🔗 Udostępnij sklep", callback_data=f"share_shop_{shop_id}")])
    shops = await get_shops()
    shop_ids = [s['id'] for s in shops]
    idx = shop_ids.index(shop_id) if shop_id in shop_ids else -1
    nav_buttons = []
    nav_buttons.append(InlineKeyboardButton(text="⬅️ Wróć", callback_data="nocna_lista"))
    nav_buttons.append(InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"))
    if idx != -1 and idx < len(shop_ids) - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️ Następny", callback_data=f"shop_{shop_ids[idx+1]}"))
    buttons.append(nav_buttons)
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    text = f"<b>{shop['shop_name']}</b>\n{shop['description']}\n\n<code>Odwiedziny: {shop['clicks']}</code>\nŚrednia ocena: <b>{avg}</b> ({len(ratings)} ocen)\nOpinie: <b>{len(opinions)}</b>"
    media_path = shop['photo'] if shop['photo'] else None
    try:
        if media_path:
            await send_shop_media(callback.message, media_path, text, reply_markup=kb)
        else:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

# Funkcja do wysyłania pliku multimedialnego (zdjęcie/gif/mp4) w szczegółach sklepu
async def send_shop_media(message, media_path, caption, reply_markup=None):
    ext = media_path.lower().split('.')[-1]
    with open(media_path, 'rb') as f:
        data = f.read()
    if ext in ["jpg", "jpeg", "png", "gif"]:
        await message.answer_photo(photo=BufferedInputFile(data, filename=media_path), caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    elif ext in ["mp4"]:
        await message.answer_video(video=BufferedInputFile(data, filename=media_path), caption=caption, reply_markup=reply_markup, parse_mode="HTML")
    else:
        await message.answer(caption, reply_markup=reply_markup, parse_mode="HTML")

# Obsługa oceniania sklepu
@dp.callback_query(lambda c: c.data.startswith("rate_"))
async def rate_shop(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="1⭐️", callback_data="review_access_1"),
        InlineKeyboardButton(text="2⭐️", callback_data="review_access_2"),
        InlineKeyboardButton(text="3⭐️", callback_data="review_access_3"),
        InlineKeyboardButton(text="4⭐️", callback_data="review_access_4"),
        InlineKeyboardButton(text="5⭐️", callback_data="review_access_5"),
    )
    shop_id = int(callback.data.split("_")[1])
    await callback.message.answer("Wybierz ocenę:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("setrate_"))
async def set_rating(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    _, shop_id, rating = callback.data.split("_")
    user_id = callback.from_user.id
    await add_rating(int(shop_id), user_id, int(rating))
    await callback.answer(f"Dziękujemy za ocenę: {rating} ⭐!", show_alert=True)

# --- ZAPISYWANIE OPINII Z IMIENIEM/NICKIEM I NOWY SPOSÓB WYŚWIETLANIA ---

@dp.callback_query(lambda c: c.data.startswith("opinions_"))
async def show_opinions(callback: types.CallbackQuery):
    await callback.answer()
    shop_id = int((callback.data or "").split("_")[-1])
    opinions = await get_opinions_full(shop_id)
    if not opinions:
        await callback.message.answer("Brak opinii dla tego sklepu.")
        await callback.answer()
        return
    kb = InlineKeyboardBuilder()
    for idx, op in enumerate(opinions):
        text_short = (op['opinion'][:15] + ("..." if len(op['opinion']) > 15 else ""))
        btn_text = f"{text_short} Czytaj Dalej >"
        kb.button(text=btn_text, callback_data=f"showop_{shop_id}_{idx}")
    kb.row(InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"shop_{shop_id}"))
    await callback.message.answer("<b>Opinie:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("showop_"))
async def show_full_opinion(callback: types.CallbackQuery):
    await callback.answer()
    _, shop_id, idx = callback.data.split("_")
    shop_id = int(shop_id)
    idx = int(idx)
    opinions = await get_opinions_full(shop_id)
    if idx < 0 or idx >= len(opinions):
        await callback.answer("Brak opinii.", show_alert=True)
        return
    op = opinions[idx]
    # Pobierz imię lub nick
    user_name = op.get('user_name') or op.get('user_username') or f"ID:{op.get('user_id')}"
    text = f"<b>Opinia użytkownika:</b> <i>{user_name}</i>\n\n{op['opinion']}"
    kb = InlineKeyboardBuilder()
    if idx > 0:
        kb.button(text="< Poprzednia", callback_data=f"showop_{shop_id}_{idx-1}")
    kb.button(text="🏠 HOME", callback_data="home_0")
    if idx < len(opinions) - 1:
        kb.button(text="Następna >", callback_data=f"showop_{shop_id}_{idx+1}")
    else:
        kb.button(text="Lista opinii", callback_data=f"opinions_{shop_id}")
    # Dodaj przycisk usuń opinię tylko dla admina
    if str(callback.from_user.id) == str(ADMIN_ID):
        kb.button(text="🗑️ Usuń opinię", callback_data=f"deleteop_{shop_id}_{op['id']}")
    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()

# Callback do usuwania opinii przez admina
@dp.callback_query(lambda c: c.data.startswith("deleteop_"))
async def delete_opinion_admin(callback: types.CallbackQuery):
    if str(callback.from_user.id) != str(ADMIN_ID):
        await callback.answer("Brak uprawnień.", show_alert=True)
        return
    _, shop_id, opinion_id = callback.data.split("_")
    from db import delete_opinion
    await delete_opinion(int(opinion_id))
    await callback.answer("Opinia została usunięta.", show_alert=True)
    # Po usunięciu wróć do listy opinii
    await show_opinions(callback)

# --- ZAPISYWANIE OPINII Z IMIENIEM/NICKIEM ---
@dp.message(lambda m: dp.get('awaiting_opinion') and dp['awaiting_opinion']['user_id'] == m.from_user.id and dp['awaiting_opinion'].get('step') == 'opinion_photo')
async def handle_opinion_photo(message: types.Message):
    op = dp['awaiting_opinion']
    photo_id = None
    # Obsługa różnych wariantów wpisania "pomiń"
    pomijane = ['pomin', 'pomijam', 'pomiń', 'pominę', 'pominąć']
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.text and message.text.lower().strip().replace('ń', 'n') in pomijane:
        photo_id = None
    else:
        await message.answer("Wyślij zdjęcie lub wpisz 'pomiń', jeśli nie chcesz dodawać zdjęcia.")
        return
    # Pobierz imię i username
    user_name = message.from_user.first_name or ""
    user_username = message.from_user.username or ""
    await add_rating(op["shop_id"], message.from_user.id, op.get("rating", 5))
    # Dodaj opinię z imieniem i username
    await add_opinion(op["shop_id"], message.from_user.id, op["opinion_text"], photo_id, user_name, user_username)
    import random
    await add_nc(message.from_user.id, random.randint(10, 20), reason="opinia")
    GROUP_ID = os.getenv("GROUP_ID")
    bot_me = await message.bot.me()
    BOT_NAME = bot_me.username
    if GROUP_ID:
        url = f"https://t.me/{BOT_NAME}?start=shop_{op['shop_id']}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Zobacz sklep", url=url)]]
        )
        await message.bot.send_message(GROUP_ID, f"🆕 Dodano nową opinię do sklepu!", reply_markup=kb)
    await message.answer("Dziękujemy za Twoją opinię i ocenę! Otrzymujesz 5 NC!")
    dp['awaiting_opinion'] = None

# Pomocnicza funkcja do bezpiecznego usuwania wiadomości (efekt znikania)
async def safe_delete(msg):
    try:
        await msg.delete()
    except Exception:
        pass

async def send_top3_to_group_and_channel():
    while True:
        await asyncio.sleep(5 * 60 * 60)  # 5 godzin w sekundach
        GROUP_ID = os.getenv("GROUP_ID")
        CHANNEL_ID = os.getenv("CHANNEL_ID")
        if not GROUP_ID and not CHANNEL_ID:
            continue
        top3, _, _, _ = await get_shops_page(0)
        if not top3:
            continue
        # Przygotuj tekst i przyciski
        text = "<b>🏆 TOP3 sklepy Nocna24:</b>\n"
        emoji = ["🥇", "🥈", "🥉"]
        bot_url = "https://t.me/nocna24_bot"
        buttons = []
        for idx, shop in enumerate(top3):
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            flag = shop.get('flag', '') or ''
            btn_text = f"{emoji[idx]}{flag} {shop['shop_name']} {int(avg)}⭐️({count})"
            text += f"{btn_text}\n"
            buttons.append([InlineKeyboardButton(text=btn_text, url=bot_url)])
        # Dodatkowy przycisk na dole
        buttons.append([InlineKeyboardButton(text="🌙 Zobacz wszystkie sklepy", url=bot_url)])
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        photo = FSInputFile("noc2.png")
        # Wysyłka tylko na kanał
        if CHANNEL_ID:
            try:
                await bot.send_photo(CHANNEL_ID, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                print(f"Błąd wysyłania TOP3 na kanał: {e}")

async def send_random_promoted_to_channel():
    import traceback
    while True:
        await asyncio.sleep(2 * 60 * 60)  # 2 godziny
        CHANNEL_ID = os.getenv("CHANNEL_ID")
        if not CHANNEL_ID:
            continue
        from db import get_promoted_shops
        shops = await get_promoted_shops()
        if not shops:
            continue
        shop = random.choice(shops)
        avg = shop.get('avg_rating', 0)
        opinions = await get_opinions(shop['id'])
        count = len(opinions)
        text = f"<b>{shop['shop_name']}</b>\n⭐️{avg} ({count} opinii)\n"
        if shop.get('description'):
            text += f"\n{shop['description']}\n"
        bot_url = "https://t.me/nocna24_bot"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=shop['shop_name'], url=bot_url)]]
        )
        photo_path = shop.get('photo') or "promo.png"
        try:
            photo = FSInputFile(photo_path)
            await send_logged_photo(CHANNEL_ID, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            print(f"[KANAL] Błąd wysyłki promowanego na kanał: {e}\n{traceback.format_exc()}")

async def send_info_announcement():
    await asyncio.sleep(20)  # 3 minuty po starcie bota
    CHANNEL_ID = os.getenv("CHANNEL_ID")
    if not CHANNEL_ID:
        return
    bot_url = "https://t.me/nocna24_bot"
    text = (
        "<b>BOT:</b> @Nocna24_Bot\n"
        "<b>Kanał Nocna Official:</b> https://t.me/+HfBnVWOy1vplNmU0\n"
        "<b>Chat:</b> https://t.me/+gbL6KkUnDhAxM2Vk"
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Przejdź do Nocnej >>>", url=bot_url)]]
    )
    photo = FSInputFile("info22.png")
    try:
        await bot.send_photo(CHANNEL_ID, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
    except Exception as e:
        print(f"[KANAL] Błąd wysyłki info22.png: {e}")
    # Powtarzaj co 3h
    while True:
        await asyncio.sleep(3 * 60 * 60)
        try:
            await bot.send_photo(CHANNEL_ID, photo=photo, caption=text, reply_markup=kb, parse_mode="HTML")
        except Exception as e:
            print(f"[KANAL] Błąd wysyłki info22.png: {e}")

async def main():
    logging.basicConfig(level=logging.WARNING)
    await init_db()
    asyncio.create_task(send_top3_to_group_and_channel())
    asyncio.create_task(send_random_promoted_to_channel())
    asyncio.create_task(send_info_announcement())
    print("[DEBUG] Bot polling started!")
    await dp.start_polling(bot)

@dp.callback_query(lambda c: c.data == "home_0")
async def go_home(callback: types.CallbackQuery, **kwargs):
    await callback.answer()
    await safe_delete(callback.message)
    await show_main_menu(callback)
    await callback.answer()

# Komenda admina do dodawania zdjęcia/gifa/mp4 do sklepu
@dp.message(Command("addphoto"))
async def cmd_addphoto(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    shops = await get_shops()
    kb = InlineKeyboardBuilder()
    row = []
    for idx, shop in enumerate(shops, 1):
        row.append(InlineKeyboardButton(text=shop['shop_name'], callback_data=f"addphoto_{shop['id']}"))
        if idx % 3 == 0:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    await message.answer("Wybierz sklep, do którego chcesz dodać zdjęcie/gif/mp4:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("addphoto_"))
async def addphoto_select(callback: types.CallbackQuery):
    await callback.answer()
    shop_id = int(callback.data.split("_")[1])
    addphoto_state[callback.from_user.id] = {"shop_id": shop_id}
    await callback.message.answer("Wyślij zdjęcie, gif lub film (mp4 do 10s) na czat.")
    await callback.answer()

@dp.message(lambda m: addphoto_state.get(m.from_user.id) and (m.photo or m.video or m.animation))
async def addphoto_receive(message: types.Message):
    print(f"[DEBUG] addphoto_receive: from_user={message.from_user.id}, photo={message.photo}, video={message.video}, animation={message.animation}")
    state = addphoto_state.get(message.from_user.id)
    if not state:
        print(f"[DEBUG] addphoto_receive: brak stanu dla użytkownika {message.from_user.id}")
        return
    shop_id = state['shop_id']
    file = None
    ext = None
    file_id = None
    if message.photo:
        file = message.photo[-1]
        ext = 'jpg'
        file_id = file.file_id
    elif message.video:
        file = message.video
        ext = 'mp4'
        file_id = file.file_id
        if hasattr(file, 'duration') and file.duration > 10:
            print(f"[DEBUG] addphoto_receive: video za długie ({file.duration}s)")
            await message.answer("⛔ Film może mieć maksymalnie 10 sekund!")
            return
    elif message.animation:
        file = message.animation
        ext = 'gif'
        file_id = file.file_id
    if file_id:
        print(f"[DEBUG] addphoto_receive: rozpoznano plik, ext={ext}, file_id={file_id}")
        file_info = await bot.get_file(file_id)
        tg_file_path = file_info.file_path
        local_file_path = f"shop_media/shop_{shop_id}.{ext}"
        await bot.download_file(tg_file_path, destination=local_file_path)
        from db import update_shop_photo
        await update_shop_photo(shop_id, local_file_path)
        await message.answer("✅ Plik został przypisany do sklepu!")
        del addphoto_state[message.from_user.id]
    else:
        print(f"[DEBUG] addphoto_receive: nie rozpoznano pliku")
        await message.answer("⛔ Nie rozpoznano pliku. Wyślij zdjęcie, gif lub mp4.")

@dp.message(Command("myid"))
async def cmd_myid(message: types.Message):
    print(f"[DEBUG] cmd_myid: from_user={message.from_user.id}")
    await message.answer(f"Twój ID: <code>{message.from_user.id}</code>", parse_mode="HTML")

@dp.message(Command("chanelid"))
async def cmd_chanelid(message: types.Message):
    print(f"[DEBUG] cmd_chanelid: from_user={message.from_user.id}, chat={message.chat}")
    if message.chat and message.chat.type in ("group", "supergroup", "channel"):
        await message.answer(f"ID tego kanału/czatu: <code>{message.chat.id}</code>", parse_mode="HTML")
    else:
        await message.answer("Ta komenda działa tylko na grupie, supergrupie lub kanale.")

# --- NOCNA SKRYNKA ---
user_chest_open = {}

@dp.callback_query(lambda c: c.data == "nocna_skrzynka")
async def open_nocna_skrzynka(callback: types.CallbackQuery):
    await callback.answer()
    now = datetime.datetime.now(ZoneInfo("Europe/Warsaw"))
    hour = now.hour
    user_id = callback.from_user.id
    user = callback.from_user
    # Admin może otwierać skrzynię bez ograniczeń czasowych i limitu dziennego
    if str(user_id) not in ADMIN_IDS:
        if not (hour >= 22 or hour < 6):
            await bot.send_message(user_id, "🎁 To nie jest odpowiednia pora na Nocną Skrzynkę!")
            await callback.answer()
            return
        today = now.date() if hour >= 6 else (now - datetime.timedelta(days=1)).date()
        last_open = await get_last_chest_open(user_id)
        if last_open == str(today):
            await bot.send_message(user_id, "🎁 Już otworzyłeś skrzynię tej nocy! Spróbuj po 22:00.")
            await callback.answer()
            return
        await set_chest_open(user_id, str(today))
    GROUP_ID = os.getenv("GROUP_ID")
    if GROUP_ID:
        mention = f"@{user.username}" if user.username else user.first_name or "Użytkownik"
        await bot.send_message(GROUP_ID, f"{mention} próbuje szczęścia otwierając nocną skrzynię!")
    import random
    # 1. Gwarantowane 5 NC
    await add_nc(user_id, 5, reason="nocna_skrzynka_gwarantowana")
    text = "Otrzymujesz <b>5 NC</b> za otwarcie skrzyni!"

    # 2. Losowa nagroda (jak dotychczas)
    roll = random.random()
    extra_text = ""
    nc = 0
    if roll < 0.05:
        nc = 15
        extra_text = f"Dodatkowo wygrałeś <b>15 NC</b>! Gratulacje!"
    elif roll < 0.12:
        nc = 10
        extra_text = f"Dodatkowo wygrałeś <b>10 NC</b>! Super!"
    elif roll < 0.22:
        nc = 5
        extra_text = f"Dodatkowo wygrałeś <b>5 NC</b>!"
    else:
        from db_targ_bonus import add_promo_bonus
        text_rewards = [
            ("💸 BONUS! Wygrałeś doładowanie 30 PLN! Skontaktuj się z @KiedysMichal.", 0.003),
            ("💸 BONUS! Wygrałeś doładowanie 20 PLN!Skontaktuj się z @KiedysMichal.", 0.005),
            ("💸 BONUS! Wygrałeś doładowanie 10 PLN! Skontaktuj się z @KiedysMichal.", 0.008),
            ("🌑 Otrzymujesz nocny cytat: 'Noc jest pełna możliwości.'", 0.25),
            ("🌙 Bonus: Twoje ogłoszenie będzie wyróżnione przez 24h!", 0.25),
            ("⭐ Otrzymujesz odznakę 'Nocny Odkrywca'! (funkcja wkrótce)", 0.25),
            ("🦉 Sowa przyniosła Ci gif! (funkcja wkrótce)", 0.15),
            ("🌌 Tajemnicza skrzynka pusta... Spróbuj jutro!", 0.087)
        ]
        r = random.random()
        acc = 0
        bonus_given = False
        for reward, prob in text_rewards:
            acc += prob
            if r < acc:
                extra_text = reward
                if "ogłoszenie będzie wyróżnione" in reward:
                    await add_promo_bonus(user_id, 1)
                    bonus_given = True
                break
        else:
            extra_text = "🌌 Tajemnicza skrzynka pusta... Spróbuj jutro!"
    if nc > 0:
        await add_nc(user_id, nc, reason="nocna_skrzynka_losowa")
        extra_text += f"\nTwoje saldo NC zostało powiększone."
    # Połącz info o gwarantowanej i losowej nagrodzie
    full_text = f"<b>🎁 Nocna Skrzynka</b>\n{text}"
    if extra_text:
        full_text += f"\n{extra_text}"
    await bot.send_message(user_id, full_text, parse_mode="HTML")
    await callback.answer()

async def send_test_notifications():
    await asyncio.sleep(10)  # Czekaj 10 sekund na start bota
    GROUP_ID = os.getenv("GROUP_ID")
    BOT_NAME = (await bot.me()).username
    if not GROUP_ID:
        print("Brak GROUP_ID w .env")
        return
    # 1. TOP3
    top3, _, _, _ = await get_shops_page(0)
    if top3:
        text = "<b>🏆 TOP3 sklepy Nocna24:</b>\n"
        for idx, shop in enumerate(top3):
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            text += f"{idx+1}. {shop['shop_name']} ⭐️{avg} ({count})\n"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🌙 Zobacz nocną listę", callback_data="nocna_lista")]]
        )
        await bot.send_message(GROUP_ID, text, reply_markup=kb, parse_mode="HTML")
    # 2. Nowa opinia z deep linkiem
    if top3:
        shop = top3[0]
        url = f"https://t.me/{BOT_NAME}?start=shop_{shop['id']}"
        kb2 = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Zobacz sklep", url=url)]]
        )
        await bot.send_message(GROUP_ID, f"🆕 Dodano nową opinię do sklepu!", reply_markup=kb2)
    # 3. Przycisk do nocnej listy
    kb3 = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🌙 Nocna lista", callback_data="nocna_lista")]]
    )
    await bot.send_message(GROUP_ID, "Testowy przycisk do nocnej listy", reply_markup=kb3)

@dp.message(Command("all"))
async def cmd_all(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Podaj treść wiadomości, np. /all Test.")
        return
    text = args[1]
    # Pobierz użytkowników z bazy
    from db import get_all_users
    users = await get_all_users()
    sent = 0
    for user in users:
        try:
            await send_logged_message(user['user_id'], text)
            sent += 1
        except Exception as e:
            print(f"[ALL] Nie wysłano do {user['user_id']}: {e}")
    await message.answer(f"Wysłano do {sent} użytkowników.")

@dp.callback_query(lambda c: c.data == "nocna_info")
async def nocna_info(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete(callback.message)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Kontakt", url="https://t.me/nocny_supp")],
            [InlineKeyboardButton(text="Kanał Nocna_Official", url="https://t.me/+HfBnVWOy1vplNmU0")],
            [InlineKeyboardButton(text="Nocna_Chat", url="https://t.me/+gbL6KkUnDhAxM2Vk")],
            [InlineKeyboardButton(text="Współpraca", url="https://t.me/nocny_supp")],
            [InlineKeyboardButton(text="Regulamin", callback_data="show_regulamin")],
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="home_0"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    try:
        photo = FSInputFile("regulamin.png")
        await callback.message.answer_photo(photo=photo, reply_markup=kb)
    except Exception:
        await callback.message.answer("Regulamin i info", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "show_regulamin")
async def show_regulamin(callback: types.CallbackQuery):
    await callback.answer()
    await safe_delete(callback.message)
    try:
        with open("bot/regulamin.txt", encoding="utf-8") as f:
            text = f.read()
    except Exception:
        text = "Brak pliku regulaminu."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="nocna_info"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    await callback.message.answer(text, reply_markup=kb)
    await callback.answer()

@dp.message(Command("testnoty"))
async def cmd_testnoty(message: types.Message):
    print(f"[DEBUG] /testnoty wywołane przez: {message.from_user.id} ({message.from_user.username})")
    group_id = os.getenv("GROUP_ID")
    bot_name = (await bot.me()).username
    if not group_id:
        await message.answer("Brak GROUP_ID w .env!")
        return
    # 1. TOP3
    top3, _, _, _ = await get_shops_page(0)
    if top3:
        text = "<b>🏆 TOP3 sklepy Nocna24:</b>\n"
        for idx, shop in enumerate(top3):
            avg = shop.get('avg_rating', 0)
            opinions = await get_opinions(shop['id'])
            count = len(opinions)
            text += f"{idx+1}. {shop['shop_name']} ⭐️{avg} ({count})\n"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="🌙 Zobacz nocną listę", callback_data="nocna_lista")]]
        )
        await bot.send_message(group_id, text, reply_markup=kb, parse_mode="HTML")
    # 2. Nowa opinia z deep linkiem
    if top3:
        shop = top3[0]
        url = f"https://t.me/{bot_name}?start=shop_{shop['id']}"
        kb2 = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Zobacz sklep", url=url)]]
        )
        await bot.send_message(group_id, f"🆕 Dodano nową opinię do sklepu!", reply_markup=kb2)
    # 3. Przycisk do nocnej listy
    kb3 = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="🌙 Nocna lista", callback_data="nocna_lista")]]
    )
    await bot.send_message(group_id, "Testowy przycisk do nocnej listy", reply_markup=kb3)
    await message.answer("Wysłano testowe powiadomienia na kanał/grupę.")

#@dp.callback_query(lambda c: c.data == "search_menu")
#async def show_search_menu(callback: types.CallbackQuery, state: FSMContext):
 #   from handlers.search import search_start  # poprawny import!
  #  await callback.answer()
  #  await search_start(callback, state)

# --- DODAWANIE NOWEGO SKLEPU: /addshop ---
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.filters import Command
from db import add_shop

class AddShopStates(StatesGroup):
    waiting_for_name = State()
    waiting_for_description = State()
    waiting_for_photo = State()
    waiting_for_bot_link = State()
    waiting_for_operator_link = State()
    waiting_for_chat_link = State()
    waiting_for_www = State()
    waiting_for_country = State()
    confirm = State()

@dp.message(Command("addshop"))
async def addshop_start(message: types.Message, state: FSMContext):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    await state.clear()
    await state.set_state(AddShopStates.waiting_for_name)
    await message.answer("Podaj nazwę sklepu:")

@dp.message(AddShopStates.waiting_for_name)
async def addshop_name(message: types.Message, state: FSMContext):
    await state.update_data(shop_name=message.text)
    await state.set_state(AddShopStates.waiting_for_description)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_description")
    await message.answer("Podaj opis sklepu lub wybierz pomiń:", reply_markup=kb.as_markup())

@dp.message(AddShopStates.waiting_for_description)
async def addshop_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await state.set_state(AddShopStates.waiting_for_photo)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_photo")
    await message.answer("Wyślij zdjęcie sklepu lub wybierz pomiń:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "addshop_skip_description")
async def addshop_skip_description(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(description=None)
    await state.set_state(AddShopStates.waiting_for_photo)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_photo")
    await callback.message.answer("Wyślij zdjęcie sklepu lub wybierz pomiń:", reply_markup=kb.as_markup())
    await callback.answer()

@dp.message(AddShopStates.waiting_for_photo, F.photo)
async def addshop_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    await state.update_data(photo_id=photo_id)
    await state.set_state(AddShopStates.waiting_for_bot_link)
    await message.answer("Podaj link do Bota:")

@dp.callback_query(lambda c: c.data == "addshop_skip_photo")
async def addshop_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(photo_id=None)
    await state.set_state(AddShopStates.waiting_for_bot_link)
    await callback.message.answer("Podaj link do Bota:")
    await callback.answer()

@dp.message(AddShopStates.waiting_for_bot_link)
async def addshop_bot_link(message: types.Message, state: FSMContext):
    await state.update_data(bot_link=message.text)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_operator_link")
    await state.set_state(AddShopStates.waiting_for_operator_link)
    await message.answer("Podaj link do operatora:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "addshop_skip_operator_link")
async def addshop_skip_operator_link(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(operator_link=None)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_chat_link")
    await state.set_state(AddShopStates.waiting_for_chat_link)
    await callback.message.answer("Podaj link do chatu:", reply_markup=kb.as_markup())

@dp.message(AddShopStates.waiting_for_operator_link)
async def addshop_operator_link(message: types.Message, state: FSMContext):
    await state.update_data(operator_link=message.text)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_chat_link")
    await state.set_state(AddShopStates.waiting_for_chat_link)
    await message.answer("Podaj link do chatu:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "addshop_skip_chat_link")
async def addshop_skip_chat_link(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(chat_link=None)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_www")
    await state.set_state(AddShopStates.waiting_for_www)
    await callback.message.answer("Podaj link do www:", reply_markup=kb.as_markup())

@dp.message(AddShopStates.waiting_for_chat_link)
async def addshop_chat_link(message: types.Message, state: FSMContext):
    await state.update_data(chat_link=message.text)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="addshop_skip_www")
    await state.set_state(AddShopStates.waiting_for_www)
    await message.answer("Podaj link do www:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "addshop_skip_www")
async def addshop_skip_www(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await state.update_data(www=None)
    await state.set_state(AddShopStates.waiting_for_country)

@dp.message(AddShopStates.waiting_for_www)
async def addshop_www(message: types.Message, state: FSMContext):
    await state.update_data(www=message.text)
    await state.set_state(AddShopStates.waiting_for_country)
    kb = InlineKeyboardBuilder()
    kb.button(text="🇵🇱 Polska", callback_data="addshop_country_PL")
    kb.button(text="🇺🇦 Ukraina", callback_data="addshop_country_UA")
    kb.button(text="🇩🇪 Niemcy", callback_data="addshop_country_DE")
    await message.answer("Podaj kraj sklepu:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("addshop_country_"))
async def addshop_country(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    country = callback.data.split("_")[-1]
    flag_map = {"PL": "🇵🇱", "UA": "🇺🇦", "DE": "🇩🇪"}
    await state.update_data(country=country, flag=flag_map.get(country, country))
    data = await state.get_data()
    text = (
        f"<b>Podsumowanie nowego sklepu:</b>\n"
        f"Nazwa: {data.get('shop_name')}\n"
        f"Opis: {data.get('description') or 'Brak'}\n"
        f"Bot: {data.get('bot_link')}\n"
        f"Operator: {data.get('operator_link')}\n"
        f"Chat: {data.get('chat_link')}\n"
        f"WWW: {data.get('www')}\n"
        f"Kraj: {flag_map.get(country, country)}"
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Dodaj sklep", callback_data="addshop_confirm")
    kb.button(text="❌ Anuluj", callback_data="addshop_cancel")
    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await state.set_state(AddShopStates.confirm)
    await callback.answer()

@dp.callback_query(lambda c: c.data == "addshop_confirm")
async def addshop_confirm(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    shop = {
        "shop_name": data.get("shop_name"),
        "description": data.get("description"),
        "photo_id": data.get("photo_id"),
        "bot_link": data.get("bot_link"),
        "operator_link": data.get("operator_link"),
        "chat_link": data.get("chat_link"),
        "www": data.get("www"),
        "flag": data.get("flag"),
        "countries": [data.get("country")],
    }
    await add_shop(shop)
    # POWIADOMIENIE NA GRUPĘ O NOWYM SKLEPIE
    import os
    GROUP_ID = os.getenv("GROUP_ID")
    if GROUP_ID:
        from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton
        bot_username = (await callback.bot.me()).username
        nightlist_url = f"https://t.me/{bot_username}?start=nightlist"
        group_kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Pokaż Night List >>>", url=nightlist_url)]
            ]
        )
        await callback.bot.send_message(
            GROUP_ID,
            f"🆕 Dodano nowy sklep! Sprawdź na Night List.",
            reply_markup=group_kb
        )
    await callback.message.answer("✅ Sklep został dodany!")
    await state.clear()
    await callback.answer()

@dp.callback_query(lambda c: c.data == "addshop_cancel")
async def addshop_cancel(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer("❌ Dodawanie sklepu anulowane.")
    await state.clear()
    await callback.answer()
# --- KONIEC /addshop ---

fallback_router = Router()

@fallback_router.message()
async def handle_other(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    print(f"[FSM DEBUG] handle_other: from_user={message.from_user.id}, text={message.text}, current_state={current_state}")
    if current_state:
        # Pozwól FSM obsłużyć wiadomość, nie przechwytuj jej tutaj
        return
    if message.text and message.text.startswith("/"):
        print(f"[DEBUG] handle_other: Komenda, przekazuję dalej")
        return
    if dp.get('awaiting_opinion') and dp['awaiting_opinion']['user_id'] == message.from_user.id and dp['awaiting_opinion'].get('step') == 'opinion_photo':
        print(f"[DEBUG] handle_other: Oczekiwano opinii, przekazuję do handlera opinii")
        return
    print(f"[DEBUG] handle_other: {message.text} | from_user: {message.from_user.id}")
    print(f"[DEBUG] handle_other: Nie-komenda, nie rozpoznano kontekstu")

# --- rejestracja routera SHOP_SEARCH ---
print("[DEBUG] Rejestracja routera SHOP_SEARCH...")
    # dp.include_router(shop_search_router)  # NIE używamy już tego routera!
print("[DEBUG] SHOP_SEARCH router zignorowany!")
print("[DEBUG] Rejestracja routera ADD_PRODUCT...")
dp.include_router(add_product_router)
dp.include_router(stats_router)
# dp.include_router(users_router)  # Usunięto, bo nie istnieje taki router
print("[DEBUG] Rejestracja routera OLX_PANEL...")
print("[DEBUG] Rejestracja routera NOCNA_OFFER...")
dp.include_router(nocna_offer_router)
print("[DEBUG] NOCNA_OFFER router registered!")
print("[DEBUG] Rejestracja routera MAIN...")
print("[DEBUG] MAIN router registered!")
print("[DEBUG] Rejestracja routera OLX...")
print("[DEBUG] OLX router registered!")
print("[DEBUG] Rejestracja routera SEARCH...")
dp.include_router(search_router)
print("[DEBUG] SEARCH router registered!")
print("[DEBUG] Rejestracja routera KASYNO...")
dp.include_router(kasyno_router)
print("[DEBUG] KASYNO router registered!")

# --- Fallback router musi być rejestrowany NA SAMYM KOŃCU, aby nie przechwytywał wiadomości FSM! ---
print("[DEBUG] Rejestracja routera FALLBACK...")
dp.include_router(fallback_router)
print("[DEBUG] FALLBACK router registered!")

@fallback_router.message()
async def handle_other(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    print(f"[FSM DEBUG] handle_other: from_user={message.from_user.id}, text={message.text}, current_state={current_state}")
    if current_state and current_state != default_state:
        print(f"[FSM DEBUG] handle_other: Użytkownik w stanie FSM ({current_state}), nie przechwytuję wiadomości.")
        return
    if message.text and message.text.startswith("/"):
        print(f"[DEBUG] handle_other: Komenda, przekazuję dalej")
        return
    if dp.get('awaiting_opinion') and dp['awaiting_opinion']['user_id'] == message.from_user.id and dp['awaiting_opinion'].get('step') == 'opinion':
        print(f"[DEBUG] handle_other: Oczekiwano opinii, przekazuję do handlera opinii")
        return
    print(f"[DEBUG] handle_other: {message.text} | from_user: {message.from_user.id}")
    print(f"[DEBUG] handle_other: Nie-komenda, nie rozpoznano kontekstu")

# --- EDYTOR ADMINA ---
editadm_state = {}

@dp.message(Command("editadm"))
async def cmd_editadm(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    shops = await get_shops()
    kb = InlineKeyboardBuilder()
    row = []
    for idx, shop in enumerate(shops, 1):
        row.append(InlineKeyboardButton(text=shop['shop_name'], callback_data=f"editadm_{shop['id']}"))
        if idx % 3 == 0:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    await message.answer("Wybierz sklep do edycji:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("editadm_") and c.data.count("_") == 1 and c.data.split("_")[1].isdigit())
async def editadm_select(callback: types.CallbackQuery):
    await callback.answer()
    shop_id = int(callback.data.split("_")[1])
    editadm_state[callback.from_user.id] = {"shop_id": shop_id}
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🖼️ Zdjęcie", callback_data="editadm_field_photo")],
            [InlineKeyboardButton(text="📝 Opis", callback_data="editadm_field_desc")],
            [InlineKeyboardButton(text="🏷️ Nazwa sklepu", callback_data="editadm_field_shop_name")],
            [InlineKeyboardButton(text="🤖 Link do bota", callback_data="editadm_field_bot")],
            [InlineKeyboardButton(text="👤 Operator", callback_data="editadm_field_operator")],
            [InlineKeyboardButton(text="💬 Chat", callback_data="editadm_field_chat")],
            [InlineKeyboardButton(text="🌐 WWW", callback_data="editadm_field_www")],
            [InlineKeyboardButton(text="🇵🇱 Flaga PL", callback_data="editadm_field_flag_PL"),
             InlineKeyboardButton(text="🇺🇦 Flaga UA", callback_data="editadm_field_flag_UA"),
             InlineKeyboardButton(text="🇩🇪 Flaga DE", callback_data="editadm_field_flag_DE")],
        ]
    )
    await callback.message.answer("Co chcesz edytować?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("editadm_field_flag_"))
async def editadm_flag_select(callback: types.CallbackQuery):
    await callback.answer()
    state = editadm_state.get(callback.from_user.id)
    if not state:
        await callback.message.answer("Brak wybranego sklepu. Zacznij od /editadm.")
        return
    shop_id = state["shop_id"]
    flag = callback.data.split("_")[-1]
    flag_map = {"PL": "🇵🇱", "UA": "🇺🇦", "DE": "🇩🇪"}
    from db import set_shop_flag
    await set_shop_flag(shop_id, flag_map.get(flag, "🇵🇱"))
    await callback.message.answer(f"✅ Flaga sklepu została ustawiona na {flag_map.get(flag, '🇵🇱')}")
    del editadm_state[callback.from_user.id]

@dp.callback_query(lambda c: c.data.startswith("editadm_field_"))
async def editadm_field_select(callback: types.CallbackQuery):
    await callback.answer()
    field = callback.data.split("_")[-1]
    state = editadm_state.get(callback.from_user.id)
    if not state:
        await callback.message.answer("Brak wybranego sklepu. Zacznij od /editadm.")
        return
    state["field"] = field
    if field == "photo":
        await callback.message.answer("Wyślij nowe zdjęcie sklepu.")
    else:
        await callback.message.answer("Wyślij nową wartość (tekst/link) dla wybranego pola.")
    await callback.answer()

@dp.message(lambda m: editadm_state.get(m.from_user.id) and editadm_state[m.from_user.id].get("field"))
async def editadm_receive(message: types.Message):
    state = editadm_state.get(message.from_user.id)
    shop_id = state["shop_id"]
    field = state["field"]
    # Mapowanie pól z callbacka na kolumny w bazie
    field_map = {
        "desc": "description",
        "bot": "bot_link",
        "operator": "operator_link",
        "chat": "chat_link",
        "www": "www",
        "shop_name": "shop_name"
    }
    if field == "photo":
        if not message.photo:
            await message.answer("Wyślij zdjęcie jako plik graficzny.")
            return
        file = message.photo[-1]
        file_info = await bot.get_file(file.file_id)
        tg_file_path = file_info.file_path
        local_file_path = f"shop_media/shop_{shop_id}.jpg"
        await bot.download_file(tg_file_path, destination=local_file_path)
        from db import update_shop_photo
        await update_shop_photo(shop_id, local_file_path)
        await message.answer("✅ Zdjęcie zaktualizowane!")
    else:
        value = message.text
        db_field = field_map.get(field)
        if not db_field:
            await message.answer("❌ Błąd: Nieprawidłowe pole do edycji!")
            del editadm_state[message.from_user.id]
            return
        from db import update_shop_field
        await update_shop_field(shop_id, db_field, value)
        await message.answer(f"✅ Pole {field} zaktualizowane!")
    del editadm_state[message.from_user.id]

# Handler do obsługi przycisku udostępniania sklepu
@dp.callback_query(F.data.startswith("share_shop_"))
async def share_shop_handler(callback: types.CallbackQuery):
    await callback.answer()
    shop_id = int(callback.data.split("_")[-1])
    bot_username = await get_bot_username()
    share_url = f"https://t.me/{bot_username}/?start=shop_{shop_id}"
    text = f"🔗 <b>Udostępnij ten sklep!</b>\nKliknij poniższy przycisk, aby przesłać link do sklepu znajomym lub na grupę."
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Otwórz sklep na Night List", url=share_url)]
        ]
    )
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

async def get_bot_username():
    me = await bot.get_me()
    return me.username


@dp.message(Command("promuj"))
async def promote_shop_cmd(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.reply("⛔ Brak uprawnień.")
        return
    # Pozwól na /promuj <id> lub reply na wiadomość z ID
    args = message.text.split(maxsplit=1)
    shop_id = None
    if len(args) > 1 and args[1].isdigit():
        shop_id = int(args[1])
    elif message.reply_to_message and message.reply_to_message.text and message.reply_to_message.text.strip().isdigit():
        shop_id = int(message.reply_to_message.text.strip())
    if not shop_id:
        await message.reply("Użyj: /promuj [ID sklepu] lub w odpowiedzi na wiadomość z ID.")
        return
    await set_shop_promoted(shop_id, True)
    await message.reply(f"Sklep {shop_id} został dodany do promowanych.")

@dp.message(Command("odpromuj"))
async def unpromote_shop_cmd(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.reply("⛔ Brak uprawnień.")
        return
    args = message.text.split(maxsplit=1)
    shop_id = None
    if len(args) > 1 and args[1].isdigit():
        shop_id = int(args[1])
    elif message.reply_to_message and message.reply_to_message.text and message.reply_to_message.text.strip().isdigit():
        shop_id = int(message.reply_to_message.text.strip())
    if not shop_id:
        await message.reply("Użyj: /odpromuj <ID sklepu> lub w odpowiedzi na wiadomość z ID.")
        return
    await set_shop_promoted(shop_id, False)
    await message.reply(f"Sklep {shop_id} został usunięty z promowanych.")

# Zamień wszystkie bot.send_message na funkcję z logowaniem
async def send_logged_message(target, *args, **kwargs):
    logging.info(f"[SEND_MESSAGE] target={target}, args={args}, kwargs={kwargs}")
    return await bot.send_message(target, *args, **kwargs)

async def send_logged_photo(target, *args, **kwargs):
    logging.info(f"[SEND_PHOTO] target={target}, args={args}, kwargs={kwargs}")
    return await bot.send_photo(target, *args, **kwargs)

@dp.callback_query(lambda c: c.data.startswith("page_"))
async def shops_pagination_handler(callback: types.CallbackQuery):
    try:
        page = int(callback.data.split("_")[1])
    except Exception:
        page = 0
    await send_shops_page(callback.message, page)
    await callback.answer()

# --- LICZNIK WIADOMOŚCI NA GRUPIE I NC ZA AKTYWNOŚĆ ---
user_message_count = {}

# --- NC ZA ZAPROSZENIE UŻYTKOWNIKA DO GRUPY ---
@dp.chat_member()
async def handle_new_member(event: types.ChatMemberUpdated):
    if event.new_chat_member.status == "member" and event.old_chat_member.status in ("left", "kicked"):
        inviter = getattr(event, 'inviter', None)
        if inviter:
            await add_nc(inviter.id, 2, reason="zaproszenie")
            try:
                await event.bot.send_message(inviter.id, "Dziękujemy za zaproszenie nowego użytkownika! Otrzymujesz 2 NC.")
            except Exception:
                pass

# --- FSM: Opinia o sklepie ---
from aiogram.fsm.state import State, StatesGroup

class OpinionStates(StatesGroup):
    waiting_for_rating = State()
    waiting_for_comment = State()
    waiting_for_photo = State()

@dp.callback_query(lambda c: c.data.startswith("rateopinion_"))
async def fsm_opinion_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    shop_id = int(callback.data.split("_")[1])
    await state.clear()
    await state.update_data(shop_id=shop_id)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="1⭐️", callback_data="review_access_1"),
        InlineKeyboardButton(text="2⭐️", callback_data="review_access_2"),
        InlineKeyboardButton(text="3⭐️", callback_data="review_access_3"),
        InlineKeyboardButton(text="4⭐️", callback_data="review_access_4"),
        InlineKeyboardButton(text="5⭐️", callback_data="review_access_5"),
    )
    kb.button(text="🏠 HOME", callback_data="home_0")
    await state.set_state(OpinionStates.waiting_for_rating)
    await callback.message.answer("Wybierz ocenę sklepu (1-5):", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fsm_setrate_"))
async def fsm_set_rating(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    parts = callback.data.split("_")
    shop_id = parts[-2]
    rating = parts[-1]
    await state.update_data(rating=int(rating))
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Wstecz", callback_data=f"fsm_back_rating_{shop_id}")
    kb.button(text="🏠 HOME", callback_data="home_0")
    await state.set_state(OpinionStates.waiting_for_comment)
    await callback.message.answer("Napisz swoją opinię o sklepie (min. 10 znaków):", reply_markup=kb.as_markup())
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fsm_back_rating_"))
async def fsm_back_rating(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
   
    shop_id = data.get("shop_id")
    kb = InlineKeyboardBuilder()
    kb.row(
    InlineKeyboardButton(text="1⭐️", callback_data="review_contact_1"),
    InlineKeyboardButton(text="2⭐️", callback_data="review_contact_2"),
    InlineKeyboardButton(text="3⭐️", callback_data="review_contact_3"),
    InlineKeyboardButton(text="4⭐️", callback_data="review_contact_4"),
    InlineKeyboardButton(text="5⭐️", callback_data="review_contact_5"),
        )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"recenzja_{shop_id}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
        InlineKeyboardButton(text="ℹ️ Info", callback_data="review_info_contact")
    )
    await state.set_state(OpinionStates.waiting_for_rating)
    await callback.message.answer("Wybierz ocenę sklepu (1-5):", reply_markup=kb.as_markup())
    await callback.answer()

@dp.message(OpinionStates.waiting_for_comment)
async def fsm_opinion_comment(message: types.Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    data = await state.get_data()
    shop_id = data.get("shop_id")
    user_id = message.from_user.id
    if len(text) < 10:
        await message.answer("Opinia musi mieć minimum 10 znaków. Napisz ją ponownie:")
        return
    # Sprawdź, czy użytkownik dodał już opinię w ciągu 24h
    if await user_opinion_last_24h(shop_id, user_id):
        await message.answer("Możesz dodać tylko 1 opinię na sklep na 24h. Spróbuj ponownie później.")
        await state.clear()
        return
    await state.update_data(comment=text)
    await state.set_state(OpinionStates.waiting_for_photo)
    kb = InlineKeyboardBuilder()
    kb.button(text="Pomiń", callback_data="fsm_skip_photo")
    kb.button(text="⬅️ Wstecz", callback_data="fsm_back_comment")
    kb.button(text="🏠 HOME", callback_data="home_0")
    await message.answer("Wyślij zdjęcie sklepu lub wybierz 'Pomiń':", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "fsm_skip_photo")
async def skip_opinion_photo(callback: types.CallbackQuery):
    op = dp.get('awaiting_opinion')
    # Jeśli nie ma aktywnej opinii, pokaż info i zdjęcie olx1.png
    if not op or op.get('step') != 'opinion_photo' or op['user_id'] != callback.from_user.id:
        try:
            photo = FSInputFile("olx1.png")
            await callback.message.answer_photo(photo=photo, caption="Brak aktywnego kroku opinii lub już pominięto.")
        except Exception:
            await callback.message.answer("Brak aktywnego kroku opinii lub już pominięto.")
        await callback.answer()
        return
    # Pobierz imię i username
    user_name = callback.from_user.first_name or ""
    user_username = callback.from_user.username or ""
    await add_rating(op["shop_id"], callback.from_user.id, op.get("rating", 5))
    await add_opinion(op["shop_id"], callback.from_user.id, op["opinion_text"], None, user_name, user_username)
    await add_nc(callback.from_user.id, 5, reason="opinia")
    GROUP_ID = os.getenv("GROUP_ID")
    bot_me = await callback.bot.me()
    BOT_NAME = bot_me.username
    if GROUP_ID:
        url = f"https://t.me/{BOT_NAME}?start=shop_{op['shop_id']}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Zobacz sklep", url=url)]]
        )
        await callback.bot.send_message(GROUP_ID, f"🆕 Dodano nową opinię do sklepu!", reply_markup=kb)
    try:
        photo = FSInputFile("olx1.png")
        await callback.message.answer_photo(photo=photo, caption="Dziękujemy za Twoją opinię i ocenę! Otrzymujesz 5 NC!")
    except Exception:
        await callback.message.answer("Dziękujemy za Twoją opinię i ocenę! Otrzymujesz 5 NC!")
    dp['awaiting_opinion'] = None
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("fsm_back_comment"))
async def fsm_back_comment(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Wstecz", callback_data=f"fsm_back_rating_")
    kb.button(text="🏠 HOME", callback_data="home_0")
    await state.set_state(OpinionStates.waiting_for_comment)
    await callback.message.answer("Napisz swoją opinię o sklepie (min. 10 znaków):", reply_markup=kb.as_markup())
    await callback.answer()

@dp.message(OpinionStates.waiting_for_photo, F.photo)
async def fsm_opinion_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    await fsm_save_opinion(message, state, photo_id=photo_id)

async def fsm_save_opinion(event, state: FSMContext, photo_id=None):
    data = await state.get_data()
    shop_id = data.get("shop_id")
    rating = data.get("rating")
    comment = data.get("comment")



    user = event.from_user
    user_name = user.first_name or ""
    user_username = user.username or ""
    await add_rating(shop_id, user.id, rating)
    await add_opinion(shop_id, user.id, comment, photo_id, user_name, user_username)
    import random
    await add_nc(user.id, random.randint(10, 20), reason="opinia")
    GROUP_ID = os.getenv("GROUP_ID")
    bot_me = await event.bot.me()
    BOT_NAME = bot_me.username
    if GROUP_ID:
        url = f"https://t.me/{BOT_NAME}?start=shop_{shop_id}"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="Zobacz sklep", url=url)]]
        )
        await event.bot.send_message(GROUP_ID, f"🆕 Dodano nową opinię do sklepu!", reply_markup=kb)
    if hasattr(event, 'answer'):
        await event.answer("Dziękujemy za Twoją opinię i ocenę! Otrzymujesz 5 NC!", show_alert=True)
    else:
        await event.reply("Dziękujemy za Twoją opinię i ocenę! Otrzymujesz 5 NC!")
    await state.clear()

# --- KONIEC FSM OPINII ---
@dp.message(Command("saldo"))
async def cmd_saldo(message: types.Message):
    nc = await get_nc(message.from_user.id)
    await message.answer(f"Twoje saldo NC: <b>{nc}</b>", parse_mode="HTML")

@dp.message(Command("addnc"))
async def cmd_addnc(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Użycie: /addnc user_id ilość")
        return
    try:
        user_id = int(args[1])
        amount = int(args[2])
    except Exception:
        await message.answer("Podaj poprawne ID i ilość, np. /addnc 123456789 10")
        return
    await add_nc(user_id, amount, reason=f"admin od {message.from_user.id}")
    await message.answer(f"✅ Dodano {amount} NC dla użytkownika {user_id}.")

@dp.message(Command("nctop"))
async def cmd_nc_top(message: types.Message):
    from db import get_nc_top
    from db import get_all_users
    top = await get_nc_top(10)
    users = {u['user_id']: u for u in await get_all_users()}
    text = "<b>🏆 TOP 10 NC:</b>\n"
    for idx, (user_id, balance) in enumerate(top, 1):
        user = users.get(user_id)
        if user:
            name = user.get('first_name') or user.get('username') or str(user_id)
        else:
            name = str(user_id)
        text += f"{idx}. <b>{name}</b>: {balance} NC\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("nchist"))
async def cmd_nc_history(message: types.Message):
    from db import get_nc_history
    history = await get_nc_history(message.from_user.id, limit=10)
    if not history:
        await message.answer("Brak historii transakcji NC.")
        return
    text = "<b>Ostatnie transakcje NC:</b>\n"
    for amount, reason, created in history:
        sign = "+" if amount > 0 else ""
        text += f"{created[:16]}: <b>{sign}{amount} NC</b> ({reason})\n"
    await message.answer(text, parse_mode="HTML")

@dp.message(Command("polec"))
async def cmd_polec(message: types.Message):
    bot_username = (await bot.me()).username
    ref_link = f"https://t.me/{bot_username}?start=ref_{message.from_user.id}"
    from db import get_referral_count
    count = await get_referral_count(message.from_user.id)
    await message.answer(f"Twój link polecający:\n{ref_link}\n\nLiczba poleconych: <b>{count}</b>", parse_mode="HTML")

@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    from db import add_referral, get_referral_count
    args = message.get_args()
    if args and args.startswith("ref_"):
        referrer_id = int(args.split("_")[1])
        referred_id = message.from_user.id
        if referrer_id != referred_id:
            # Sprawdź czy już był polecony
            count = await get_referral_count(referred_id)
            if count == 0:
                await add_referral(referrer_id, referred_id)
                await add_nc(referrer_id, 20, reason="polecenie")
                await message.answer(f"Dziękujemy za rejestrację z polecenia! {referrer_id} otrzymał 20 NC.")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="✅ WCHODZĘ", callback_data="accept_rules")]
        ]
    )
    try:
        photo = FSInputFile("nocny111.png")
        await message.answer_photo(photo=photo, reply_markup=kb)
    except Exception:
        await message.answer("Witaj!", reply_markup=kb)

# --- KONIEC FSM OPINII ---
class ReviewStates(StatesGroup):
    waiting_for_access = State()
    waiting_for_contact = State()
    waiting_for_quality = State()
    waiting_for_comment = State()
    waiting_for_photo = State()
    summary = State()

@dp.callback_query(lambda c: c.data.startswith("recenzja_"))
async def start_review(callback: types.CallbackQuery, state: FSMContext):
    shop_id = int(callback.data.split("_")[1])
    await state.set_state(ReviewStates.waiting_for_access)
    await state.update_data(shop_id=shop_id)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="1⭐️", callback_data="review_access_1"),
        InlineKeyboardButton(text="2⭐️", callback_data="review_access_2"),
        InlineKeyboardButton(text="3⭐️", callback_data="review_access_3"),
        InlineKeyboardButton(text="4⭐️", callback_data="review_access_4"),
        InlineKeyboardButton(text="5⭐️", callback_data="review_access_5"),
    )
    # NIE UŻYWAJ kb.buttons.clear() - to generator!
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"shop_{shop_id}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
        InlineKeyboardButton(text="ℹ️ Info", callback_data="review_info_access")
    )
    await callback.message.answer(
        "1️⃣ Jak oceniasz dostępność miast i produktów oferowanych przez sklep?\nWybierz odpowiednią liczbę, pamiętaj, że 1 to bardzo źle, a 5 to bardzo dobrze.",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("review_info_access"))
async def review_info_access(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Oceń dostępność produktów i miast sklepu w skali od 1 do 5, gdzie 5 to bardzo dobrze, a 1 to bardzo źle.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("review_access_"))
async def review_access(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[2])
    await state.update_data(access=rating)
    shop_id = (await state.get_data())["shop_id"]
    await state.set_state(ReviewStates.waiting_for_contact)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="1⭐️", callback_data="review_contact_1"),
        InlineKeyboardButton(text="2⭐️", callback_data="review_contact_2"),
        InlineKeyboardButton(text="3⭐️", callback_data="review_contact_3"),
        InlineKeyboardButton(text="4⭐️", callback_data="review_contact_4"),
        InlineKeyboardButton(text="5⭐️", callback_data="review_contact_5"),
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"recenzja_{shop_id}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
        InlineKeyboardButton(text="ℹ️ Info", callback_data="review_info_contact")
    )
    await callback.message.answer(
        "2️⃣ Jak oceniasz kontakt i obsługę tego sklepu?\nWybierz odpowiednią liczbę, pamiętaj, że 1 to bardzo źle, a 5 to bardzo dobrze.",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("review_info_contact"))
async def review_info_contact(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Oceń obsługę sklepu oraz kontakt ze sklepem w skali od 1 do 5, gdzie 5 to bardzo dobrze, a 1 to bardzo źle.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("review_contact_"))
async def review_contact(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[2])
    await state.update_data(contact=rating)
    shop_id = (await state.get_data())["shop_id"]
    await state.set_state(ReviewStates.waiting_for_quality)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="1⭐️", callback_data="review_quality_1"),
        InlineKeyboardButton(text="2⭐️", callback_data="review_quality_2"),
        InlineKeyboardButton(text="3⭐️", callback_data="review_quality_3"),
        InlineKeyboardButton(text="4⭐️", callback_data="review_quality_4"),
        InlineKeyboardButton(text="5⭐️", callback_data="review_quality_5"),
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"recenzja_{shop_id}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
        InlineKeyboardButton(text="ℹ️ Info", callback_data="review_info_quality")
    )
    await callback.message.answer(
        "3️⃣ Jak oceniasz jakość produktów oraz realizację/odbiór zamówienia?\nWybierz odpowiednią liczbę, pamiętaj, że 1 to bardzo źle, a 5 to bardzo dobrze.",
        reply_markup=kb.as_markup()
    )

@dp.callback_query(lambda c: c.data.startswith("review_info_quality"))
async def review_info_quality(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer("Oceń jakość produktów oraz realizację/odbiór zamówienia w skali od 1 do 5, gdzie 5 to bardzo dobrze, a 1 to bardzo źle.", show_alert=True)

@dp.callback_query(lambda c: c.data.startswith("review_quality_"))
async def review_quality(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[2])
    await state.update_data(quality=rating)
    shop_id = (await state.get_data())["shop_id"]
    await state.set_state(ReviewStates.waiting_for_comment)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Pomiń", callback_data="review_skip_comment"),
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="review_contact_{shop_id}"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Napisz komentarz do recenzji (opcjonalnie, min. 10 znaków) lub wybierz 'Pomiń':", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "review_skip_comment")
async def review_skip_comment(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(comment=None)
    await state.set_state(ReviewStates.waiting_for_photo)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Pomiń", callback_data="review_skip_photo"),
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="review_back_comment"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Wyślij zdjęcie (opcjonalnie) lub wybierz 'Pomiń':", reply_markup=kb.as_markup())

@dp.message(ReviewStates.waiting_for_comment)
async def review_comment(message: types.Message, state: FSMContext):
    text = message.text.strip() if message.text else ""
    if text and len(text) < 10:
        await message.answer("Komentarz musi mieć minimum 10 znaków lub wybierz 'Pomiń'.")
        return
    await state.update_data(comment=text)
    await state.set_state(ReviewStates.waiting_for_photo)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Pomiń", callback_data="review_skip_photo"),
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="review_back_comment"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await message.answer("Wyślij zdjęcie (opcjonalnie) lub wybierz 'Pomiń':", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data == "review_skip_photo")
async def review_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(photo_id=None)
    await show_review_summary(callback.message, state)
    await state.set_state(ReviewStates.summary)
    await callback.answer()

@dp.message(ReviewStates.waiting_for_photo, F.photo)
async def review_photo(message: types.Message, state: FSMContext):
    photo_id = message.photo[-1].file_id if message.photo else None
    await state.update_data(photo_id=photo_id)
    await show_review_summary(message, state)
    await state.set_state(ReviewStates.summary)

async def show_review_summary(message, state):
    from db import add_opinion, user_opinion_last_24h
    data = await state.get_data()
    shop_id = data.get("shop_id")
    user_id = message.from_user.id
    # Blokada 24h
    if await user_opinion_last_24h(shop_id, user_id):
        await message.answer("Możesz wystawić recenzję temu sklepowi tylko raz na 24h. Spróbuj ponownie później.")
        await state.clear()
        return
    access = data.get("access", 0)
    contact = data.get("contact", 0)
    quality = data.get("quality", 0)
    comment = data.get("comment")
    photo_id = data.get("photo_id")
    # Wylicz średnią
    avg = round((access + contact + quality) / 3, 2)
    user = message.from_user
    user_name = user.first_name or ""
    user_username = user.username or ""
    # Zapisz recenzję jako tekst: oceny, komentarz, średnia
    review_text = f"Dostępność: {access}/5\nObsługa: {contact}/5\nJakość: {quality}/5\nŚrednia: {avg}/5"
    if comment:
        review_text += f"\nKomentarz: {comment}"
    await add_opinion(shop_id, user_id, review_text, photo_id, user_name, user_username)
    await message.answer(f"Dziękujemy za recenzję!\nTwoja średnia ocena: <b>{avg}/5</b>", parse_mode="HTML")
    await state.clear()

# --- UNIWERSALNE SZUKAJ ---
import os
import importlib
from aiogram.fsm.state import State, StatesGroup

class SearchAllStates(StatesGroup):
    waiting_for_city = State()
    waiting_for_phrase = State()

def load_all_products():
    folder = "produkty_sklepy"
    all_products = {}
    for fname in os.listdir(folder):
        if fname.endswith(".py") and fname.startswith("produkty_") and fname != "__init__.py":
            modulename = fname[:-3]
            module = importlib.import_module(f"produkty_sklepy.{modulename}")
            produkty = getattr(module, modulename)
            all_products[modulename] = produkty
    return all_products


@dp.callback_query(lambda c: c.data.startswith("search_menu"))
async def search_menu_start(callback: types.CallbackQuery, state: FSMContext):
    # Paginacja miast: 2 kolumny po 12 miast (24 na stronę)
    all_products = load_all_products()
    miasta_set = set()
    for produkty in all_products.values():
        miasta_set.update(produkty.keys())
    miasta = sorted(miasta_set)
    # Paginacja
    data = callback.data.split(":")
    page = int(data[1]) if len(data) > 1 and data[1].isdigit() else 0
    per_page = 24
    start = page * per_page
    end = start + per_page
    miasta_page = miasta[start:end]
    kb = InlineKeyboardBuilder()
    # Dodajemy miasta w 2 kolumnach
    for i in range(0, len(miasta_page), 2):
        row = []
        row.append(InlineKeyboardButton(text=miasta_page[i], callback_data=f"search_all_city_{miasta_page[i]}"))
        if i+1 < len(miasta_page):
            row.append(InlineKeyboardButton(text=miasta_page[i+1], callback_data=f"search_all_city_{miasta_page[i+1]}"))
        kb.row(*row)
    # Paginacja: przyciski Dalej/Wstecz
    pag_buttons = []
    if page > 0:
        pag_buttons.append(InlineKeyboardButton(text="⬅️ Wstecz", callback_data=f"search_menu:{page-1}"))
    if end < len(miasta):
        pag_buttons.append(InlineKeyboardButton(text="Dalej ➡️", callback_data=f"search_menu:{page+1}"))
    if pag_buttons:
        kb.row(*pag_buttons)
    await state.set_state(SearchAllStates.waiting_for_city)
    await callback.message.answer("Wybierz miasto:", reply_markup=kb.as_markup())

@dp.callback_query(lambda c: c.data.startswith("search_all_city_"))
async def search_city_selected(callback: types.CallbackQuery, state: FSMContext):
    miasto = callback.data.split("search_all_city_")[1]
    await state.update_data(miasto=miasto)
    await state.set_state(SearchAllStates.waiting_for_phrase)
    await callback.message.answer(f"Wybrane miasto: {miasto}\nWpisz frazę do wyszukania:")

@dp.message(SearchAllStates.waiting_for_phrase)
async def search_phrase_entered(message: types.Message, state: FSMContext):
    data = await state.get_data()
    miasto = data["miasto"]
    fraza = message.text.strip().lower()
    frazy = [f for f in fraza.replace(",", " ").split() if f]
    all_products = load_all_products()
    results = []
    for sklep, produkty in all_products.items():
        produkty_miasto = produkty.get(miasto, [])
        for p in produkty_miasto:
            nazwa = p["name"].lower()
            # Produkt pasuje jeśli każde słowo z frazy występuje w nazwie
            if all(f in nazwa for f in frazy):
                results.append((sklep.replace("produkty_", "").capitalize(), sklep, p))
    if results:
        for sklep_nazwa, sklep_modul, p in results:
            bot_username = (await message.bot.me()).username
            nightlist_url = f"https://t.me/{bot_username}?start={sklep_modul}"
            text = f"[{sklep_nazwa}] {p['name']} {p['variant']} {p['price']}"
            kb = InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="Otwórz sklep na Night List", url=nightlist_url)]]
            )
            await message.answer(text, reply_markup=kb)
    else:
        await message.answer("Brak wyników.")
    await state.clear()


# Komenda /fp dla operatorów: przypina wiadomość z powiadomieniem wszystkich, po kilku sekundach odpina
@dp.message(Command("fp"))
async def cmd_fp(message: types.Message):
    # Sprawdź czy operator
    if not is_operator_user(message.from_user):
        await message.answer("⛔ Komenda tylko dla operatorów.")
        return
    # Pozwól przejść dalej tylko jeśli to komenda /start (obsłużona niżej)
    if message.text and message.text.startswith("/start"):
        return
    from db import is_banned
    if await is_banned(message.from_user.id):
        await message.answer("⛔ Twoje konto zostało zablokowane przez administrację. Nie możesz korzystać z usług bota Nocna24. W razie pomyłki napisz do @KiedysMichal.")
        return
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Użycie: /fp <treść>")
        return
    text = args[1]
    # Wyślij wiadomość z powiadomieniem wszystkich
    sent = await message.answer(f"{text}\n@everyone")
    try:
        await message.bot.pin_chat_message(chat_id=message.chat.id, message_id=sent.message_id, disable_notification=False)
        await asyncio.sleep(5)  # czas przypięcia w sekundach
        await message.bot.unpin_chat_message(chat_id=message.chat.id, message_id=sent.message_id)
    except Exception as e:
        await message.answer(f"Błąd przy przypinaniu/odpinaniu: {e}")

# --- KOMENDA TŁUMACZA PL <-> UA ---
from aiogram.filters import Command

def detect_lang(text):
    # Bardzo uproszczone wykrywanie (możesz rozbudować)
    uk_chars = set("іїєґІЇЄҐ")
    pl_chars = set("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ")
    if any(c in text for c in uk_chars):
        return "uk"
    if any(c in text for c in pl_chars):
        return "pl"
    # domyślnie pl
    return "pl"

@dp.message(Command("tl"))
async def cmd_tlumacz(message: types.Message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        await message.answer("Użycie: /tl <tekst do przetłumaczenia>")
        return
    text = args[1]
    src = detect_lang(text)
    tgt = "uk" if src == "pl" else "pl"
    try:
        resp = requests.post("https://libretranslate.com/translate", json={
            "q": text,
            "source": src,
            "target": tgt
        }, timeout=10)
        data = resp.json()
        translated = data.get("translatedText")
        if translated:
            await message.answer(f"<b>Tłumaczenie ({src} → {tgt}):</b>\n{translated}", parse_mode="HTML")
        else:
            await message.answer("Błąd tłumaczenia lub brak wyniku.")
    except Exception as e:
        await message.answer(f"Błąd podczas tłumaczenia: {e}")

#########################
# SYSTEM RANG: OPERATOR #
#########################
# Lista operatorów (user_id jako int lub username jako str)
import json
OPERATORS = set()
OPERATORS_FILE = "operators_list.json"

def save_operators_to_file():
    data = []
    for op in OPERATORS:
        if isinstance(op, int):
            data.append({"user_id": op})
        elif isinstance(op, str) and op.startswith("@"): 
            data.append({"username": op})
    with open(OPERATORS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_operators_from_file():
    try:
        with open(OPERATORS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        ops = set()
        for entry in data:
            if "user_id" in entry:
                ops.add(int(entry["user_id"]))
            elif "username" in entry:
                ops.add(entry["username"].lower())
        return ops
    except Exception:
        return set()

OPERATORS.update(load_operators_from_file())

# Komenda do dodawania operatora przez ID lub @nazwa
@dp.message(Command("addopr"))
async def cmd_addopr(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Użycie: /addopr <user_id lub @nazwa>")
        return
    ident = args[1]
    if ident.startswith("@"):  # dodaj po username
        OPERATORS.add(ident.lower())
        save_operators_to_file()
        await message.answer(f"Dodano operatora: {ident}")
    elif ident.isdigit():
        OPERATORS.add(int(ident))
        save_operators_to_file()
        await message.answer(f"Dodano operatora: {ident}")
    else:
        await message.answer("Podaj user_id (liczba) lub @nazwa.")

# Komenda do usuwania operatora
@dp.message(Command("delopr"))
async def cmd_delopr(message: types.Message):
    args = message.text.split()
    if len(args) < 2:
        await message.answer("Użycie: /delopr <user_id lub @nazwa>")
        return
    ident = args[1]
    if ident.startswith("@"):  # usuń po username
        OPERATORS.discard(ident.lower())
        save_operators_to_file()
        await message.answer(f"Usunięto operatora: {ident}")
    elif ident.isdigit():
        OPERATORS.discard(int(ident))
        save_operators_to_file()
        await message.answer(f"Usunięto operatora: {ident}")
    else:
        await message.answer("Podaj user_id (liczba) lub @nazwa.")

# Komenda /opr - wyświetla listę operatorów
from aiogram.filters import Command
@dp.message(Command("opr"))
async def cmd_opr(message: types.Message):
    if not OPERATORS:
        await message.answer("Brak operatorów.")
        return
    text = "<b>Lista Operatorów:</b>\n"
    for op in OPERATORS:
        try:
            if isinstance(op, int):
                user = await message.bot.get_chat(op)
                uname = user.username or user.full_name or str(op)
                text += f"<b>[OPERATOR]</b> <a href='tg://user?id={op}'>{uname}</a>\n"
            elif isinstance(op, str) and op.startswith("@"):  # username z @
                text += f"<b>[OPERATOR]</b> <a href='https://t.me/{op[1:]}'>{op}</a>\n"
            else:
                text += f"<b>[OPERATOR]</b> {op}\n"
        except Exception:
            text += f"<b>[OPERATOR]</b> {op}\n"
    await message.answer(text, parse_mode="HTML")

# Funkcja do pobierania prefixu rangi do dowolnej odpowiedzi
def get_user_rank_prefix(user):
    if is_operator_user(user):
        return "<b>[OPERATOR]</b> "
    return ""
def callback_item_wrapper(handler):
    async def wrapper(callback: types.CallbackQuery, *args, **kwargs):
        await try_give_random_item(callback.from_user.id, callback)
        return await handler(callback, *args, **kwargs)
    return wrapper
from promoted_ads import promoted_ads_loop
async def on_startup(dispatcher):
    # ...inne zadania startowe...
    asyncio.create_task(promoted_ads_loop(bot))

# --- PRZYPISYWANIE OPERATORA DO SKLEPU ---
import json

# Tabela operator_shop: operator_id (user_id lub username), shop_id
def init_operator_shop_db():
    with _OPERATORS_DB_LOCK:
        conn = sqlite3.connect(_OPERATORS_DB_PATH)
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS operator_shop (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operator TEXT,
                shop_id INTEGER
            )
        """)
        conn.commit()
        conn.close()

def assign_operator_to_shop(operator, shop_id):
    with _OPERATORS_DB_LOCK:
        conn = sqlite3.connect(_OPERATORS_DB_PATH)
        c = conn.cursor()
        c.execute("INSERT INTO operator_shop (operator, shop_id) VALUES (?, ?)", (str(operator), int(shop_id)))
        conn.commit()
        conn.close()

def get_operators_for_shop(shop_id):
    with _OPERATORS_DB_LOCK:
        conn = sqlite3.connect(_OPERATORS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT operator FROM operator_shop WHERE shop_id = ?", (int(shop_id),))
        rows = c.fetchall()
        conn.close()
    return [row[0] for row in rows]

def get_shops_for_operator(operator):
    with _OPERATORS_DB_LOCK:
        conn = sqlite3.connect(_OPERATORS_DB_PATH)
        c = conn.cursor()
        c.execute("SELECT shop_id FROM operator_shop WHERE operator = ?", (str(operator),))
        rows = c.fetchall()
        conn.close()
    return [row[0] for row in rows]

def remove_operator_from_shop(operator, shop_id):
    with _OPERATORS_DB_LOCK:
        conn = sqlite3.connect(_OPERATORS_DB_PATH)
        c = conn.cursor()
        c.execute("DELETE FROM operator_shop WHERE operator = ? AND shop_id = ?", (str(operator), int(shop_id)))
        conn.commit()
        conn.close()

# Inicjalizacja tabeli operator_shop
init_operator_shop_db()

# Komenda /shop_opr dla admina: wybierz operatora, potem sklep, przypisz
from aiogram.utils.keyboard import InlineKeyboardMarkup, InlineKeyboardButton

@dp.message(Command("shop_opr"))
async def cmd_shop_opr(message: types.Message):
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    # Lista operatorów
    if not OPERATORS:
        await message.answer("Brak operatorów do przypisania.")
        return
    kb = InlineKeyboardMarkup()
    for op in OPERATORS:
        if isinstance(op, int):
            label = f"ID: {op}"
            data = f"shopopr_op_{op}"
        else:
            label = op
            data = f"shopopr_op_{op}"
        kb.add(InlineKeyboardButton(text=label, callback_data=data))
    await message.answer("Wybierz operatora do przypisania do sklepu:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("shopopr_op_"))
async def shopopr_select_operator(callback: types.CallbackQuery):
    op = callback.data[len("shopopr_op_"):]
    # Pokaż listę sklepów
    from db import get_shops
    shops = await get_shops()
    kb = InlineKeyboardMarkup()
    for shop in shops:
        label = shop['shop_name']
        data = f"shopopr_assign_{op}_{shop['id']}"
        kb.add(InlineKeyboardButton(text=label, callback_data=data))
    await callback.message.answer(f"Wybierz sklep do przypisania operatora <b>{op}</b>:", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("shopopr_assign_"))
async def shopopr_assign(callback: types.CallbackQuery):
    _, _, op, shop_id = callback.data.split("_", 3)
    assign_operator_to_shop(op, shop_id)
    await callback.message.answer(f"✅ Operator <b>{op}</b> został przypisany do sklepu ID <b>{shop_id}</b>.", parse_mode="HTML")
    await callback.answer()

# Komenda /operatormenu dla operatora: lista sklepów, wybierz sklep, edytuj opis/linki
@dp.message(Command("operatormenu"))
async def cmd_operatormenu(message: types.Message):
    # Sprawdź czy operator
    op = message.from_user.id
    op_username = message.from_user.username
    op_keys = [str(op)]
    if op_username:
        op_keys.append("@" + op_username.lower())
    # Pobierz sklepy operatora
    shops = set()
    for key in op_keys:
        shops.update(get_shops_for_operator(key))
    if not shops:
        await message.answer("Nie jesteś przypisany do żadnego sklepu.")
        return
    from db import get_shops
    all_shops = await get_shops()
    shop_map = {str(shop['id']): shop for shop in all_shops}
    kb = InlineKeyboardMarkup()
    for shop_id in shops:
        shop = shop_map.get(str(shop_id))
        if shop:
            kb.add(InlineKeyboardButton(text=shop['shop_name'], callback_data=f"oprmenu_edit_{shop_id}"))
    await message.answer("Wybierz sklep do edycji:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("oprmenu_edit_"))
async def oprmenu_edit(callback: types.CallbackQuery):
    shop_id = int(callback.data.split("_")[-1])
    # Pokaż menu edycji: opis, linki
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="📝 Edytuj opis", callback_data=f"oprmenu_field_desc_{shop_id}")],
            [InlineKeyboardButton(text="🤖 Edytuj link do bota", callback_data=f"oprmenu_field_bot_{shop_id}")],
            [InlineKeyboardButton(text="💬 Edytuj link do chatu", callback_data=f"oprmenu_field_chat_{shop_id}")],
            [InlineKeyboardButton(text="🌐 Edytuj WWW", callback_data=f"oprmenu_field_www_{shop_id}")],
        ]
    )
    await callback.message.answer("Co chcesz edytować?", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("oprmenu_field_"))
async def oprmenu_field_select(callback: types.CallbackQuery):
    parts = callback.data.split("_")
    field = parts[2]
    shop_id = int(parts[3])
    # Zapisz w tymczasowym stanie użytkownika co edytuje
    if not hasattr(callback.bot, "oprmenu_state"):
        callback.bot.oprmenu_state = {}
    callback.bot.oprmenu_state[callback.from_user.id] = {"shop_id": shop_id, "field": field}
    await callback.message.answer("Wyślij nową wartość (tekst/link) dla wybranego pola.")
    await callback.answer()

@dp.message(lambda m: hasattr(m.bot, "oprmenu_state") and m.from_user.id in m.bot.oprmenu_state)
async def oprmenu_receive(message: types.Message):
    state = message.bot.oprmenu_state.get(message.from_user.id)
    shop_id = state["shop_id"]
    field = state["field"]
    # Mapowanie pól na kolumny w bazie
    field_map = {
        "desc": "description",
        "bot": "bot_link",
        "chat": "chat_link",
        "www": "www"
    }
    db_field = field_map.get(field)
    if not db_field:
        await message.answer("❌ Błąd: Nieprawidłowe pole do edycji!")
        del message.bot.oprmenu_state[message.from_user.id]
        return
    from db import update_shop_field
    await update_shop_field(shop_id, db_field, message.text)
    await message.answer(f"✅ Pole {field} zaktualizowane!")
    del message.bot.oprmenu_state[message.from_user.id]

if __name__ == "__main__":
    import asyncio
    print("[DEBUG] Startuję main loop...")
    asyncio.run(main())

@dp.message()
async def block_banned_and_give_item(message: types.Message):
    # Logowanie wszystkich wiadomości z grupy do pliku .txt
    if message.chat and message.chat.type in ("group", "supergroup"):
        try:
            with open("chest_log.txt", "a", encoding="utf-8") as f:
                f.write(f"{message.date} | {message.chat.id} | {message.from_user.id} | {message.from_user.username or '-'} | {message.text or ''}\n")
        except Exception as e:
            print(f"[LOG ERROR] Nie można zapisać do chest_log.txt: {e}")
        # Automatyczne wyróżnienie operatora
        is_operator = (message.from_user.id in OPERATORS) or \
            (message.from_user.username and ("@" + message.from_user.username.lower()) in OPERATORS)
        if is_operator:
            prefix = "[Opr] "
            uname = message.from_user.username or message.from_user.full_name or str(message.from_user.id)
            await message.reply(f"{prefix}{uname}: {message.text}")
        # Dla grup: losuj przedmiot
        await try_give_random_item(message.from_user.id, message)
        return
    # Pozwól przejść dalej tylko jeśli to komenda /start (obsłużona niżej)
    if message.text and message.text.startswith("/start"):
        return
    from db import is_banned
    if await is_banned(message.from_user.id):
        await message.answer("⛔ Twoje konto zostało zablokowane przez administrację. Nie możesz korzystać z usług bota Nocna24. W razie pomyłki napisz do @KiedysMichal.")
        return
    # Losuj przedmiot w priv
    await try_give_random_item(message.from_user.id, message)
