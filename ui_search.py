import os
import importlib
from aiogram import types, F
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.state import State, StatesGroup

class SearchStates(StatesGroup):
    waiting_for_sklep = State()
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

async def search_menu_start(callback: types.CallbackQuery, state: FSMContext):
    all_products = load_all_products()
    sklepy = list(all_products.keys())
    kb = InlineKeyboardBuilder()
    for sklep in sklepy:
        kb.button(text=sklep.replace("produkty_", "").capitalize(), callback_data=f"search_sklep_{sklep}")
    await state.set_state(SearchStates.waiting_for_sklep)
    await callback.message.answer("Wybierz sklep:", reply_markup=kb.as_markup())

async def search_sklep_selected(callback: types.CallbackQuery, state: FSMContext):
    sklep = callback.data.split("search_sklep_")[1]
    all_products = load_all_products()
    miasta = list(all_products[sklep].keys())
    kb = InlineKeyboardBuilder()
    for miasto in miasta:
        kb.button(text=miasto, callback_data=f"search_city_{sklep}_{miasto}")
    await state.update_data(sklep=sklep)
    await state.set_state(SearchStates.waiting_for_city)
    await callback.message.answer("Wybierz miasto:", reply_markup=kb.as_markup())

async def search_city_selected(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("search_city_")[1].split("_")
    sklep = parts[0]
    miasto = "_".join(parts[1:])
    await state.update_data(miasto=miasto)
    await state.set_state(SearchStates.waiting_for_phrase)
    await callback.message.answer(f"Wybrane miasto: {miasto}\nWpisz frazę do wyszukania:")

async def search_phrase_entered(message: types.Message, state: FSMContext):
    data = await state.get_data()
    sklep = data["sklep"]
    miasto = data["miasto"]
    fraza = message.text.strip().lower()
    all_products = load_all_products()
    produkty = all_products.get(sklep, {}).get(miasto, [])
    results = [p for p in produkty if fraza in p["name"].lower()]
    if results:
        text = "\n".join([f"- {p['name']} {p['variant']} {p['price']}" for p in results])
    else:
        text = "Brak wyników."
    await message.answer(text)
    await state.clear()
