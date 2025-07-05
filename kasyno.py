from aiogram import Router, types, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from db import get_nc, add_nc
import random
import asyncio
import os
from dotenv import load_dotenv
from aiogram.types import FSInputFile

kasyno_router = Router()

# --- Słownik stawek kasynowych per user_id ---
stawki_nc = {}

# --- ZASADY ---
@kasyno_router.callback_query(lambda c: c.data == "kasyno_zasady")
async def kasyno_zasady(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "<b>ℹ️ Zasady kasyna NC:</b>\n"
        "- W każdej grze obstawiasz NC (Night Coiny).\n"
        "- Wygrywasz, gdy trafisz najlepszy wynik (np. 6 na kostce, środek w dart/koszykówce).\n"
        "- Przegrywasz, gdy wynik jest niższy.\n"
        "- Stawkę możesz zmieniać przyciskami ➖ i ➕.\n"
        "- Im wyższa stawka, tym wyższa potencjalna wygrana!\n"
        "- Saldo i historia NC dostępne w menu.\n"
        "\nPowodzenia!"
    )
    await callback.message.answer(text, parse_mode="HTML")

# --- Licznik gier do bonusu ---
bonus_counter = {}

async def kasyno_result_menu(callback, game_callback, user_id, stawka, bonus=False):
    import random
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="⬅️ Wróć", callback_data="go_back"),
        types.InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
        types.InlineKeyboardButton(text="😈 Powtórz", callback_data=game_callback)
    )
    # Bonus game co 30 gier
    if not bonus:
        bonus_counter[user_id] = bonus_counter.get(user_id, 0) + 1
        if bonus_counter[user_id] % 30 == 0:
            kb.row(types.InlineKeyboardButton(text="🤩 BONUS GAME 🤩", callback_data=f"bonus_{game_callback}"))
    await callback.message.edit_text("<b>🎲 KASYNO NC 🎲\nWybierz grę:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")

# --- obsługa zmiany stawki ---
@kasyno_router.callback_query(lambda c: c.data == "stawka_plus")
async def stawka_plus(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    stawka = stawki_nc.get(user_id, 10)
    stawka = min(stawka + 10, 100)
    stawki_nc[user_id] = stawka
    await kasyno_menu(callback, edit=True)

@kasyno_router.callback_query(lambda c: c.data == "stawka_minus")
async def stawka_minus(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    stawka = stawki_nc.get(user_id, 10)
    stawka = max(stawka - 10, 10)
    stawki_nc[user_id] = stawka
    await kasyno_menu(callback, edit=True)

# --- MENU KASYNA ---
@kasyno_router.callback_query(lambda c: c.data == "kasyno_menu")
async def kasyno_menu(callback: types.CallbackQuery, edit=False):
    await callback.answer()
    user_id = callback.from_user.id
    stawka = stawki_nc.get(user_id, 10)
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎰 Sloty", callback_data="kasyno_sloty"),
        types.InlineKeyboardButton(text="🎲 Kostka", callback_data="kasyno_kostka"),
        types.InlineKeyboardButton(text="🏀 Koszykówka", callback_data="kasyno_koszykowka"),
        types.InlineKeyboardButton(text="🎯 Dart", callback_data="kasyno_dart"),
        types.InlineKeyboardButton(text="🎡 Ruletka", callback_data="kasyno_ruletka")
    )
    kb.row(
        types.InlineKeyboardButton(text="➖", callback_data="stawka_minus"),
        types.InlineKeyboardButton(text=f"Stawka: {stawka} NC", callback_data="stawka_info"),
        types.InlineKeyboardButton(text="➕", callback_data="stawka_plus"),
        types.InlineKeyboardButton(text="ℹ️ Zasady", callback_data="kasyno_zasady")
    )
    kb.row(
        types.InlineKeyboardButton(text="⬅️ Wróć", callback_data="go_back"),
        types.InlineKeyboardButton(text="🏠 HOME", callback_data="home_0"),
        types.InlineKeyboardButton(text="💰 Saldo", callback_data="kasyno_saldo")
    )
    if edit:
        try:
            await callback.message.edit_text("<b>🎲 KASYNO NC 🎲\nWybierz grę:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
        except Exception:
            await callback.message.answer("<b>🎲 KASYNO NC 🎲\nWybierz grę:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")
    else:
        await callback.message.answer("<b>🎲 KASYNO NC 🎲\nWybierz grę:</b>", reply_markup=kb.as_markup(), parse_mode="HTML")

# --- SALDO ---
@kasyno_router.callback_query(lambda c: c.data == "kasyno_saldo")
async def kasyno_saldo(callback: types.CallbackQuery):
    await callback.answer()
    nc = await get_nc(callback.from_user.id)
    await callback.message.answer(f"Twoje saldo NC: {nc}", parse_mode="HTML")

# --- SLOTY ---

# --- SLOTY INTERAKTYWNE ---
sloty_state = {}  # user_id: {"cost": int, "symbols": [str, str, str], "stopped": [bool, bool, bool], "msg_id": int}

@kasyno_router.callback_query(lambda c: c.data == "kasyno_sloty")
async def kasyno_sloty(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    cost = stawki_nc.get(user_id, 10)
    nc = await get_nc(user_id)
    if nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    await add_nc(user_id, -cost, reason="sloty")
    audio_path = os.path.join("media", "slot_machine.mp3")
    if os.path.exists(audio_path):
        try:
            audio = FSInputFile(audio_path)
            await callback.message.answer_audio(audio, caption="🎰 Kręcimy bębnami!")
        except Exception:
            pass
    symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    # Stan początkowy: losujemy tylko pierwszy symbol, reszta pusta
    sloty_state[user_id] = {
        "cost": cost,
        "symbols": [None, None, None],
        "stopped": [False, False, False],
        "msg_id": None
    }
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🛑 Stop 1", callback_data="sloty_stop_0"),
        types.InlineKeyboardButton(text="🛑 Stop 2", callback_data="sloty_stop_1"),
        types.InlineKeyboardButton(text="�� Stop 3", callback_data="sloty_stop_2")
    )
    kb.row(types.InlineKeyboardButton(text="🎰 Pull (zatrzymaj wszystko)", callback_data="sloty_pull"))
    msg = await callback.message.answer("🎰 |   |   |   |\nKliknij STOP pod wybranym bębnem lub Pull, aby zatrzymać wszystkie!", reply_markup=kb.as_markup())
    sloty_state[user_id]["msg_id"] = msg.message_id


@kasyno_router.callback_query(lambda c: c.data.startswith("sloty_stop_"))
async def sloty_stop(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    state = sloty_state.get(user_id)
    if not state:
        await callback.message.answer("Nie rozpocząłeś gry w sloty!")
        return
    idx = int(callback.data.split("_")[-1])
    if state["stopped"][idx]:
        await callback.answer("Ten bęben już zatrzymany!", show_alert=True)
        return
    symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    state["symbols"][idx] = random.choice(symbols)
    state["stopped"][idx] = True
    # Aktualizuj widok slotów
    display = [s if s else " " for s in state["symbols"]]
    text = f"🎰 | {display[0]} | {display[1]} | {display[2]} |\n"
    stopped_count = sum(state["stopped"])
    if stopped_count < 3:
        text += f"Zatrzymaj pozostałe bębny!"
        kb = InlineKeyboardBuilder()
        kb.row(
            types.InlineKeyboardButton(text="🛑 Stop 1", callback_data="sloty_stop_0"),
            types.InlineKeyboardButton(text="🛑 Stop 2", callback_data="sloty_stop_1"),
            types.InlineKeyboardButton(text="🛑 Stop 3", callback_data="sloty_stop_2")
        )
        kb.row(types.InlineKeyboardButton(text="🎰 Pull (zatrzymaj wszystko)", callback_data="sloty_pull"))
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
    else:
        # Wynik końcowy
        win = 0
        cost = state["cost"]
        if len(set(state["symbols"])) == 1:
            win = cost * 5
        elif len(set(state["symbols"])) == 2:
            win = cost * 2
        if win:
            await add_nc(user_id, win, reason="sloty_wygrana")
        nc2 = await get_nc(user_id)
        text += "\n"
        if win:
            if len(set(state["symbols"])) == 1:
                text += f"JACKPOT! 3x {state['symbols'][0]}! Wygrywasz {win} NC!\n"
            else:
                text += f"Dwie takie same! Wygrywasz {win} NC!\n"
        else:
            text += "Brak wygranej.\n"
        text += f"Saldo: {nc2} NC"
        kb = InlineKeyboardBuilder()
        kb.row(
            types.InlineKeyboardButton(text="🎰 Zagraj ponownie", callback_data="kasyno_sloty"),
            types.InlineKeyboardButton(text="🏠 Menu kasyna", callback_data="kasyno_menu")
        )
        await callback.message.edit_text(text, reply_markup=kb.as_markup())
        sloty_state.pop(user_id, None)

# --- SLOTY: PULL ---
@kasyno_router.callback_query(lambda c: c.data == "sloty_pull")
async def sloty_pull(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    state = sloty_state.get(user_id)
    if not state:
        await callback.message.answer("Nie rozpocząłeś gry w sloty!")
        return
    symbols = ["🍒", "🍋", "🔔", "⭐", "7️⃣"]
    for i in range(3):
        if not state["stopped"][i]:
            state["symbols"][i] = random.choice(symbols)
            state["stopped"][i] = True
    # Wynik końcowy
    display = [s if s else " " for s in state["symbols"]]
    text = f"🎰 | {display[0]} | {display[1]} | {display[2]} |\n"
    win = 0
    cost = state["cost"]
    if len(set(state["symbols"])) == 1:
        win = cost * 5
    elif len(set(state["symbols"])) == 2:
        win = cost * 2
    if win:
        await add_nc(user_id, win, reason="sloty_wygrana")
    nc2 = await get_nc(user_id)
    text += "\n"
    if win:
        if len(set(state["symbols"])) == 1:
            text += f"JACKPOT! 3x {state['symbols'][0]}! Wygrywasz {win} NC!\n"
        else:
            text += f"Dwie takie same! Wygrywasz {win} NC!\n"
    else:
        text += "Brak wygranej.\n"
    text += f"Saldo: {nc2} NC"
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎰 Zagraj ponownie", callback_data="kasyno_sloty"),
        types.InlineKeyboardButton(text="🏠 Menu kasyna", callback_data="kasyno_menu")
    )
    await callback.message.edit_text(text, reply_markup=kb.as_markup())
    sloty_state.pop(user_id, None)

# --- KOSTKA ---

# --- INTERAKTYWNA KOSTKA ---
kostka_state = {}  # user_id: {"cost": int}

@kasyno_router.callback_query(lambda c: c.data == "kasyno_kostka")
async def kasyno_kostka(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    cost = stawki_nc.get(user_id, 10)
    nc = await get_nc(user_id)
    if nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    # Zapisz stan gry (stawka)
    kostka_state[user_id] = {"cost": cost}
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎲 Rzuć kostką", callback_data="kostka_rzut")
    )
    await callback.message.answer(f"🎲 Gra w kostkę!\nStawka: {cost} NC\nKliknij, aby rzucić kostką.", reply_markup=kb.as_markup())


# Handler do rzutu kostką po kliknięciu
@kasyno_router.callback_query(lambda c: c.data == "kostka_rzut")
async def kostka_rzut(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    state = kostka_state.get(user_id)
    if not state:
        await callback.message.answer("Nie rozpocząłeś gry w kostkę!")
        return
    cost = state["cost"]
    nc = await get_nc(user_id)
    if nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        kostka_state.pop(user_id, None)
        return
    await add_nc(user_id, -cost, reason="kostka")
    # Rzut kostką przez użytkownika (animacja)
    user_dice_msg = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(3)
    user_roll = user_dice_msg.dice.value
    # Rzut kostką przez bota (animacja)
    bot_dice_msg = await callback.message.answer_dice(emoji="🎲")
    await asyncio.sleep(3)
    bot_roll = bot_dice_msg.dice.value
    win = 0
    if user_roll > bot_roll:
        win = cost * 2
        await add_nc(user_id, win, reason="kostka_wygrana")
    nc2 = await get_nc(user_id)
    text = f"🎲 Ty: {user_roll} | Bot: {bot_roll}\n"
    if win:
        text += f"Wygrywasz {win} NC!\n"
    elif user_roll == bot_roll:
        text += "Remis!\n"
    else:
        text += "Przegrywasz.\n"
    text += f"Saldo: {nc2} NC"
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎲 Zagraj ponownie", callback_data="kasyno_kostka"),
        types.InlineKeyboardButton(text="🏠 Menu kasyna", callback_data="kasyno_menu")
    )
    await callback.message.answer(text, reply_markup=kb.as_markup())
    kostka_state.pop(user_id, None)

# --- ZDRAPKA ---
@kasyno_router.callback_query(lambda c: c.data == "kasyno_zdrapka")
async def kasyno_zdrapka(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    cost = stawki_nc.get(user_id, 10)
    nc = await get_nc(user_id)
    if nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    await add_nc(user_id, -cost, reason="zdrapka")
    # Proporcjonalne szanse i wygrane
    win = random.choices([0, cost * 2, cost * 4, cost * 10], weights=[0.7, 0.2, 0.08, 0.02])[0]
    if win:
        await add_nc(user_id, win, reason="zdrapka_wygrana")
    nc2 = await get_nc(user_id)
    text = f"🎯 Zdrapka: {'WYGRANA!' if win else 'Pusto!'}\n"
    if win:
        text += f"Wygrywasz {win} NC!\n"
    else:
        text += "Brak wygranej.\n"
    text += f"Saldo: {nc2} NC"
    await callback.message.answer(text)
    await kasyno_menu(callback)


# --- INTERAKTYWNA RULETKA ---
ruletka_bets = {}  # user_id: {"bet_type": "number"/"color", "value": int/str, "cost": int}
ruletka_active = False
GROUP_ID = -1002673559305  # Stały ID grupy kasyna (nie z .env)
ruletka_min_players = 5  # minimalna liczba graczy
ruletka_cost = 20
ruletka_queue = []  # [(user_id, bet_type, value, name)]

@kasyno_router.callback_query(lambda c: c.data == "kasyno_ruletka")
async def kasyno_ruletka(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    nc = await get_nc(user_id)
    if nc < ruletka_cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    # Wybór typu zakładu
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🔢 Liczba (0-36)", callback_data="ruletka_bet_number"),
        types.InlineKeyboardButton(text="🔴/⚫ Kolor", callback_data="ruletka_bet_color")
    )
    await callback.message.answer(f"🎡 RULETKA!\nStawka: {ruletka_cost} NC\nWybierz rodzaj zakładu:", reply_markup=kb.as_markup())

# Wybór liczby
@kasyno_router.callback_query(lambda c: c.data == "ruletka_bet_number")
async def ruletka_bet_number(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    kb = InlineKeyboardBuilder()
    # 0-36, po 6 w wierszu
    for i in range(0, 37, 6):
        row = [types.InlineKeyboardButton(text=str(n), callback_data=f"ruletka_num_{n}") for n in range(i, min(i+6, 37))]
        kb.row(*row)
    await callback.message.answer("Wybierz liczbę (0-36):", reply_markup=kb.as_markup())

# Wybór koloru
@kasyno_router.callback_query(lambda c: c.data == "ruletka_bet_color")
async def ruletka_bet_color(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🔴 Czerwony", callback_data="ruletka_color_red"),
        types.InlineKeyboardButton(text="⚫ Czarny", callback_data="ruletka_color_black")
    )
    await callback.message.answer("Wybierz kolor:", reply_markup=kb.as_markup())

# Zatwierdzenie liczby
@kasyno_router.callback_query(lambda c: c.data.startswith("ruletka_num_"))
async def ruletka_num_select(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in [u[0] for u in ruletka_queue]:
        await callback.answer("Już obstawiłeś w tej rundzie!", show_alert=True)
        return
    nc = await get_nc(user_id)
    if nc < ruletka_cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    num = int(callback.data.split("_")[-1])
    await add_nc(user_id, -ruletka_cost, reason="ruletka")
    ruletka_queue.append((user_id, "number", num, callback.from_user.full_name or str(user_id)))
    await callback.answer(f"Obstawiono liczbę {num}!", show_alert=True)
    await ruletka_waiting(callback)

# Zatwierdzenie koloru
@kasyno_router.callback_query(lambda c: c.data.startswith("ruletka_color_"))
async def ruletka_color_select(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    if user_id in [u[0] for u in ruletka_queue]:
        await callback.answer("Już obstawiłeś w tej rundzie!", show_alert=True)
        return
    nc = await get_nc(user_id)
    if nc < ruletka_cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    color = "red" if callback.data.endswith("red") else "black"
    await add_nc(user_id, -ruletka_cost, reason="ruletka")
    ruletka_queue.append((user_id, "color", color, callback.from_user.full_name or str(user_id)))
    await callback.answer(f"Obstawiono kolor {'CZERWONY' if color=='red' else 'CZARNY'}!", show_alert=True)
    await ruletka_waiting(callback)

# Czekanie na graczy i rozstrzygnięcie
async def ruletka_waiting(callback):
    global ruletka_active
    if len(ruletka_queue) < ruletka_min_players:
        await callback.message.answer(f"🎡 Ruletka: czeka na graczy... ({len(ruletka_queue)}/{ruletka_min_players})")
        return
    if ruletka_active:
        return
    ruletka_active = True


    # --- Wysyłka info na grupę i do graczy ---
    # ID grupy pobierane z .env (KASYNO_GROUP_ID)

    info_msg = ("🎡 Ruletka: zebrano minimalną liczbę graczy!\n"
                "Gra rozpocznie się za 15 minut.\n"
                "Możesz jeszcze dołączyć do tej rundy!\n"
                f"Aktualnie zapisanych: {len(ruletka_queue)}\n")
    join_kb = InlineKeyboardBuilder()
    join_kb.row(types.InlineKeyboardButton(text="Dołącz do ruletki!", callback_data="kasyno_ruletka"))

    # Do graczy prywatnie
    for uid, bet_type, value, name in ruletka_queue:
        try:
            await callback.bot.send_message(uid, info_msg, reply_markup=join_kb.as_markup())
        except Exception:
            pass
    # Na grupę
    try:
        await callback.bot.send_message(GROUP_ID, info_msg, reply_markup=join_kb.as_markup())
    except Exception:
        pass

    # Odliczanie i komunikaty
    await asyncio.sleep(12 * 60)  # 12 minut
    try:
        await callback.bot.send_message(GROUP_ID, "🎡 Ruletka: gra rozpocznie się za 3 minuty!", reply_markup=join_kb.as_markup())
    except Exception:
        pass
    for uid, bet_type, value, name in ruletka_queue:
        try:
            await callback.bot.send_message(uid, "🎡 Ruletka: gra rozpocznie się za 3 minuty!", reply_markup=join_kb.as_markup())
        except Exception:
            pass
    await asyncio.sleep(60)
    try:
        await callback.bot.send_message(GROUP_ID, "🎡 Ruletka: gra rozpocznie się za 2 minuty!", reply_markup=join_kb.as_markup())
    except Exception:
        pass
    for uid, bet_type, value, name in ruletka_queue:
        try:
            await callback.bot.send_message(uid, "🎡 Ruletka: gra rozpocznie się za 2 minuty!", reply_markup=join_kb.as_markup())
        except Exception:
            pass
    await asyncio.sleep(60)
    try:
        await callback.bot.send_message(GROUP_ID, "🎡 Ruletka: gra rozpocznie się za 1 minutę!", reply_markup=join_kb.as_markup())
    except Exception:
        pass
    for uid, bet_type, value, name in ruletka_queue:
        try:
            await callback.bot.send_message(uid, "🎡 Ruletka: gra rozpocznie się za 1 minutę!", reply_markup=join_kb.as_markup())
        except Exception:
            pass
    await asyncio.sleep(60)

    # Losowanie wyniku

    # Losowanie wyniku
    number = random.randint(0, 36)
    color = "red" if number != 0 and number % 2 == 1 else ("black" if number != 0 else "green")

    # Zbierz zwycięzców liczby i koloru
    number_winners = [u for u in ruletka_queue if u[1] == "number" and u[2] == number]
    color_winners = [u for u in ruletka_queue if u[1] == "color" and u[2] == color]

    # Wypłaty: liczba x10, kolor x3
    number_prize = ruletka_cost * 10
    color_prize = ruletka_cost * 3

    # Podział wygranej jeśli jest więcej zwycięzców
    number_share = number_prize // len(number_winners) if number_winners else 0
    color_share = color_prize // len(color_winners) if color_winners else 0

    # Wypłać wygrane
    for uid, bet_type, value, name in number_winners:
        if number_share > 0:
            await add_nc(uid, number_share, reason="ruletka_wygrana")
    for uid, bet_type, value, name in color_winners:
        if color_share > 0:
            await add_nc(uid, color_share, reason="ruletka_wygrana")

    # Powiadom wszystkich o wyniku
    for uid, bet_type, value, name in ruletka_queue:
        msg = f"🎡 Ruletka! Wylosowano: {number} ({'CZERWONY' if color=='red' else ('CZARNY' if color=='black' else 'ZIELONY')})\n"
        if bet_type == "number":
            msg += f"Twój zakład: liczba {value}\n"
            if number_winners and any(u[0] == uid for u in number_winners):
                msg += f"WYGRYWASZ {number_share} NC!\n"
            else:
                msg += "Brak wygranej.\n"
        else:
            msg += f"Twój zakład: kolor {'CZERWONY' if value=='red' else 'CZARNY'}\n"
            if color_winners and any(u[0] == uid for u in color_winners):
                msg += f"WYGRYWASZ {color_share} NC!\n"
            else:
                msg += "Brak wygranej.\n"
        saldo = await get_nc(uid)
        msg += f"Saldo: {saldo} NC"
        try:
            await callback.bot.send_message(uid, msg)
        except Exception:
            pass
    ruletka_queue.clear()
    ruletka_active = False

# --- KOSZYKÓWKA ---

# --- INTERAKTYWNA KOSZYKÓWKA ---
koszykowka_state = {}  # user_id: {"cost": int}

@kasyno_router.callback_query(lambda c: c.data == "kasyno_koszykowka")
async def kasyno_koszykowka(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    cost = stawki_nc.get(user_id, 10)
    nc = await get_nc(user_id)
    if nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    koszykowka_state[user_id] = {"cost": cost}
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🏀 Rzuć piłką", callback_data="koszykowka_rzut")
    )
    await callback.message.answer(f"🏀 Gra w koszykówkę!\nStawka: {cost} NC\nKliknij, aby rzucić piłką.", reply_markup=kb.as_markup())


# Handler do rzutu piłką po kliknięciu
@kasyno_router.callback_query(lambda c: c.data == "koszykowka_rzut")
async def koszykowka_rzut(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    state = koszykowka_state.get(user_id)
    if not state:
        await callback.message.answer("Nie rozpocząłeś gry w koszykówkę!")
        return
    cost = state["cost"]
    nc = await get_nc(user_id)
    if nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        koszykowka_state.pop(user_id, None)
        return
    await add_nc(user_id, -cost, reason="koszykowka")
    dice_msg = await callback.message.answer_dice(emoji="🏀")
    await asyncio.sleep(3)
    wynik = dice_msg.dice.value  # 1-6, 6 to najlepszy rzut
    win = 0
    if wynik == 6:
        win = cost * 3
        await add_nc(user_id, win, reason="koszykowka_wygrana")
    nc2 = await get_nc(user_id)
    text = f"🏀 Twój rzut: {wynik}/6\n"
    if win:
        text += f"TRAFIONA TRÓJKA! Wygrywasz {win} NC!\n"
    else:
        text += "Nie trafiłeś trójki.\n"
    text += f"Saldo: {nc2} NC"
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🏀 Zagraj ponownie", callback_data="kasyno_koszykowka"),
        types.InlineKeyboardButton(text="🏠 Menu kasyna", callback_data="kasyno_menu")
    )
    await callback.message.answer(text, reply_markup=kb.as_markup())
    koszykowka_state.pop(user_id, None)

# --- DART ---

# --- INTERAKTYWNY DART ---
dart_state = {}  # user_id: {"cost": int, "bonus": bool}

@kasyno_router.callback_query(lambda c: c.data == "kasyno_dart" or c.data == "bonus_kasyno_dart")
async def kasyno_dart(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    bonus = callback.data.startswith("bonus_")
    cost = stawki_nc.get(user_id, 10)
    nc = await get_nc(user_id)
    if not bonus and nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        return
    dart_state[user_id] = {"cost": cost, "bonus": bonus}
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎯 Rzuć rzutką", callback_data="dart_rzut")
    )
    await callback.message.answer(f"🎯 Gra w dart!\nStawka: {cost} NC\nKliknij, aby rzucić rzutką.", reply_markup=kb.as_markup())


# Handler do rzutu dartem po kliknięciu
@kasyno_router.callback_query(lambda c: c.data == "dart_rzut")
async def dart_rzut(callback: types.CallbackQuery):
    await callback.answer()
    user_id = callback.from_user.id
    state = dart_state.get(user_id)
    if not state:
        await callback.message.answer("Nie rozpocząłeś gry w dart!")
        return
    cost = state["cost"]
    bonus = state["bonus"]
    nc = await get_nc(user_id)
    if not bonus and nc < cost:
        await callback.answer("Masz za mało NC!", show_alert=True)
        dart_state.pop(user_id, None)
        return
    if not bonus:
        await add_nc(user_id, -cost, reason="dart")
    dice_msg = await callback.message.answer_dice(emoji="🎯")
    await asyncio.sleep(3)
    wynik = dice_msg.dice.value  # 1-6, 6 to środek tarczy
    win = 0
    if wynik == 6:
        win = cost * 4
        await add_nc(user_id, win, reason="dart_wygrana")
    nc2 = await get_nc(user_id)
    text = f"🎯 Twój rzut: {wynik}/6\n"
    if win:
        text += f"BULLSEYE! Wygrywasz {win} NC!\n"
    else:
        text += "Nie trafiłeś w środek.\n"
    text += f"Saldo: {nc2} NC"
    kb = InlineKeyboardBuilder()
    kb.row(
        types.InlineKeyboardButton(text="🎯 Zagraj ponownie", callback_data="kasyno_dart"),
        types.InlineKeyboardButton(text="🏠 Menu kasyna", callback_data="kasyno_menu")
    )
    await callback.message.answer(text, reply_markup=kb.as_markup())
    dart_state.pop(user_id, None)

# --- TEST POWIADOMIEŃ NA GRUPĘ/KANAŁ ---
@kasyno_router.message(lambda m: m.text and m.text.lower().startswith("/testnoty"))
async def testnoty_handler(message: types.Message):
    try:
        await message.answer("Wysyłam wszystkie powiadomienia kasynowe na grupę/kanał...")
        # Typowe powiadomienia kasynowe
        powiadomienia = [
            "🎡 Ruletka: zebrano minimalną liczbę graczy! Gra rozpocznie się za 15 minut. Możesz jeszcze dołączyć do tej rundy!",
            "🎡 Ruletka: gra rozpocznie się za 3 minuty!",
            "🎡 Ruletka: gra rozpocznie się za 2 minuty!",
            "🎡 Ruletka: gra rozpocznie się za 1 minutę!",
            "✅ Testowe powiadomienie na grupę/kanał działa!",
            "🎰 Sloty: JACKPOT! Gratulacje!",
            "🎲 Kostka: Wygrałeś z botem!",
            "🏀 Koszykówka: Trafiona trójka!",
            "🎯 Dart: Bullseye!"
        ]
        for powiadom in powiadomienia:
            await message.bot.send_message(GROUP_ID, powiadom)
        await message.answer(f"Wysłano {len(powiadomienia)} powiadomień na GROUP_ID: {GROUP_ID}")
    except Exception as e:
        await message.answer(f"Błąd przy wysyłaniu powiadomień: {e}")

@kasyno_router.message(lambda m: m.text and m.text.lower().startswith("/addncall "))
async def addncall_handler(message: types.Message):
    try:
        parts = message.text.strip().split()
        if len(parts) != 2 or not parts[1].isdigit():
            await message.answer("Użycie: /addncall <liczba>")
            return
        kwota = int(parts[1])
        # Pobierz wszystkich user_id z bazy (przykład: SELECT id FROM users)
        from db import get_all_user_ids  # Musisz mieć taką funkcję w db.py
        user_ids = await get_all_user_ids()
        for uid in user_ids:
            await add_nc(uid, kwota, reason="masowa_doladowanie")
        await message.answer(f"Dodano {kwota} NC wszystkim użytkownikom ({len(user_ids)} osób).")
    except Exception as e:
        await message.answer(f"Błąd przy masowym dodawaniu NC: {e}")
