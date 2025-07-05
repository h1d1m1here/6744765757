import random
import os
import asyncio
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from admin_utils import safe_delete

nocna_offer_router = Router()

CITIES = ["Katowice", "Tychy", "Kraków", "Chorzów", "Szczecin", "Chorzów"]
PRODUCTS = {
    "Katowice": [("🫧Alpha-PVP🫧 0.5g 🟢", 75), ("🫧Alpha-PVP🫧 1.0g 🟢", 140), ("🫧Alpha-PVP🫧 BLUE HQ 1g 🔵", 180), ("🫧Alpha-PVP🫧 PURPLE HQ 1g 🟣", 180), ("💊2C-B💊 20mg - 2szt", 55), ("💊2C-B💊 20mg - 1szt", 35), ("🧩LSD HQ🧩 300qu - 2szt", 85)],
    "Tychy": [("💊2C-B💊 20mg - 2szt", 55), ("🧩LSD HQ🧩 300qu - 2szt", 85), ("🧩LSD HQ🧩 300qu - 1szt", 40), ("🍫Hash - Classic Afgan🍫 2g", 120)],
    "Kraków": [("🫧Alpha-PVP🫧 1.0g 🟢", 140), ("🫧Alpha-PVP🫧 1.0g 🟢", 140)],
    "Chorzów": [("💠Mef 4=MMC💠 1g", 60), ("🫧Alpha-PVP🫧 1.0g 🟢", 140)],
    "Szczecin": [("💠Mef 4=MMC💠 1g", 60), ("🫧Alpha-PVP🫧 BLUE HQ 1g 🔵", 180), ("🫧Alpha-PVP🫧 PURPLE HQ 1g 🟣", 180)],
    "Chorzów": [("❄️Амфетамин❄️ 1g", 50), ("❄️Амфетамин❄️ 2g", 80), ("🫧Alpha-PVP🫧 1.0g 🟢", 140), ("🫧Alpha-PVP🫧 BLUE HQ 1g 🔵", 180), ("🫧Alpha-PVP🫧 PURPLE HQ 1g 🟣", 180)]
}
DISTRICTS = {
    "Katowice": ["Ogólne"],
    "Tychy": ["Ogólne"],
    "Kraków": ["Ogólne"],
    "Sosnowiec": ["Ogólne"],
    "Szczecin": ["Ogólne"],
    "Chorzów": ["Ogólne"]
}
PAYMENTS = ["BLIK", "KRYPTO", "PRZELEW", "PAYPAL"]

BLIK_NUMBERS = [
    "+48519402544",
    "+48512345678"
]
CRYPTO_ADDRESS = {
    "BTC": "bc1qmtm6msy0xjj52ggfgwxu55n2c6a00lh42qsxcu",
    "ETH": "0x3f9a51f9E4aa51862005412AAbf378A3ee6b7FC5",
    "SOL": "2UCjRv4FQdZgDu4dR12f7nmutYJBpRX71feLWbLBhoum"
}

def generate_order_number():
    return str(random.randint(10000, 99999))

class OfferStates(StatesGroup):
    choosing_city = State()
    choosing_product = State()
    choosing_district = State()
    summary = State()
    payment = State()
    crypto_currency = State()

@nocna_offer_router.callback_query(F.data == "noc_menu_offer")
async def offer_start(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=city, callback_data=f"offer_city_{city}")] for city in CITIES
        ] + [
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="noc_menu_offer"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    await state.clear()
    await state.set_state(OfferStates.choosing_city)
    text = (
        "<b>🌙 NOCNA_OFFER</b>\n"
        "Witaj w sklepie Nocna24!\n\n"
        "Wybierz miasto, w którym chcesz zrealizować zamówienie.\n"
        "Po wyborze miasta zobaczysz dostępne produkty."
    )
    await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@nocna_offer_router.callback_query(F.data.startswith("offer_city_"))
async def offer_choose_city(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    city = callback.data.split("_", 2)[2]
    await state.update_data(city=city)
    products = PRODUCTS.get(city, [])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=f"{name} ({price} zł)", callback_data=f"offer_product_{name}")] for name, price in products
        ] + [
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="noc_menu_offer"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    await state.set_state(OfferStates.choosing_product)
    await callback.message.answer(f"Wybrałeś miasto: {city}\nWybierz produkt:", reply_markup=kb)
    await callback.answer()

@nocna_offer_router.callback_query(F.data.startswith("offer_product_"))
async def offer_choose_product(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    product = callback.data.split("_", 2)[2]
    data = await state.get_data()
    city = data.get("city")
    price = next((p[1] for p in PRODUCTS[city] if p[0] == product), 0)
    await state.update_data(product=product, price=price)
    districts = DISTRICTS.get(city, [])
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=d, callback_data=f"offer_district_{d}")] for d in districts
        ] + [
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="noc_menu_offer"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    await state.set_state(OfferStates.choosing_district)
    await callback.message.answer(f"Wybrałeś produkt: {product}\nWybierz dzielnicę:", reply_markup=kb)
    await callback.answer()

@nocna_offer_router.callback_query(F.data.startswith("offer_district_"))
async def offer_choose_district(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    district = callback.data.split("_", 2)[2]
    await state.update_data(district=district)
    data = await state.get_data()
    city = data.get("city")
    product = data.get("product")
    price = data.get("price")
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Przechodzę do płatności", callback_data="offer_pay")],
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="noc_menu_offer"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    await state.set_state(OfferStates.summary)
    await callback.message.answer(
        f"Kupujesz produkt: <b>{product}</b>\nMiasto: <b>{city}</b>\nDzielnica: <b>{district}</b>\nCena: <b>{price} zł</b>",
        reply_markup=kb, parse_mode="HTML"
    )
    await callback.answer()

@nocna_offer_router.callback_query(F.data == "offer_cancel")
async def offer_cancel(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    await state.clear()
    msg = await callback.message.answer("Zamówienie anulowane.")
    await callback.answer()
    await asyncio.sleep(10)
    try:
        await msg.delete()
    except Exception:
        pass

@nocna_offer_router.callback_query(F.data == "offer_pay")
async def offer_pay(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=pay, callback_data=f"offer_payment_{pay}") for pay in PAYMENTS],
            [
                InlineKeyboardButton(text="⬅️ Wróć", callback_data="noc_menu_offer"),
                InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
            ]
        ]
    )
    await state.set_state(OfferStates.payment)
    msg = await callback.message.answer("Wybierz metodę płatności:", reply_markup=kb)
    await callback.answer()
    await asyncio.sleep(30)
    try:
        await msg.delete()
    except Exception:
        pass

@nocna_offer_router.callback_query(F.data.startswith("offer_payment_"))
async def offer_payment_method(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    method = callback.data.split("_", 2)[2]
    data = await state.get_data()
    price = data.get("price")
    order_number = generate_order_number()
    if method == "BLIK":
        blik_number = random.choice(BLIK_NUMBERS)
        # Pobierz dane zamówienia
        product = data.get("product")
        city = data.get("city")
        district = data.get("district")
        user = callback.from_user
        text = (
            f"Wybrałeś płatność BLIK.\n"
            f"Numer BLIK: <b>{blik_number}</b>\n"
            f"Kwota: <b>{price} zł</b>\n"
            f"Numer zamówienia: <b>{order_number}</b>\n"
            f"Po opłaceniu zamówienia napisz do obsługi z numerem zamówienia."
        )
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="Potwierdzam wpłatę", callback_data=f"blik_confirm_{order_number}")],
                [
                    InlineKeyboardButton(text="⬅️ Wróć", callback_data="noc_menu_offer"),
                    InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
                    InlineKeyboardButton(text="➡️ Dalej", callback_data="nocna_lista")
                ]
            ]
        )
        msg = await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
        await callback.answer()
        await asyncio.sleep(30)
        try:
            await msg.delete()
        except Exception:
            pass
        return
    elif method == "KRYPTO":
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="BTC", callback_data="offer_crypto_BTC")],
                [InlineKeyboardButton(text="ETH", callback_data="offer_crypto_ETH")],
                [InlineKeyboardButton(text="SOL", callback_data="offer_crypto_SOL")]
            ]
        )
        await state.set_state(OfferStates.crypto_currency)
        msg = await callback.message.answer("Wybierz kryptowalutę:", reply_markup=kb)
        await callback.answer()
        await asyncio.sleep(30)
        try:
            await msg.delete()
        except Exception:
            pass
        return
    elif method == "PRZELEW":
        msg = await callback.message.answer("Dane do przelewu: ...\nPo opłaceniu zamówienia napisz do obsługi z numerem zamówienia.")
        await state.clear()
        await callback.answer()
        await asyncio.sleep(15)
        try:
            await msg.delete()
        except Exception:
            pass
        return
    elif method == "PAYPAL":
        msg = await callback.message.answer("PayPal: sklep@nocna24.pl\nPo opłaceniu zamówienia napisz do obsługi z numerem zamówienia.")
        await state.clear()
        await callback.answer()
        await asyncio.sleep(15)
        try:
            await msg.delete()
        except Exception:
            pass
        return

@nocna_offer_router.callback_query(F.data.startswith("offer_crypto_"))
async def offer_crypto(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    currency = callback.data.split("_", 2)[2]
    address = CRYPTO_ADDRESS.get(currency)
    data = await state.get_data()
    price = data.get("price")
    order_number = generate_order_number()
    text = (
        f"Wybrałeś płatność {currency}.\n"
        f"Adres portfela: <b>{address}</b>\n"
        f"Kwota: <b>{price} zł</b>\n"
        f"Numer zamówienia: <b>{order_number}</b>\n"
        f"Po opłaceniu zamówienia napisz do obsługi z numerem zamówienia."
    )
    msg = await callback.message.answer(text, parse_mode="HTML")
    await state.clear()
    await callback.answer()
    await asyncio.sleep(20)
    try:
        await msg.delete()
    except Exception:
        pass

@nocna_offer_router.callback_query(F.data.startswith("blik_confirm_"))
async def blik_confirm(callback: types.CallbackQuery, state: FSMContext):
    await safe_delete(callback.message)
    data = await state.get_data()
    user = callback.from_user
    product = data.get("product")
    city = data.get("city")
    district = data.get("district")
    price = data.get("price")
    order_number = callback.data.split("_", 2)[2]
    admin_id = os.getenv("ADMIN_ID")
    msg = (
        f"🟡 POTWIERDZENIE WPŁATY\n"
        f"Użytkownik: <b>{user.first_name or user.username or user.id}</b> ({user.id})\n"
        f"Produkt: <b>{product}</b>\nMiasto: <b>{city}</b>\nDzielnica: <b>{district}</b>\nKwota: <b>{price} zł</b>\nNumer zamówienia: <b>{order_number}</b>"
    )
    if admin_id:
        try:
            await callback.bot.send_message(admin_id, msg, parse_mode="HTML")
        except Exception as e:
            print(f"[BLIK] Nie wysłano do admina: {e}")
    msg2 = await callback.message.answer("Dziękujemy! Twoje potwierdzenie wpłaty zostało przesłane do obsługi.")
    await state.clear()
    await callback.answer()
    await asyncio.sleep(15)
    try:
        await msg2.delete()
    except Exception:
        pass
