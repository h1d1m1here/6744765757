from aiogram import Router, types
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import StateFilter, Command
from db_targ import add_ogloszenie, get_ogloszenia, get_ogloszenia_by_user, delete_ogloszenie, get_ogloszenie_by_id, update_ogloszenie
from db_targ_bonus import get_promo_bonus, use_promo_bonus
from targ_views import increment_wyswietlenia
from datetime import datetime, timedelta
import os

# Pobierz listę adminów z .env (np. ADMIN_ID=7572862671,8132494878)
ADMIN_IDS = set(os.getenv("ADMIN_ID", "").split(","))

nocny_targ_router = Router()

# --- PROMOWANIE OGŁOSZENIA przez admina ---
@nocny_targ_router.message(Command("promo"))
async def promo_ogloszenie(message: types.Message):
    if str(message.from_user.id) not in ADMIN_IDS:
        await message.answer("Brak uprawnień.")
        return
    args = message.text.split()
    if len(args) < 3:
        await message.answer("Użycie: /promo <id_ogłoszenia> <dni>")
        return
    try:
        ogloszenie_id = int(args[1])
        dni = int(args[2])
    except Exception:
        await message.answer("Podaj poprawne ID ogłoszenia i liczbę dni!")
        return
    ogloszenie = await get_ogloszenie_by_id(ogloszenie_id)
    if not ogloszenie:
        await message.answer("Nie znaleziono ogłoszenia o podanym ID.")
        return
    promoted_until = (datetime.now() + timedelta(days=dni)).isoformat()
    await update_ogloszenie(ogloszenie_id, promoted_until=promoted_until)
    await message.answer(f"Ogłoszenie {ogloszenie_id} promowane do {promoted_until}!")

# Pobierz listę adminów z .env (np. ADMIN_ID=7572862671,8132494878)
ADMIN_IDS = set(os.getenv("ADMIN_ID", "").split(","))

nocny_targ_router = Router()

class TargAddStates(StatesGroup):
    choose_type = State()        # Sprzedaję / Kupię
    title = State()             # Tytuł ogłoszenia
    opis = State()              # Opis ogłoszenia
    price = State()             # Cena
    city = State()              # Miejscowość
    photo = State()             # Zdjęcie (opcjonalnie)
    delivery = State()          # Forma odbioru
    summary = State()           # Podsumowanie

# --- MENU GŁÓWNE NOCNEGO TARGU ---
@nocny_targ_router.callback_query(lambda c: c.data == "nocny_targ")
async def nocny_targ_menu(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🛒 Przeglądaj Ogłoszenia", callback_data="targ_przegladaj"),
        InlineKeyboardButton(text="➕ Dodaj Ogłoszenie", callback_data="targ_dodaj")
    )
    kb.row(InlineKeyboardButton(text="📋 Twoje Ogłoszenia", callback_data="targ_twoje"))
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="go_back"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
        InlineKeyboardButton(text="➡️ Dalej", callback_data="targ_przegladaj")
    )
    opis = (
        "Cześć!\n"
        "Witam Cię na Nocnym Targowisku, możesz tu przeglądać ogłoszenia dodane przez innych użytkowników, a także dodać swoje ogłoszenie sprzedaży lub chęci kupna !\n"
        "Pamiętaj by dodając ogłoszenia i zdjęcia przestrzegać naszego regulaminu, to bardzo ważne, a kara za jego łamanie nie podlega odwołaniu !\n"
        "Kupując lub sprzedając produkty, pamiętaj by zachować czujność !\n"
        "NIE ODPOIWADAMY ZA HANDEL MIĘDZY UŻYTKOWNIKAMI ANI ZAMIESZCZANE PRZEZ NICH OGŁOSZENIA!!!\n"
        "Zachęcamy do skorzystania z opcji bezpiecznych zakupów, lub osobistego spotkania ze sprzedającym/kupującym.\n"
        "Życzymy owocnocyh zakupów!\n"
        "@Nocna24_bot ✨"
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    try:
        photo = FSInputFile("nooc2.png")
        await callback.message.answer_photo(photo=photo, caption=opis, reply_markup=kb.as_markup(), parse_mode="HTML")
    except Exception:
        await callback.message.answer(opis, reply_markup=kb.as_markup(), parse_mode="HTML")

# --- Placeholdery pod dalszą logikę ---
# Przeglądanie wszystkich ogłoszeń
@nocny_targ_router.callback_query(lambda c: c.data == "targ_przegladaj")
async def targ_przegladaj(callback: types.CallbackQuery):
    await callback.answer()
    try:
        await callback.message.delete()
    except Exception:
        pass
    ogloszenia = await get_ogloszenia()
    if not ogloszenia:
        await callback.message.answer("Brak ogłoszeń na Nocnym Targu.")
        return
    for ogl in ogloszenia[:10]:  # wyświetl pierwsze 10
        # Tytuł | Cena zł | Miejscowość
        text = f"<b>{ogl[5]}</b> | {ogl[4]} zł | {ogl[7]}"
        kb = InlineKeyboardBuilder()
        row = [
            InlineKeyboardButton(text="⬅️ Wróć", callback_data="nocny_targ"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
            InlineKeyboardButton(text="Szczegóły", callback_data=f"targ_ogl_{ogl[0]}")
        ]
        if str(callback.from_user.id) in ADMIN_IDS:
            row.append(InlineKeyboardButton(text="🗑️ Usuń (admin)", callback_data=f"targ_del_{ogl[0]}"))
        kb.row(*row)
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())

@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_ogl_"))
async def targ_ogloszenie_detail(callback: types.CallbackQuery):
    ogloszenie_id = int(callback.data.split("_", 2)[2])
    await increment_wyswietlenia(ogloszenie_id, 3)
    ogl = await get_ogloszenie_by_id(ogloszenie_id)  # pobierz ponownie po aktualizacji!
    if not ogl:
        await callback.answer("Ogłoszenie nie istnieje.", show_alert=True)
        return
    wyswietlenia = ogl[11] if len(ogl) > 11 and ogl[11] is not None else 0
    text = (
        f"<b>{ogl[3]}</b> | {ogl[4]} zł\n"
        f"{ogl[5]}\n"
        f"Miejscowość: {ogl[7]}\n"
        f"Forma odbioru: {'H2H' if ogl[8] else 'Inna'}\n"
        f"<b>🔎 Wyświetlono: {wyswietlenia}</b>"
    )
    kb = InlineKeyboardBuilder()
    row = [
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_przegladaj"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    ]
    if ogl[2] and ogl[2] != "brak":
        row.append(InlineKeyboardButton(text="💬 Wiadomość", url=f"https://t.me/{ogl[2]}"))
    if str(callback.from_user.id) in ADMIN_IDS:
        row.append(InlineKeyboardButton(text="🗑️ Usuń (admin)", callback_data=f"targ_del_{ogl[0]}"))
    kb.row(*row)
    if ogl[6]:
        await callback.message.answer_photo(ogl[6], caption=text, parse_mode="HTML", reply_markup=kb.as_markup())
    else:
        await callback.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())

@nocny_targ_router.callback_query(lambda c: c.data == "targ_dodaj")
async def targ_dodaj(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🟢 Sprzedaję", callback_data="targ_type_sell"),
        InlineKeyboardButton(text="🔵 Kupię", callback_data="targ_type_buy")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="nocny_targ"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await state.set_state(TargAddStates.choose_type)
    await callback.message.answer(
        "Wybierz rodzaj ogłoszenia:",
        reply_markup=kb.as_markup()
    )

# Obsługa wyboru typu ogłoszenia
@nocny_targ_router.callback_query(lambda c: c.data in ["targ_type_sell", "targ_type_buy"])
async def targ_choose_type(callback: types.CallbackQuery, state: FSMContext):
    ad_type = "Sprzedaję" if callback.data == "targ_type_sell" else "Kupię"
    await state.update_data(ad_type=ad_type)
    await state.set_state(TargAddStates.title)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_dodaj"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        f"Wybrano: {ad_type}\nPodaj tytuł ogłoszenia:",
        reply_markup=kb.as_markup()
    )

# Obsługa podania tytułu ogłoszenia
@nocny_targ_router.message(StateFilter(TargAddStates.title))
async def targ_add_title(message: types.Message, state: FSMContext):
    title = message.text.strip()
    if not title or len(title) < 3:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_dodaj"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
        )
        await message.answer("Tytuł ogłoszenia musi mieć co najmniej 3 znaki. Podaj poprawny tytuł:", reply_markup=kb.as_markup())
        return
    await state.update_data(title=title)
    await state.set_state(TargAddStates.opis)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_title_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await message.answer(f"Tytuł zapisany: {title}\nPodaj opis ogłoszenia:", reply_markup=kb.as_markup())

# Obsługa podania opisu ogłoszenia
@nocny_targ_router.message(StateFilter(TargAddStates.opis))
async def targ_add_opis(message: types.Message, state: FSMContext):
    opis = message.text.strip()
    if not opis or len(opis) < 5:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_title_back"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
        )
        await message.answer("Opis ogłoszenia musi mieć co najmniej 5 znaków. Podaj poprawny opis:", reply_markup=kb.as_markup())
        return
    await state.update_data(opis=opis)
    await state.set_state(TargAddStates.price)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_opis_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await message.answer(f"Opis zapisany. Podaj cenę (liczbowo, np. 100):", reply_markup=kb.as_markup())

# Obsługa przycisku Wróć z kroku opisu (wraca do tytułu)
@nocny_targ_router.callback_query(lambda c: c.data == "targ_opis_back")
async def targ_opis_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.title)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_dodaj"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer("Podaj tytuł ogłoszenia:", reply_markup=kb.as_markup())

# Obsługa podania ceny
@nocny_targ_router.message(StateFilter(TargAddStates.price))
async def targ_add_price(message: types.Message, state: FSMContext):
    price_text = message.text.strip().replace(',', '.')
    try:
        price = float(price_text)
        if price < 0:
            raise ValueError
    except ValueError:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_opis_back"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
        )
        await message.answer("Podaj poprawną cenę (liczbowo, np. 100):", reply_markup=kb.as_markup())
        return
    await state.update_data(price=price)
    await state.set_state(TargAddStates.city)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_price_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await message.answer(f"Cena zapisana: {price} zł\nPodaj miejscowość:", reply_markup=kb.as_markup())

# Obsługa podania miejscowości
@nocny_targ_router.message(StateFilter(TargAddStates.city))
async def targ_add_city(message: types.Message, state: FSMContext):
    city = message.text.strip()
    if not city or len(city) < 2:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_price_back"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
        )
        await message.answer("Podaj poprawną miejscowość (min. 2 znaki):", reply_markup=kb.as_markup())
        return
    await state.update_data(city=city)
    await state.set_state(TargAddStates.photo)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_city_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
        InlineKeyboardButton(text="⏭️ Pomiń", callback_data="targ_skip_photo")
    )
    await message.answer("Możesz dodać zdjęcie do ogłoszenia. Prześlij zdjęcie lub kliknij 'Pomiń':", reply_markup=kb.as_markup())

# Obsługa przycisku Wróć z kroku miejscowości (wraca do ceny)
@nocny_targ_router.callback_query(lambda c: c.data == "targ_price_back")
async def targ_price_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.price)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_title_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Podaj cenę (liczbowo, np. 100):", reply_markup=kb.as_markup())

# Obsługa przycisku Wróć z kroku ceny (wraca do tytułu)
@nocny_targ_router.callback_query(lambda c: c.data == "targ_title_back")
async def targ_title_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.title)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_dodaj"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Podaj tytuł ogłoszenia:", reply_markup=kb.as_markup())

# Obsługa przesłania zdjęcia
@nocny_targ_router.message(StateFilter(TargAddStates.photo))
async def targ_add_photo(message: types.Message, state: FSMContext):
    if not message.photo:
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_city_back"),
            InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
            InlineKeyboardButton(text="⏭️ Pomiń", callback_data="targ_skip_photo")
        )
        await message.answer("Wyślij zdjęcie lub kliknij 'Pomiń':", reply_markup=kb.as_markup())
        return
    file_id = message.photo[-1].file_id
    await state.update_data(photo=file_id)
    await state.set_state(TargAddStates.delivery)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🤝 H2H", callback_data="targ_delivery_h2h"),
        InlineKeyboardButton(text="📦 Dostawa", callback_data="targ_delivery_dostawa")
    )
    kb.row(
        InlineKeyboardButton(text="🐾 Wykopki", callback_data="targ_delivery_wykopki"),
        InlineKeyboardButton(text="👍 Dowolny", callback_data="targ_delivery_any")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_photo_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await message.answer("Wybierz formę odbioru:", reply_markup=kb.as_markup())

# Obsługa przycisku Pomiń zdjęcie
@nocny_targ_router.callback_query(lambda c: c.data == "targ_skip_photo")
async def targ_skip_photo(callback: types.CallbackQuery, state: FSMContext):
    await state.update_data(photo=None)
    await state.set_state(TargAddStates.delivery)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🤝 H2H", callback_data="targ_delivery_h2h"),
        InlineKeyboardButton(text="📦 Dostawa", callback_data="targ_delivery_dostawa")
    )
    kb.row(
        InlineKeyboardButton(text="🐾 Wykopki", callback_data="targ_delivery_wykopki"),
        InlineKeyboardButton(text="👍 Dowolny", callback_data="targ_delivery_any")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_photo_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Wybierz formę odbioru:", reply_markup=kb.as_markup())

# Obsługa przycisku Wróć z kroku zdjęcia (wraca do miejscowości)
@nocny_targ_router.callback_query(lambda c: c.data == "targ_city_back")
async def targ_city_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.city)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_price_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Podaj miejscowość:", reply_markup=kb.as_markup())

# Obsługa wyboru formy odbioru
@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_delivery_"))
async def targ_choose_delivery(callback: types.CallbackQuery, state: FSMContext):
    delivery_map = {
        "targ_delivery_h2h": "🤝 H2H",
        "targ_delivery_dostawa": "📦 Dostawa",
        "targ_delivery_wykopki": "🐾 Wykopki",
        "targ_delivery_any": "👍 Dowolny"
    }
    delivery = delivery_map.get(callback.data, "")
    await state.update_data(delivery=delivery)
    await state.set_state(TargAddStates.summary)
    data = await state.get_data()
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Akceptuj i dodaj", callback_data="targ_accept"),
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_delivery_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    podsumowanie = (
        f"<b>Podsumowanie ogłoszenia:</b>\n"
        f"Typ: {data.get('ad_type')}\n"
        f"Tytuł: {data.get('title')}\n"
        f"Cena: {data.get('price')} zł\n"
        f"Miejscowość: {data.get('city')}\n"
        f"Forma odbioru: {delivery}\n"
    )
    if data.get('photo'):
        await callback.message.answer_photo(data['photo'], caption=podsumowanie, parse_mode="HTML", reply_markup=kb.as_markup())
    else:
        await callback.message.answer(podsumowanie, parse_mode="HTML", reply_markup=kb.as_markup())

# Obsługa przycisku Wróć z kroku formy odbioru (wraca do zdjęcia)
@nocny_targ_router.callback_query(lambda c: c.data == "targ_photo_back")
async def targ_photo_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.photo)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_city_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0"),
        InlineKeyboardButton(text="⏭️ Pomiń", callback_data="targ_skip_photo")
    )
    await callback.message.answer("Możesz dodać zdjęcie do ogłoszenia. Prześlij zdjęcie lub kliknij 'Pomiń':", reply_markup=kb.as_markup())

# Obsługa przycisku Wróć z podsumowania (wraca do wyboru formy odbioru)
@nocny_targ_router.callback_query(lambda c: c.data == "targ_delivery_back")
async def targ_delivery_back(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.delivery)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🤝 H2H", callback_data="targ_delivery_h2h"),
        InlineKeyboardButton(text="📦 Dostawa", callback_data="targ_delivery_dostawa")
    )
    kb.row(
        InlineKeyboardButton(text="🐾 Wykopki", callback_data="targ_delivery_wykopki"),
        InlineKeyboardButton(text="👍 Dowolny", callback_data="targ_delivery_any")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_photo_back"),
        InlineKeyboardButton(text="🏠 Home", callback_data="home_0")
    )
    await callback.message.answer("Wybierz formę odbioru:", reply_markup=kb.as_markup())

# Obsługa akceptacji i dodania ogłoszenia
@nocny_targ_router.callback_query(lambda c: c.data == "targ_accept")
async def targ_accept(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    user = callback.from_user
    # Zapis do bazy danych
    await add_ogloszenie(
        user_id=user.id,
        username=user.username or "brak",
        typ=data.get("ad_type"),
        cena=str(data.get("price")),
        opis=data.get("opis"),
        photo_id=data.get("photo"),
        miejscowosc=data.get("city"),
        bezpieczne=data.get("delivery") == "🤝 H2H"
    )
    await state.clear()
    await callback.message.answer("✅ Ogłoszenie zostało dodane!", reply_markup=None)

# Twoje ogłoszenia - lista z opcjami edycji i usuwania
@nocny_targ_router.callback_query(lambda c: c.data == "targ_twoje")
async def targ_twoje(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    ogloszenia = await get_ogloszenia_by_user(user_id)
    if not ogloszenia:
        await callback.message.answer("Nie masz jeszcze żadnych ogłoszeń na Nocnym Targu.")
        return
    promo_count = await get_promo_bonus(user_id)
    for ogl in ogloszenia:
        text = (
            f"<b>{ogl[3]}</b> | {ogl[4]} zł\n"
            f"{ogl[5]}\n"
            f"Miejscowość: {ogl[7]}\n"
            f"Forma odbioru: {'H2H' if ogl[8] else 'Inna'}\n"
            f"ID ogłoszenia: {ogl[0]}"
        )
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="✏️ Edytuj", callback_data=f"targ_edit_{ogl[0]}"),
            InlineKeyboardButton(text="🗑️ Usuń", callback_data=f"targ_del_{ogl[0]}")
        )
        # Dodaj przycisk promowania jeśli użytkownik ma bonusy (sprawdzaj dla każdego ogłoszenia osobno)
        if promo_count > 0:
            kb.row(InlineKeyboardButton(text=f"Promuj ({promo_count})", callback_data=f"targ_bonus_promuj_{ogl[0]}"))
        if ogl[6]:
            await callback.message.answer_photo(ogl[6], caption=text, parse_mode="HTML", reply_markup=kb.as_markup())
        else:
            await callback.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
# Obsługa promowania ogłoszenia przez bonus
from db_targ import update_ogloszenie
from datetime import datetime, timedelta
@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_bonus_promuj_"))
async def targ_bonus_promuj(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    ogloszenie_id = int(callback.data.split("_", 3)[3])
    promo_count = await get_promo_bonus(user_id)
    if promo_count < 1:
        await callback.answer("Brak dostępnych bonusów promowania.", show_alert=True)
        return
    promoted_until = (datetime.now() + timedelta(hours=24)).isoformat()
    await update_ogloszenie(ogloszenie_id, promoted_until=promoted_until)
    await use_promo_bonus(user_id)
    await callback.answer("Ogłoszenie zostało wyróżnione na 24h!", show_alert=True)
    await callback.message.edit_reply_markup(reply_markup=None)

# Usuwanie ogłoszenia z potwierdzeniem
@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_del_"))
async def targ_delete(callback: types.CallbackQuery):
    ogloszenie_id = int(callback.data.split("_", 2)[2])
    # Potwierdzenie usunięcia
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="✅ Tak, usuń", callback_data=f"targ_del_confirm_{ogloszenie_id}"),
        InlineKeyboardButton(text="❌ Anuluj", callback_data="targ_przegladaj")
    )
    await callback.message.answer("Czy na pewno chcesz usunąć to ogłoszenie?", reply_markup=kb.as_markup())

@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_del_confirm_"))
async def targ_delete_confirm(callback: types.CallbackQuery):
    ogloszenie_id = int(callback.data.split("_", 3)[3])
    await delete_ogloszenie(ogloszenie_id, user_id=callback.from_user.id)
    await callback.answer("Ogłoszenie usunięte.", show_alert=True)
    await callback.message.answer("Ogłoszenie zostało usunięte.")

# Rozpoczęcie edycji ogłoszenia
@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_edit_"))
async def targ_edit_start(callback: types.CallbackQuery, state: FSMContext):
    ogloszenie_id = int(callback.data.split("_", 2)[2])
    ogl = await get_ogloszenie_by_id(ogloszenie_id)
    if not ogl or ogl[1] != callback.from_user.id:
        await callback.answer("Brak dostępu do edycji tego ogłoszenia.", show_alert=True)
        return
    await state.update_data(edit_ogloszenie_id=ogloszenie_id)
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="Tytuł", callback_data="targ_edit_title"),
        InlineKeyboardButton(text="Cena", callback_data="targ_edit_price")
    )
    kb.row(
        InlineKeyboardButton(text="Miejscowość", callback_data="targ_edit_city"),
        InlineKeyboardButton(text="Zdjęcie", callback_data="targ_edit_photo")
    )
    kb.row(
        InlineKeyboardButton(text="Opis", callback_data="targ_edit_opis"),  # NOWY PRZYCISK
        InlineKeyboardButton(text="Forma odbioru", callback_data="targ_edit_delivery"),
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_twoje")
    )
    await callback.message.answer("Co chcesz edytować?", reply_markup=kb.as_markup())

# Edycja tytułu
@nocny_targ_router.callback_query(lambda c: c.data == "targ_edit_title")
async def targ_edit_title_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.title)
    await callback.message.answer("Podaj nowy tytuł ogłoszenia:")

@nocny_targ_router.message(StateFilter(TargAddStates.title))
async def targ_edit_title_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ogloszenie_id = data.get("edit_ogloszenie_id")
    title = message.text.strip()
    if not title or len(title) < 3:
        await message.answer("Tytuł musi mieć co najmniej 3 znaki. Podaj poprawny tytuł:")
        return
    await update_ogloszenie(ogloszenie_id, opis=title)
    await state.clear()
    await message.answer("Tytuł ogłoszenia został zaktualizowany.")
    # Powrót do listy ogłoszeń
    await targ_twoje(message, state)

# Edycja ceny
@nocny_targ_router.callback_query(lambda c: c.data == "targ_edit_price")
async def targ_edit_price_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.price)
    await callback.message.answer("Podaj nową cenę ogłoszenia:")

@nocny_targ_router.message(StateFilter(TargAddStates.price))
async def targ_edit_price_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ogloszenie_id = data.get("edit_ogloszenie_id")
    price_text = message.text.strip().replace(',', '.')
    try:
        price = float(price_text)
        if price < 0:
            raise ValueError
    except ValueError:
        await message.answer("Podaj poprawną cenę (liczbowo, np. 100):")
        return
    await update_ogloszenie(ogloszenie_id, cena=str(price))
    await state.clear()
    await message.answer("Cena ogłoszenia została zaktualizowana.")
    await targ_twoje(message, state)

# Edycja miejscowości
@nocny_targ_router.callback_query(lambda c: c.data == "targ_edit_city")
async def targ_edit_city_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.city)
    await callback.message.answer("Podaj nową miejscowość ogłoszenia:")

@nocny_targ_router.message(StateFilter(TargAddStates.city))
async def targ_edit_city_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ogloszenie_id = data.get("edit_ogloszenie_id")
    city = message.text.strip()
    if not city or len(city) < 2:
        await message.answer("Podaj poprawną miejscowość (min. 2 znaki):")
        return
    await update_ogloszenie(ogloszenie_id, miejscowosc=city)
    await state.clear()
    await message.answer("Miejscowość ogłoszenia została zaktualizowana.")
    await targ_twoje(message, state)

# Edycja zdjęcia
@nocny_targ_router.callback_query(lambda c: c.data == "targ_edit_photo")
async def targ_edit_photo_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.photo)
    await callback.message.answer("Prześlij nowe zdjęcie do ogłoszenia:")

@nocny_targ_router.message(StateFilter(TargAddStates.photo))
async def targ_edit_photo_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ogloszenie_id = data.get("edit_ogloszenie_id")
    if not message.photo:
        await message.answer("Wyślij zdjęcie jako zdjęcie (nie plik)!");
        return
    file_id = message.photo[-1].file_id
    await update_ogloszenie(ogloszenie_id, photo_id=file_id)
    await state.clear()
    await message.answer("Zdjęcie ogłoszenia zostało zaktualizowane.")
    await targ_twoje(message, state)

# Edycja formy odbioru
@nocny_targ_router.callback_query(lambda c: c.data == "targ_edit_delivery")
async def targ_edit_delivery_start(callback: types.CallbackQuery, state: FSMContext):
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🤝 H2H", callback_data="targ_edit_delivery_h2h"),
        InlineKeyboardButton(text="📦 Dostawa", callback_data="targ_edit_delivery_dostawa")
    )
    kb.row(
        InlineKeyboardButton(text="🐾 Wykopki", callback_data="targ_edit_delivery_wykopki"),
        InlineKeyboardButton(text="👍 Dowolny", callback_data="targ_edit_delivery_any")
    )
    await callback.message.answer("Wybierz nową formę odbioru:", reply_markup=kb.as_markup())

@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_edit_delivery_"))
async def targ_edit_delivery_save(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    ogloszenie_id = data.get("edit_ogloszenie_id")
    delivery_map = {
        "targ_edit_delivery_h2h": 1,
        "targ_edit_delivery_dostawa": 0,
        "targ_edit_delivery_wykopki": 0,
        "targ_edit_delivery_any": 0
    }
    bezpieczne = delivery_map.get(callback.data, 0)
    await update_ogloszenie(ogloszenie_id, bezpieczne=bezpieczne)
    await state.clear()
    await callback.message.answer("Forma odbioru została zaktualizowana.")
    await targ_twoje(callback, state)

# Edycja opisu
@nocny_targ_router.callback_query(lambda c: c.data == "targ_edit_opis")
async def targ_edit_opis_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(TargAddStates.opis)
    await callback.message.answer("Podaj nowy opis ogłoszenia:")

@nocny_targ_router.message(StateFilter(TargAddStates.opis))
async def targ_edit_opis_save(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ogloszenie_id = data.get("edit_ogloszenie_id")
    opis = message.text.strip()
    if not opis or len(opis) < 5:
        await message.answer("Opis ogłoszenia musi mieć co najmniej 5 znaków. Podaj poprawny opis:")
        return
    await update_ogloszenie(ogloszenie_id, opis=opis)
    await state.clear()
    await message.answer("Opis ogłoszenia został zaktualizowany.")
    await targ_twoje(message, state)
