import asyncio
from aiogram import Bot, Dispatcher, types, Router
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties

API_TOKEN = "8166429025:AAHdLh8KCAJz-nCJEa4ouZWQP__JSekb0Wo"

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

router = Router()

class TestFSMStates(StatesGroup):
    waiting_for_test = State()

@router.message(Command("testfsm"))
async def testfsm_start(message: types.Message, state: FSMContext):
    print("[DEBUG] testfsm_start handler WYWOŁANY!")
    await message.answer("Podaj dowolny tekst (test FSM):")
    await state.set_state(TestFSMStates.waiting_for_test)

@router.message(TestFSMStates.waiting_for_test)
async def testfsm_waiting(message: types.Message, state: FSMContext):
    print(f"[DEBUG] testfsm_waiting handler WYWOŁANY! text={message.text}")
    await message.answer(f"Odebrano: {message.text}\nFSM DZIAŁA! (stan: {await state.get_state()})")
    await state.clear()

dp.include_router(router)

async def main():
    print("[DEBUG] Startuję testowy polling...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())