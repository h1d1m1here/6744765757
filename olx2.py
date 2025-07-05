import os
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters import Command

olx2_router = Router()

class AddAd2States(StatesGroup):
    waiting_for_title = State()
    waiting_for_description = State()
    waiting_for_price = State()
    waiting_for_photo = State()

@olx2_router.message(Command("olx2"))
async def olx2_menu(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dodaj ogłoszenie OLX2", callback_data="olx2_add")],
        ]
    )
    await message.answer("<b>OLX2</b>\nWybierz opcję:", reply_markup=kb, parse_mode="HTML")

@olx2_router.callback_query(F.data == "olx2_add")
async def olx2_add_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.delete()
    await callback.bot.send_message(callback.from_user.id, "Podaj tytuł ogłoszenia OLX2:")
    await state.set_state(AddAd2States.waiting_for_title)
    await callback.answer()

@olx2_router.message(AddAd2States.waiting_for_title)
async def olx2_add_title(message: types.Message, state: FSMContext):
    title = message.text.strip() if message.text else None
    if not title or len(title) < 3:
        await message.answer("Tytuł ogłoszenia musi mieć minimum 3 znaki. Podaj tytuł jeszcze raz:")
        return
    await state.update_data(title=title)
    await message.answer("Podaj opis przedmiotu:")
    await state.set_state(AddAd2States.waiting_for_description)

@olx2_router.message(AddAd2States.waiting_for_description)
async def olx2_add_description(message: types.Message, state: FSMContext):
    description = message.text.strip() if message.text else None
    if not description or len(description) < 5:
        await message.answer("Opis ogłoszenia musi mieć minimum 5 znaków. Podaj opis jeszcze raz:")
        return
    await state.update_data(description=description)
    await message.answer("Podaj cenę (PLN):")
    await state.set_state(AddAd2States.waiting_for_price)

@olx2_router.message(AddAd2States.waiting_for_price)
async def olx2_add_price(message: types.Message, state: FSMContext):
    price = message.text.strip() if message.text else None
    if not price or not price.replace(",", ".").replace(".", "", 1).isdigit():
        await message.answer("Podaj poprawną cenę (liczba, np. 99.99):")
        return
    await state.update_data(price=price)
    await message.answer("Wyślij zdjęcie przedmiotu lub napisz 'pomiń':")
    await state.set_state(AddAd2States.waiting_for_photo)

@olx2_router.message(AddAd2States.waiting_for_photo)
async def olx2_add_photo(message: types.Message, state: FSMContext):
    if message.text and message.text.lower() == "pomiń":
        await message.answer("Ogłoszenie OLX2 zostało dodane bez zdjęcia!")
        await state.clear()
        return
    if not message.photo:
        await message.answer("Wyślij zdjęcie lub napisz 'pomiń'.")
        return
    await message.answer("Ogłoszenie OLX2 zostało dodane ze zdjęciem!")
    await state.clear()

# Testowy uniwersalny handler do debugowania
@olx2_router.message()
async def olx2_any_message(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    print(f"[OLX2 DEBUG] olx2_any_message: from_user={message.from_user.id}, text={message.text}, state={current_state}")
    if current_state:
        print(f"[OLX2 DEBUG] olx2_any_message: użytkownik w stanie FSM, nie przechwytuję wiadomości")
        return
    print(f"[OLX2 DEBUG] olx2_any_message: wiadomość NIE została obsłużona przez żaden handler FSM")
