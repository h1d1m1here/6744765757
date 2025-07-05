from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton
from db import get_shops, get_shop_countries, set_shop_countries, get_all_countries

# Mapowanie kodów krajów na flagi emoji
COUNTRY_FLAGS = {
    'PL': '🇵🇱',
    'UA': '🇺🇦',
    'DE': '🇩🇪',
    # Dodaj kolejne kraje jeśli potrzeba
}

def get_flags_for_shop(shop_countries):
    """Zwraca string z flagami na podstawie listy kodów krajów."""
    return ''.join(COUNTRY_FLAGS.get(code, '') for code in shop_countries)

# Uniwersalna funkcja do rozpoczęcia edycji pola
async def start_edit_shop_field(message, field, field_label):
    from main import ADMIN_ID  # import lokalny, by uniknąć cykliczności
    if str(message.from_user.id) != str(ADMIN_ID):
        await message.answer("⛔ Brak uprawnień.")
        return
    shops = await get_shops()
    kb = InlineKeyboardBuilder()
    for shop in shops:
        kb.row(InlineKeyboardButton(text=f"{get_flags_for_shop(shop.get('countries', []))} {shop['shop_name']}", callback_data=f"editshop_{field}_{shop['id']}"))
    await message.answer(f"Wybierz sklep do edycji {field_label}:", reply_markup=kb.as_markup())

# Pomocnicza funkcja do bezpiecznego usuwania wiadomości (efekt znikania)
import asyncio
async def safe_delete(msg):
    try:
        await msg.delete()
    except Exception:
        pass
