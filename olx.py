
import os
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command
from db import add_olx_ad, get_olx_ads, count_olx_ads, get_user_olx_ads, delete_olx_ad, update_olx_ad, set_olx_ad_sold
from admin_utils import safe_delete

print("[DEBUG] OLX router loaded!")

OLX_ADS_PER_PAGE = 5
olx_router = Router()

from aiogram.filters import Command

# TESTOWY HANDLER - sprawdza czy router OLX przechwytuje jakiekolwiek wiadomości
@olx_router.message()
async def olx_test_any_message(message: types.Message, state: FSMContext):
    print(f"[OLX DEBUG] olx_router.message() ANY: {message.text}, state={await state.get_state()}")
    # Nie odpowiadaj użytkownikowi, tylko loguj
    current_state = await state.get_state()
    if current_state:
        print(f"[OLX DEBUG] olx_test_any_message: użytkownik w stanie FSM, nie przechwytuję wiadomości")

# TEST FSM: sprawdzenie czy FSM działa w Twoim bocie
from aiogram.fsm.state import State, StatesGroup

class TestFSMStates(StatesGroup):
    waiting_for_test = State()

@olx_router.message(Command("testfsm"))
async def testfsm_start(message: types.Message, state: FSMContext):
    await message.answer("Podaj dowolny tekst (test FSM):")
    await state.set_state(TestFSMStates.waiting_for_test)

@olx_router.message(TestFSMStates.waiting_for_test)
async def testfsm_waiting(message: types.Message, state: FSMContext):
    await message.answer(f"Odebrano: {message.text}\nFSM DZIAŁA! (stan: {await state.get_state()})")
    await state.clear()

class AddAdStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()

class EditAdStates(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()

# Menu główne OLX
@olx_router.message(Command("olx"))
async def olx_menu(message: types.Message):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dodaj ogłoszenie", callback_data="olx_add")],
            [InlineKeyboardButton(text="Przeglądaj ogłoszenia", callback_data="olx_list_0")],
            [InlineKeyboardButton(text="Moje ogłoszenia", callback_data="olx_my")],
        ]
    )
    await message.answer("<b>Nocny_OLX</b>\nWybierz opcję:", reply_markup=kb, parse_mode="HTML")

# Dodawanie ogłoszenia
@olx_router.callback_query(F.data == "olx_add")
async def olx_add_start(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    print(f"[DEBUG] olx_add_start: Ustawiamy stan AddAdStates.waiting_for_title dla usera {callback.from_user.id}")
    await callback.bot.send_message(callback.from_user.id, "Podaj tytuł ogłoszenia:")
    await state.set_state(AddAdStates.waiting_for_title)
    print(f"[DEBUG] olx_add_start: state po set_state = {await state.get_state()} dla usera {callback.from_user.id}")
    await callback.answer()

@olx_router.callback_query(F.data == "olx_cancel")
async def olx_cancel(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dodaj ogłoszenie", callback_data="olx_add")],
            [InlineKeyboardButton(text="Przeglądaj ogłoszenia", callback_data="olx_list_0")],
            [InlineKeyboardButton(text="Moje ogłoszenia", callback_data="olx_my")],
        ]
    )
    await callback.message.answer("Dodawanie ogłoszenia anulowane.\n<b>Nocny_OLX</b>\nWybierz opcję:", reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@olx_router.callback_query(F.data == "olx_back_title")
async def olx_back_title(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.set_state(AddAdStates.waiting_for_title)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")]
        ]
    )
    await callback.message.answer("Podaj tytuł ogłoszenia:", reply_markup=kb)
    await callback.answer()

@olx_router.callback_query(F.data == "olx_back_desc")
async def olx_back_desc(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.set_state(AddAdStates.waiting_for_description)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Wstecz", callback_data="olx_back_title")],
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")]
        ]
    )
    await callback.message.answer("Podaj opis przedmiotu:", reply_markup=kb)
    await callback.answer()

@olx_router.callback_query(F.data == "olx_back_price")
async def olx_back_price(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.set_state(AddAdStates.waiting_for_price)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Wstecz", callback_data="olx_back_desc")],
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")]
        ]
    )
    await callback.message.answer("Podaj cenę (PLN):", reply_markup=kb)
    await callback.answer()

@olx_router.callback_query(F.data == "olx_back_photo")
async def olx_back_photo(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.set_state(AddAdStates.waiting_for_photo)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Wstecz", callback_data="olx_back_price")],
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")],
            [InlineKeyboardButton(text="Pomiń", callback_data="olx_skip_photo")]
        ]
    )
    await callback.message.answer("Wyślij zdjęcie przedmiotu lub pomiń:", reply_markup=kb)
    await callback.answer()

@olx_router.callback_query(F.data == "olx_skip_photo")
async def olx_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    data = await state.get_data()
    # Dodaj domyślne wartości dla brakujących pól
    location = data.get("location", "")
    delivery_method = data.get("delivery_method", "")
    await add_olx_ad(
        user_id=callback.from_user.id,
        username=callback.from_user.username or str(callback.from_user.id),
        title=data["title"],
        description=data["description"],
        price=data["price"],
        location=location,
        delivery_method=delivery_method,
        photo_id=None
    )
    # Przyznaj 5 NC za ogłoszenie
    from db import add_nc
    await add_nc(callback.from_user.id, 5, reason="ogloszenie")
    await callback.message.answer("Twoje ogłoszenie zostało dodane!")
    await state.clear()
    await callback.answer()

# Modyfikacja istniejących handlerów FSM:
@olx_router.message(AddAdStates.waiting_for_title, flags={"block": False})
async def olx_add_title(message: types.Message, state: FSMContext):
    """
    Handler FSM: OLX - podanie tytułu ogłoszenia
    Stan: AddAdStates.waiting_for_title
    """
    print(f"[OLX DEBUG] olx_add_title handler WYWOŁANY! from_user={message.from_user.id}, text={message.text}, state={await state.get_state()}")
    current_state = await state.get_state()
    if current_state != AddAdStates.waiting_for_title.state:
        print(f"[OLX DEBUG] olx_add_title: stan NIEZGODNY! current_state={current_state}, oczekiwany={AddAdStates.waiting_for_title.state}")
        return
    else:
        print(f"[OLX DEBUG] olx_add_title: stan ZGODNY!")

    title = message.text.strip() if message.text else None
    if not title or len(title) < 3:
        await message.answer("Tytuł ogłoszenia musi mieć minimum 3 znaki. Podaj tytuł jeszcze raz:")
        return

    await state.update_data(title=title)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")]
        ]
    )
    await message.answer("Podaj opis przedmiotu:", reply_markup=kb)
    await state.set_state(AddAdStates.waiting_for_description)
    print(f"[OLX DEBUG] olx_add_title: state po set_state = {await state.get_state()} dla usera {message.from_user.id}")

@olx_router.message(AddAdStates.waiting_for_description, flags={"block": False})
async def olx_add_description(message: types.Message, state: FSMContext):
    print(f"[OLX DEBUG] Użytkownik {message.from_user.id} podaje opis: {message.text}")
    description = message.text.strip() if message.text else None
    if not description or len(description) < 5:
        await message.answer("Opis ogłoszenia musi mieć minimum 5 znaków. Podaj opis jeszcze raz:")
        return
    await state.update_data(description=description)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Wstecz", callback_data="olx_back_title")],
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")]
        ]
    )
    await message.answer("Podaj cenę (PLN):", reply_markup=kb)
    await state.set_state(AddAdStates.waiting_for_price)

@olx_router.message(AddAdStates.waiting_for_price, flags={"block": False})
async def olx_add_price(message: types.Message, state: FSMContext):
    print(f"[OLX DEBUG] Użytkownik {message.from_user.id} podaje cenę: {message.text}")
    price = message.text.strip() if message.text else None
    if not price or not price.replace(",", ".").replace(".", "", 1).isdigit():
        await message.answer("Podaj poprawną cenę (liczba, np. 99.99):")
        return
    await state.update_data(price=price)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Wstecz", callback_data="olx_back_desc")],
            [InlineKeyboardButton(text="Anuluj", callback_data="olx_cancel")],
            [InlineKeyboardButton(text="Pomiń", callback_data="olx_skip_photo")]
        ]
    )
    await message.answer("Wyślij zdjęcie przedmiotu lub pomiń:", reply_markup=kb)
    await state.set_state(AddAdStates.waiting_for_photo)

@olx_router.message(AddAdStates.waiting_for_photo, flags={"block": False})
async def olx_add_photo(message: types.Message, state: FSMContext):
    print(f"[OLX DEBUG] Użytkownik {message.from_user.id} wysyła zdjęcie lub plik: {bool(message.photo)}, dokument: {bool(message.document)}")
    data = await state.get_data()
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    elif message.document and message.document.mime_type.startswith("image/"):
        photo_id = message.document.file_id
    else:
        await message.answer("Wyślij zdjęcie jako zdjęcie lub plik graficzny.")
        return
    # Dodaj domyślne wartości dla brakujących pól
    location = data.get("location", "")
    delivery_method = data.get("delivery_method", "")
    await add_olx_ad(
        user_id=message.from_user.id,
        username=message.from_user.username or str(message.from_user.id),
        title=data["title"],
        description=data["description"],
        price=data["price"],
        location=location,
        delivery_method=delivery_method,
        photo_id=photo_id
    )
    # Przyznaj 5 NC za ogłoszenie
    from db import add_nc
    await add_nc(message.from_user.id, 5, reason="ogloszenie")
    await message.answer("Twoje ogłoszenie zostało dodane!")
    # Powiadomienie na grupę o nowym ogłoszeniu
    import os
    GROUP_ID = os.getenv("GROUP_ID")
    if GROUP_ID:
        text = f"🛒 Nowe ogłoszenie w Nocny_OLX!\n<b>{data['title']}</b>\n{data['description']}\nCena: <b>{data['price']} PLN</b>"
        if photo_id:
            await message.bot.send_photo(GROUP_ID, photo=photo_id, caption=text, parse_mode="HTML")
        else:
            await message.bot.send_photo(GROUP_ID, photo=FSInputFile('olx1.png'), caption=text, parse_mode="HTML")
    await state.clear()

# Przeglądanie ogłoszeń (paginacja)
@olx_router.callback_query(F.data.startswith("olx_list_"))
async def olx_list(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    if not callback.from_user:
        await callback.answer("Brak danych użytkownika", show_alert=True)
        return
    page = int((callback.data or "").split("_")[-1])
    total = await count_olx_ads()
    offset = page * OLX_ADS_PER_PAGE
    ads = await get_olx_ads(offset=offset, limit=OLX_ADS_PER_PAGE)
    if not ads:
        await callback.bot.send_message(callback.from_user.id, "Brak ogłoszeń na tej stronie.")
        return
    for ad in ads:
        text = f"<b>{ad['title']}</b>\n{ad['description']}\nCena: <b>{ad['price']} PLN</b>"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Wyślij wiadomość", url=f"https://t.me/{ad['username']}")]
            ]
        )
        if ad['photo_id']:
            await callback.bot.send_photo(callback.from_user.id, photo=ad['photo_id'], caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            try:
                await callback.bot.send_photo(callback.from_user.id, photo=FSInputFile('olx1.png'), caption=text, reply_markup=kb, parse_mode="HTML")
            except Exception:
                await callback.bot.send_message(callback.from_user.id, text, reply_markup=kb, parse_mode="HTML")
    nav = []
    if offset > 0:
        nav.append(InlineKeyboardButton(text="⬅️ Poprzednia", callback_data=f"olx_list_{page-1}"))
    if offset + OLX_ADS_PER_PAGE < total:
        nav.append(InlineKeyboardButton(text="➡️ Następna", callback_data=f"olx_list_{page+1}"))
    # Dodaj uniwersalne przyciski nawigacyjne na końcu
    nav.append(InlineKeyboardButton(text="⬅️ Wróć", callback_data="home_0"))
    nav.append(InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"))
    nav.append(InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista"))
    if nav:
        nav_kb = InlineKeyboardMarkup(inline_keyboard=[nav])
        await callback.bot.send_message(callback.from_user.id, "Nawigacja:", reply_markup=nav_kb)
    await callback.answer()

# Moje ogłoszenia
@olx_router.callback_query(F.data == "olx_my")
async def olx_my(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    if not callback.from_user:
        await callback.answer("Brak danych użytkownika", show_alert=True)
        return
    user_id = callback.from_user.id
    ads = await get_user_olx_ads(user_id)
    if not ads:
        await callback.bot.send_message(user_id, "Nie masz żadnych ogłoszeń.")
        await callback.answer()
        return
    for ad in ads:
        text = f"<b>{ad['title']}</b>\n{ad['description']}\nCena: <b>{ad['price']} PLN</b>"
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Edytuj", callback_data=f"olx_myedit_{ad['id']}"),
                 InlineKeyboardButton(text="Sprzedane", callback_data=f"olx_sold_{ad['id']}")],
                [InlineKeyboardButton(text="Usuń ogłoszenie", callback_data=f"olx_del_{ad['id']}")]
            ]
        )
        if ad['photo_id']:
            await callback.bot.send_photo(user_id, photo=ad['photo_id'], caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.bot.send_photo(user_id, photo=FSInputFile('olx1.png'), caption=text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

# Usuwanie ogłoszenia
@olx_router.callback_query(F.data.startswith("olx_del_"))
async def olx_del(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    ad_id = int((callback.data or "").split("_")[-1])
    user_id = callback.from_user.id if callback.from_user else None
    if not user_id:
        await callback.answer("Brak danych użytkownika", show_alert=True)
        return
    await delete_olx_ad(ad_id, user_id)
    await callback.bot.send_message(user_id, "🗑️ Ogłoszenie zostało usunięte.")
    await callback.answer()

# Oznaczanie jako sprzedane
@olx_router.callback_query(F.data.startswith("olx_sold_"))
async def olx_sold(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    ad_id = int((callback.data or "").split("_")[-1])
    user_id = callback.from_user.id if callback.from_user else None
    if not user_id:
        await callback.answer("Brak danych użytkownika", show_alert=True)
        return
    await set_olx_ad_sold(ad_id, user_id)
    await callback.bot.send_message(user_id, "✅ Ogłoszenie oznaczone jako sprzedane.")
    await callback.answer()

# Edycja ogłoszenia (wielostanowa)
@olx_router.callback_query(F.data.startswith("olx_myedit_"))
async def olx_myedit(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    ad_id = int((callback.data or "").split("_")[-1])
    user_id = callback.from_user.id if callback.from_user else None
    if not user_id:
        await callback.answer("Brak danych użytkownika", show_alert=True)
        return
    await state.update_data(ad_id=ad_id, user_id=user_id)
    await callback.bot.send_message(user_id, "Podaj nowy tytuł ogłoszenia:")
    await state.set_state(EditAdStates.waiting_for_title)
    await callback.answer()

@olx_router.message(EditAdStates.waiting_for_title, flags={"block": False})
async def olx_edit_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text)
    await message.answer("Podaj nowy opis przedmiotu:")
    await state.set_state(EditAdStates.waiting_for_description)

@olx_router.message(EditAdStates.waiting_for_description, flags={"block": False})
async def olx_edit_description(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text)
    await message.answer("Podaj nową cenę (PLN):")
    await state.set_state(EditAdStates.waiting_for_price)

@olx_router.message(EditAdStates.waiting_for_price, flags={"block": False})
async def olx_edit_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text)
    await message.answer("Wyślij nowe zdjęcie lub napisz 'pomiń':")
    await state.set_state(EditAdStates.waiting_for_photo)

@olx_router.message(EditAdStates.waiting_for_photo, flags={"block": False})
async def olx_edit_photo(message: types.Message, state: FSMContext):
    data = await state.get_data()
    photo_id = None
    if message.photo:
        photo_id = message.photo[-1].file_id
    user_id = data.get("user_id")
    if not user_id:
        await message.answer("Brak danych użytkownika.")
        return
    await update_olx_ad(
        ad_id=data["ad_id"],
        user_id=user_id,
        title=data["title"],
        description=data["description"],
        price=data["price"],
        photo_id=photo_id
    )
    await message.answer("Ogłoszenie zostało zaktualizowane!")
    await state.clear()

@olx_router.message()
async def test_any_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    print(f"[OLX DEBUG] test_any_message: from_user={message.from_user.id}, text={message.text}, state={current_state}")
    if current_state:
        print(f"[OLX DEBUG] test_any_message: użytkownik w stanie FSM, nie przechwytuję wiadomości")
        return
    print(f"[OLX DEBUG] test_any_message: wiadomość NIE została obsłużona przez żaden handler FSM")
