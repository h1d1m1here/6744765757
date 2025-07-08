# IMPLEMENTACJA ULEPSZEŃ - SYSTEM OPINII I NOCNY TARG

## **1. UPROSZCZONY SYSTEM OPINII - NOWY KOD**

### Nowy, prostszy FSM dla opinii (3 kroki):

```python
class SimpleReviewStates(StatesGroup):
    rating = State()        # Ocena 1-5 ⭐
    comment = State()       # Komentarz lub szablon
    confirm = State()       # Potwierdzenie

# KROK 1: Ocena gwiazdkami
@dp.callback_query(lambda c: c.data.startswith("review_simple_"))
async def simple_review_start(callback: types.CallbackQuery, state: FSMContext):
    shop_id = callback.data.split("_")[2]
    await state.update_data(shop_id=shop_id)
    await state.set_state(SimpleReviewStates.rating)
    
    kb = InlineKeyboardBuilder()
    # Większe, czytelniejsze przyciski
    kb.row(
        InlineKeyboardButton(text="⭐ (1)", callback_data="simple_rate_1"),
        InlineKeyboardButton(text="⭐⭐ (2)", callback_data="simple_rate_2")
    )
    kb.row(
        InlineKeyboardButton(text="⭐⭐⭐ (3)", callback_data="simple_rate_3"),
        InlineKeyboardButton(text="⭐⭐⭐⭐ (4)", callback_data="simple_rate_4")
    )
    kb.row(InlineKeyboardButton(text="⭐⭐⭐⭐⭐ (5)", callback_data="simple_rate_5"))
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data=f"shop_detail_{shop_id}"),
        InlineKeyboardButton(text="❌ Anuluj", callback_data="home_0")
    )
    
    await callback.message.answer(
        "⭐ <b>Oceń sklep</b>\n\nJak oceniasz ten sklep ogólnie?",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# KROK 2: Szybki komentarz lub własny
@dp.callback_query(lambda c: c.data.startswith("simple_rate_"))
async def simple_rating_selected(callback: types.CallbackQuery, state: FSMContext):
    rating = int(callback.data.split("_")[2])
    await state.update_data(rating=rating)
    await state.set_state(SimpleReviewStates.comment)
    
    # Sugerowane komentarze na podstawie oceny
    if rating >= 4:
        templates = [
            "✅ Polecam!",
            "⚡ Szybka obsługa",
            "💯 Jak w opisie", 
            "🤝 Miły kontakt",
            "🔥 Super jakość"
        ]
    elif rating == 3:
        templates = [
            "👌 W porządku",
            "📊 Średnio",
            "🤔 Może być",
            "⚖️ Tak sobie"
        ]
    else:
        templates = [
            "👎 Nie polecam",
            "⏰ Długo czekałem",
            "📦 Słaba jakość",
            "💸 Za drogie"
        ]
    
    kb = InlineKeyboardBuilder()
    # Szablony w 2 kolumnach
    for i in range(0, len(templates), 2):
        row = [InlineKeyboardButton(text=templates[i], callback_data=f"template_{i}")]
        if i+1 < len(templates):
            row.append(InlineKeyboardButton(text=templates[i+1], callback_data=f"template_{i+1}"))
        kb.row(*row)
    
    kb.row(
        InlineKeyboardButton(text="✍️ Napisz własny", callback_data="write_custom"),
        InlineKeyboardButton(text="⏭️ Pomiń komentarz", callback_data="skip_comment")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="back_to_rating"),
        InlineKeyboardButton(text="❌ Anuluj", callback_data="home_0")
    )
    
    rating_stars = "⭐" * rating
    await callback.message.answer(
        f"💬 <b>Dodaj komentarz</b>\n\nTwoja ocena: {rating_stars} ({rating}/5)\n\nWybierz gotowy komentarz lub napisz własny:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# KROK 3: Potwierdzenie i zapis
@dp.callback_query(lambda c: c.data.startswith("template_") or c.data == "skip_comment")
async def simple_comment_selected(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    
    if callback.data == "skip_comment":
        comment = None
    else:
        # Mapowanie szablonów
        templates_map = {
            "0": "✅ Polecam!",
            "1": "⚡ Szybka obsługa", 
            "2": "💯 Jak w opisie",
            "3": "🤝 Miły kontakt",
            "4": "🔥 Super jakość",
            # ... więcej szablonów
        }
        template_id = callback.data.split("_")[1]
        comment = templates_map.get(template_id, "Brak komentarza")
    
    await state.update_data(comment=comment)
    await simple_review_save(callback, state)

async def simple_review_save(callback, state):
    """Zapisz uproszczoną opinię"""
    data = await state.get_data()
    shop_id = data.get("shop_id")
    rating = data.get("rating")
    comment = data.get("comment")
    
    user = callback.from_user
    user_name = user.first_name or ""
    user_username = user.username or ""
    
    # Sprawdź blokadę 24h
    from db import user_opinion_last_24h, add_opinion, add_rating, add_nc
    if await user_opinion_last_24h(shop_id, user.id):
        await callback.answer("⏰ Możesz ocenić ten sklep ponownie za 24h", show_alert=True)
        await state.clear()
        return
    
    # Zapisz ocenę i opinię
    await add_rating(shop_id, user.id, rating)
    if comment:
        await add_opinion(shop_id, user.id, comment, None, user_name, user_username)
    
    # Nagroda NC
    nc_reward = 15 if comment else 10
    await add_nc(user.id, nc_reward, reason="opinia")
    
    rating_stars = "⭐" * rating
    success_msg = f"✅ <b>Dziękujemy za opinię!</b>\n\n{rating_stars} ({rating}/5)"
    if comment:
        success_msg += f"\n💬 \"{comment}\""
    success_msg += f"\n\n🎁 Otrzymujesz <b>{nc_reward} NC</b>!"
    
    await callback.message.answer(success_msg, parse_mode="HTML")
    await state.clear()
```

## **2. USPRAWNIENIA NOCNEGO TARGU**

### Uproszczony formularz dodawania (3 kroki):

```python
class FastTargAddStates(StatesGroup):
    basic_info = State()    # Typ + Tytuł + Cena
    details = State()       # Opis + Miasto  
    extras = State()        # Zdjęcie + Dostawa + Potwierdzenie

# KROK 1: Podstawowe informacje
@nocny_targ_router.callback_query(lambda c: c.data == "targ_add_fast")
async def targ_add_fast_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(FastTargAddStates.basic_info)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="🟢 SPRZEDAJĘ 📱💰", callback_data="fast_type_sell"),
        InlineKeyboardButton(text="🔵 KUPUJĘ 💰📱", callback_data="fast_type_buy")
    )
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="nocny_targ"),
        InlineKeyboardButton(text="❌ Anuluj", callback_data="home_0")
    )
    
    await callback.message.answer(
        "➕ <b>Szybkie dodawanie ogłoszenia</b> (1/3)\n\n🎯 Wybierz typ ogłoszenia:",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@nocny_targ_router.callback_query(lambda c: c.data.startswith("fast_type_"))
async def fast_type_selected(callback: types.CallbackQuery, state: FSMContext):
    ad_type = "Sprzedaję" if callback.data == "fast_type_sell" else "Kupię"
    await state.update_data(ad_type=ad_type)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="targ_add_fast"),
        InlineKeyboardButton(text="❌ Anuluj", callback_data="home_0")
    )
    
    await callback.message.answer(
        f"✅ Wybrano: <b>{ad_type}</b>\n\n📝 Teraz napisz w jednej wiadomości:\n\n"
        "<b>TYTUŁ</b>\n"
        "<b>CENA w PLN</b>\n\n"
        "Przykład:\n"
        "<i>iPhone 12 Pro</i>\n"
        "<i>1500</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

@nocny_targ_router.message(FastTargAddStates.basic_info)
async def fast_basic_info(message: types.Message, state: FSMContext):
    lines = message.text.strip().split('\n')
    if len(lines) < 2:
        await message.answer(
            "❌ Podaj dane w dwóch liniach:\n\n"
            "<b>Linia 1:</b> Tytuł ogłoszenia\n"
            "<b>Linia 2:</b> Cena w PLN\n\n"
            "Spróbuj ponownie:",
            parse_mode="HTML"
        )
        return
    
    title = lines[0].strip()
    price_text = lines[1].strip()
    
    # Walidacja
    if len(title) < 3:
        await message.answer("❌ Tytuł musi mieć minimum 3 znaki. Spróbuj ponownie:")
        return
    
    try:
        price = float(price_text.replace(',', '.'))
        if price <= 0:
            raise ValueError
    except ValueError:
        await message.answer("❌ Podaj poprawną cenę (liczbę). Spróbuj ponownie:")
        return
    
    await state.update_data(title=title, price=price)
    await state.set_state(FastTargAddStates.details)
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="fast_back_basic"),
        InlineKeyboardButton(text="❌ Anuluj", callback_data="home_0")
    )
    
    await message.answer(
        f"✅ <b>Zapisano podstawowe dane</b> (2/3)\n\n"
        f"📝 Tytuł: {title}\n"
        f"💰 Cena: {price} PLN\n\n"
        "Teraz napisz w jednej wiadomości:\n\n"
        "<b>OPIS PRODUKTU</b>\n"
        "<b>MIASTO</b>\n\n"
        "Przykład:\n"
        "<i>Stan bardzo dobry, pełne wyposażenie</i>\n"
        "<i>Kraków</i>",
        reply_markup=kb.as_markup(),
        parse_mode="HTML"
    )

# Kategorie produktów do wyboru
KATEGORIE_TARG = {
    "📱": "Elektronika",
    "🚗": "Motoryzacja", 
    "👕": "Odzież",
    "🏠": "Dom & Ogród",
    "📚": "Hobby & Sport",
    "🎮": "Gaming",
    "💄": "Uroda",
    "🍔": "Jedzenie",
    "💼": "Usługi",
    "🔄": "Wymiana"
}

# Lepsze menu główne z statystykami
@nocny_targ_router.callback_query(lambda c: c.data == "nocny_targ_v2")
async def nocny_targ_menu_v2(callback: types.CallbackQuery):
    # Pobierz statystyki
    from db_targ import get_targ_stats
    stats = await get_targ_stats()
    
    aktywne = stats.get('aktywne', 0)
    dzis = stats.get('dzis', 0)
    online = stats.get('online', 0)
    
    kb = InlineKeyboardBuilder()
    
    # Główne akcje - większe przyciski
    kb.row(InlineKeyboardButton(text="🛒 PRZEGLĄDAJ OGŁOSZENIA", callback_data="targ_browse_v2"))
    kb.row(InlineKeyboardButton(text="➕ DODAJ OGŁOSZENIE", callback_data="targ_add_fast"))
    
    # Sekcja użytkownika
    kb.row(
        InlineKeyboardButton(text="📋 Moje (3)", callback_data="targ_my_ads"),
        InlineKeyboardButton(text="🔍 Szukaj", callback_data="targ_search")
    )
    
    # Statystyki i narzędzia
    kb.row(
        InlineKeyboardButton(text="📊 Statystyki", callback_data="targ_stats"),
        InlineKeyboardButton(text="⚙️ Filtry", callback_data="targ_filters")
    )
    
    # Nawigacja
    kb.row(
        InlineKeyboardButton(text="⬅️ Wróć", callback_data="home_0"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0")
    )
    
    opis = (
        f"🏪 <b>NOCNY TARG</b> - Twój marketplace\n\n"
        f"📊 <b>Statystyki Live:</b>\n"
        f"🔥 {aktywne} aktywnych ogłoszeń\n"
        f"📈 +{dzis} nowych dzisiaj\n"
        f"👥 {online} użytkowników online\n\n"
        f"💡 <b>Wskazówki:</b>\n"
        f"• Dodaj zdjęcie - więcej kontaktów\n"
        f"• Dokładny opis zwiększa szanse\n"
        f"• Sprawdź ceny podobnych produktów"
    )
    
    try:
        photo = FSInputFile("nooc2.png")
        await callback.message.answer_photo(
            photo=photo, 
            caption=opis, 
            reply_markup=kb.as_markup(), 
            parse_mode="HTML"
        )
    except Exception:
        await callback.message.answer(opis, reply_markup=kb.as_markup(), parse_mode="HTML")
```

## **3. LEPSZE PRZEGLĄDANIE OGŁOSZEŃ**

```python
@nocny_targ_router.callback_query(lambda c: c.data.startswith("targ_browse_"))
async def targ_browse_v2(callback: types.CallbackQuery):
    # Parsuj parametry paginacji
    page = 0
    if "_" in callback.data:
        parts = callback.data.split("_")
        if len(parts) > 2 and parts[2].isdigit():
            page = int(parts[2])
    
    per_page = 5  # Mniej ogłoszeń na stronę dla lepszej mobilności
    offset = page * per_page
    
    ogloszenia = await get_ogloszenia(limit=per_page, offset=offset)
    total_count = await get_ogloszenia_count()
    total_pages = (total_count + per_page - 1) // per_page
    
    if not ogloszenia:
        await callback.message.answer("😔 Brak ogłoszeń w tej kategorii.")
        return
    
    # Wyświetl ogłoszenia w kompaktowej formie
    messages_sent = []
    for ogl in ogloszenia:
        # Format: typ | miasto | cena | czas
        typ_emoji = "🟢" if ogl[3] == "Sprzedaję" else "🔵" 
        time_ago = get_time_ago(ogl[9])  # data_dodania
        
        text = (
            f"{typ_emoji} <b>{ogl[3]}</b> | 🏠 {ogl[7]} | 💰 {ogl[4]} PLN\n"
            f"📝 {ogl[5][:50]}{'...' if len(ogl[5]) > 50 else ''}\n"
            f"👁️ {ogl[11] or 0} wyświetleń | ⏰ {time_ago}"
        )
        
        kb = InlineKeyboardBuilder()
        kb.row(
            InlineKeyboardButton(text="👁️ Szczegóły", callback_data=f"targ_details_{ogl[0]}"),
            InlineKeyboardButton(text="💬 Kontakt", url=f"https://t.me/{ogl[2]}")
        )
        
        if ogl[6]:  # ma zdjęcie
            await callback.message.answer_photo(
                photo=ogl[6], 
                caption=text, 
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(
                text, 
                reply_markup=kb.as_markup(),
                parse_mode="HTML"
            )
    
    # Nawigacja paginacji
    nav_kb = InlineKeyboardBuilder()
    nav_buttons = []
    
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️", callback_data=f"targ_browse_{page-1}"))
    
    nav_buttons.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="targ_page_info"))
    
    if page < total_pages - 1:
        nav_buttons.append(InlineKeyboardButton(text="➡️", callback_data=f"targ_browse_{page+1}"))
    
    if nav_buttons:
        nav_kb.row(*nav_buttons)
    
    # Dodatkowe opcje
    nav_kb.row(
        InlineKeyboardButton(text="🔍 Filtry", callback_data="targ_filters"),
        InlineKeyboardButton(text="➕ Dodaj", callback_data="targ_add_fast")
    )
    nav_kb.row(
        InlineKeyboardButton(text="⬅️ Menu", callback_data="nocny_targ"),
        InlineKeyboardButton(text="🏠 HOME", callback_data="home_0")
    )
    
    await callback.message.answer(
        f"📋 <b>Strona {page+1} z {total_pages}</b>\n"
        f"📊 Łącznie: {total_count} ogłoszeń",
        reply_markup=nav_kb.as_markup(),
        parse_mode="HTML"
    )

def get_time_ago(datetime_str):
    """Przekształć datetime na czytelny format 'X czasu temu'"""
    from datetime import datetime
    try:
        dt = datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
        now = datetime.now()
        diff = now - dt
        
        if diff.days > 0:
            return f"{diff.days}d temu"
        elif diff.seconds > 3600:
            return f"{diff.seconds//3600}h temu"
        elif diff.seconds > 60:
            return f"{diff.seconds//60}min temu"
        else:
            return "teraz"
    except:
        return "dawno"
```

## **4. SYSTEM STATYSTYK I GAMIFIKACJI**

```python
@dp.callback_query(lambda c: c.data == "user_stats")  
async def user_stats_panel(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    
    # Pobierz statystyki użytkownika
    from db import get_user_stats
    stats = await get_user_stats(user_id)
    
    nc_balance = stats.get('nc_balance', 0)
    opinions_count = stats.get('opinions_count', 0)
    ads_count = stats.get('ads_count', 0)
    referrals = stats.get('referrals', 0)
    
    # Wyznacz poziom użytkownika
    if opinions_count >= 50:
        level = "👑 Mistrz Recenzji"
        level_emoji = "👑"
    elif opinions_count >= 21:
        level = "🥇 Ekspert Opinii"  
        level_emoji = "🥇"
    elif opinions_count >= 6:
        level = "🥈 Doświadczony Recenzent"
        level_emoji = "🥈"
    else:
        level = "🥉 Recenzent Początkujący"
        level_emoji = "🥉"
    
    # Kolejny poziom
    next_threshold = 6 if opinions_count < 6 else (21 if opinions_count < 21 else 50)
    progress = min(opinions_count, next_threshold) if opinions_count < 50 else 50
    
    kb = InlineKeyboardBuilder()
    kb.row(
        InlineKeyboardButton(text="📜 Historia opinii", callback_data="opinion_history"),
        InlineKeyboardButton(text="🏆 Ranking", callback_data="user_ranking")
    )
    kb.row(
        InlineKeyboardButton(text="🎯 Cele", callback_data="user_goals"),
        InlineKeyboardButton(text="💰 Historia NC", callback_data="nc_history")
    )
    kb.row(InlineKeyboardButton(text="⬅️ Wróć", callback_data="home_0"))
    
    text = (
        f"{level_emoji} <b>Twój Profil</b>\n\n"
        f"🎖️ <b>Poziom:</b> {level}\n"
        f"💰 <b>Saldo NC:</b> {nc_balance}\n"
        f"📝 <b>Napisane opinie:</b> {opinions_count}\n"
        f"🛒 <b>Dodane ogłoszenia:</b> {ads_count}\n"
        f"👥 <b>Poleceni użytkownicy:</b> {referrals}\n\n"
        f"📊 <b>Progres do kolejnego poziomu:</b>\n"
        f"{'🟢' * (progress * 10 // next_threshold)}{'⚪' * (10 - progress * 10 // next_threshold)} "
        f"({progress}/{next_threshold})\n\n"
        f"💡 <b>Wskazówka:</b> Pisz więcej szczegółowych opinii, aby zdobywać więcej NC!"
    )
    
    await callback.message.answer(text, reply_markup=kb.as_markup(), parse_mode="HTML")
```

Te ulepszenia znacznie poprawią doświadczenie użytkownika na urządzeniach mobilnych i zwiększą aktywność w bocie! 🚀
