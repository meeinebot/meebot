from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import asyncio
import sqlite3
import time
import os

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ====== БАЗА ДАННЫХ ======
conn = sqlite3.connect("players.db", check_same_thread=False)
cursor = conn.cursor()
cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        user_id INTEGER PRIMARY KEY,
        username TEXT DEFAULT '',
        class_name TEXT DEFAULT 'Разведчик',
        level INTEGER DEFAULT 0,
        gems INTEGER DEFAULT 0,
        satiety INTEGER DEFAULT 10,
        in_round INTEGER DEFAULT 0,
        round_start_time INTEGER DEFAULT 0,
        is_dead INTEGER DEFAULT 0,
        death_time INTEGER DEFAULT 0,
        in_forest INTEGER DEFAULT 0,
        forest_action TEXT DEFAULT '',
        forest_start_time INTEGER DEFAULT 0,
        metal INTEGER DEFAULT 0,
        food INTEGER DEFAULT 0,
        wood INTEGER DEFAULT 0,
        fire_level INTEGER DEFAULT 100,
        fire_update_time INTEGER DEFAULT 0,
        day_count INTEGER DEFAULT 1,
        is_night INTEGER DEFAULT 0,
        night_start_time INTEGER DEFAULT 0,
        game_mode TEXT DEFAULT 'single'
    )
""")
conn.commit()

# ====== ВРЕМЕННЫЕ ДАННЫЕ ДЛЯ ДВОЙНОГО РЕЖИМА ======
double_mode_data = {}

def get_player(user_id):
    cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    if result:
        return result
    else:
        current_time = int(time.time())
        cursor.execute("INSERT INTO players (user_id, fire_level, fire_update_time) VALUES (?, 100, ?)", (user_id, current_time))
        conn.commit()
        cursor.execute("SELECT * FROM players WHERE user_id = ?", (user_id,))
        return cursor.fetchone()

def update_player(user_id, **kwargs):
    updates = []
    params = []
    for key, value in kwargs.items():
        updates.append(f"{key} = ?")
        params.append(value)
    
    if updates:
        params.append(user_id)
        cursor.execute(f"UPDATE players SET {', '.join(updates)} WHERE user_id = ?", params)
        conn.commit()

# ====== КЛАВИАТУРЫ ======
def profile_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎲 Создать раунд", callback_data="create_round"),
            InlineKeyboardButton(text="💰 Покупка класса", callback_data="buy_class")
        ]
    ])

def round_setup_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣ Один", callback_data="players_1"),
            InlineKeyboardButton(text="2️⃣ Два", callback_data="players_2")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile"),
            InlineKeyboardButton(text="➡️ Вперёд", callback_data="forward_more")
        ]
    ])

def game_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌳 Отправиться в лес", callback_data="go_forest")
        ],
        [
            InlineKeyboardButton(text="🍗 Съесть", callback_data="eat"),
            InlineKeyboardButton(text="🪵 Огонь", callback_data="fire")
        ]
    ])

def forest_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🍃 За ресурсами", callback_data="forest_resources")
        ],
        [
            InlineKeyboardButton(text="🪵 Рубка дерева", callback_data="forest_wood")
        ],
        [
            InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_game")
        ]
    ])

def death_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="💎 Возродиться", callback_data="revive")
        ]
    ])

def double_registration_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="👤 Присоединиться", callback_data="double_join")
        ]
    ])

# ====== ПРОВЕРКА ОГНЯ ======
def check_fire(user_id):
    player = get_player(user_id)
    fire_level = player[16]
    fire_update_time = player[17]
    
    if fire_level <= 0:
        return "dead"
    
    current_time = int(time.time())
    minutes_passed = (current_time - fire_update_time) // 60
    
    if minutes_passed > 0:
        new_fire = max(0, fire_level - minutes_passed)
        update_player(user_id, fire_level=new_fire, fire_update_time=current_time)
        
        if new_fire == 0:
            return "dead"
    return "alive"

# ====== ПРОВЕРКА СЫТОСТИ И ДНЯ/НОЧИ ======
def check_game_status(user_id):
    player = get_player(user_id)
    satiety = player[3]
    in_round = player[4]
    round_start_time = player[5]
    is_dead = player[6]
    day_count = player[18]
    is_night = player[19]
    night_start_time = player[20]
    
    if in_round == 0 or is_dead == 1:
        return "not_in_round"
    
    current_time = int(time.time())
    
    # Проверка сытости
    minutes_passed = (current_time - round_start_time) // 60
    if minutes_passed > 0:
        new_satiety = max(0, satiety - minutes_passed)
        update_player(user_id, satiety=new_satiety)
        if new_satiety == 0:
            update_player(user_id, is_dead=1, death_time=current_time)
            return "dead"
    
    # Проверка дня/ночи
    if is_night == 0:
        time_in_day = current_time - round_start_time
        if time_in_day >= 150:
            return "night_soon"
        if time_in_day >= 180:
            update_player(user_id, is_night=1, night_start_time=current_time)
            return "night_start"
    else:
        time_in_night = current_time - night_start_time
        if time_in_night >= 90:
            update_player(user_id, is_night=0, day_count=day_count+1, round_start_time=current_time)
            return "day_start"
    
    return "alive"

# ====== ЭКРАН СМЕРТИ ======
async def show_death_screen(message, user_id):
    player = get_player(user_id)
    class_name, level, gems, death_time = player[1], player[2], player[3], player[7]
    
    current_time = int(time.time())
    time_passed = current_time - death_time
    
    if time_passed >= 30:
        update_player(user_id, in_round=0, is_dead=0, satiety=10, round_start_time=0, death_time=0, in_forest=0, forest_action="", forest_start_time=0, metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time, day_count=1, is_night=0, night_start_time=0, game_mode='single')
        text = (
            f"👤 {class_name} | {level}\n"
            f"💎 Самоцветы: {gems}\n"
            f"⏳ Находится в раунде"
        )
        await message.answer(text, reply_markup=profile_keyboard())
    else:
        remaining = 30 - time_passed
        text = f"💀 Вы проиграли!\n⏳ У вас {remaining} секунд."
        await message.answer(text, reply_markup=death_keyboard())

# ====== ОБРАБОТКА ЛЕСА ======
async def handle_forest_check(message, user_id):
    player = get_player(user_id)
    forest_action, forest_start_time = player[9], player[10]
    
    current_time = int(time.time())
    time_passed = current_time - forest_start_time
    remaining = max(0, 300 - time_passed)
    
    if remaining == 0:
        if forest_action == "resources":
            update_player(user_id, metal=player[11]+5, food=player[12]+1, in_forest=0, forest_action="", forest_start_time=0)
            text = "🌳 Поиск окончен! 🔩 +5 металла, 🍗 +1 еда"
        else:
            update_player(user_id, wood=player[13]+5, in_forest=0, forest_action="", forest_start_time=0)
            text = "🌳 Рубка окончена! 🪵 +5 брёвен"
        await message.answer(text, reply_markup=game_keyboard())
    else:
        minutes = remaining // 60
        secs = remaining % 60
        if forest_action == "resources":
            text = f"🌳 Гуляем и добываем ресурсы. ⏳ Вернёмся через: {minutes} мин. {secs} сек"
        else:
            text = f"🪵 Рубим деревья. ⏳ Вернёмся через: {minutes} мин. {secs} сек"
        await message.answer(text, reply_markup=game_keyboard())

# ====== КОМАНДА /PROFILE ======
@dp.message(Command("profile"))
async def profile_handler(message: types.Message):
    user_id = message.from_user.id
    
    player = get_player(user_id)
    class_name, level, gems, satiety, in_round, round_start_time, is_dead, death_time, in_forest, forest_action, forest_start_time, metal, food, wood, fire_level, fire_update_time, day_count, is_night, night_start_time, game_mode = player[1], player[2], player[3], player[4], player[5], player[6], player[7], player[8], player[9], player[10], player[11], player[12], player[13], player[14], player[15], player[16], player[17], player[18], player[19], player[20]
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(message, user_id)
        return
    
    if in_forest == 1:
        await handle_forest_check(message, user_id)
        return
    
    status = check_game_status(user_id)
    
    if in_round == 1 and is_dead == 0:
        if status == "dead":
            await show_death_screen(message, user_id)
            return
        elif status == "night_soon":
            await message.answer("🌙 Ночь скоро наступит!")
        
        day_text = "Первый" if day_count == 1 else f"{day_count}-й"
        time_text = "Ночь" if is_night == 1 else "День"
        day_emoji = "🌙" if is_night == 1 else "🌞"
        
        text = (
            f"{day_emoji} {day_text} {time_text} | X1\n"
            f"🌿 Сытость | {satiety}/10"
        )
        await message.answer(text, reply_markup=game_keyboard())
    
    elif is_dead == 1:
        await show_death_screen(message, user_id)
    
    else:
        text = (
            f"👤 {class_name} | {level}\n"
            f"💎 Самоцветы: {gems}\n"
            f"⏳ Находится в раунде"
        )
        await message.answer(text, reply_markup=profile_keyboard())

# ====== ОБРАБОТКА КНОПОК ======
@dp.callback_query(lambda call: call.data == "buy_class")
async def buy_class(call: types.CallbackQuery):
    await call.answer("⏳ Функция находится на стадии разработки!", show_alert=True)

@dp.callback_query(lambda call: call.data == "create_round")
async def create_round(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.message.chat.type in ["group", "supergroup"]:
        await call.message.edit_text(
            "🎲 Создание раунда\nВыбери количество игроков:",
            reply_markup=round_setup_keyboard()
        )
        await call.answer()
    else:
        player = get_player(user_id)
        if player[4] == 1:
            await call.answer("⏳ Вы уже в игре!", show_alert=True)
            return
        
        current_time = int(time.time())
        update_player(user_id, in_round=1, round_start_time=current_time, satiety=10, is_dead=0, metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time, day_count=1, is_night=0, night_start_time=0, game_mode='single')
        
        text = "🌞 Первый день | X1\n🌿 Сытость | 10/10"
        await call.message.edit_text(text, reply_markup=game_keyboard())
        await call.answer()

@dp.callback_query(lambda call: call.data == "back_to_profile")
async def back_to_profile(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    player = get_player(user_id)
    class_name, level, gems, satiety, in_round, round_start_time, is_dead, death_time, in_forest, forest_action, forest_start_time, metal, food, wood, fire_level, fire_update_time, day_count, is_night, night_start_time, game_mode = player[1], player[2], player[3], player[4], player[5], player[6], player[7], player[8], player[9], player[10], player[11], player[12], player[13], player[14], player[15], player[16], player[17], player[18], player[19], player[20]
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    if in_forest == 1:
        await handle_forest_check(call.message, user_id)
        await call.answer()
        return
    
    if in_round == 1 and is_dead == 0:
        status = check_game_status(user_id)
        if status == "dead":
            await show_death_screen(call.message, user_id)
            await call.answer()
            return
        elif status == "night_soon":
            await call.message.answer("🌙 Ночь скоро наступит!")
        
        day_text = "Первый" if day_count == 1 else f"{day_count}-й"
        time_text = "Ночь" if is_night == 1 else "День"
        day_emoji = "🌙" if is_night == 1 else "🌞"
        
        text = (
            f"{day_emoji} {day_text} {time_text} | X1\n"
            f"🌿 Сытость | {satiety}/10"
        )
        await call.message.edit_text(text, reply_markup=game_keyboard())
        await call.answer()
    elif is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
    else:
        text = (
            f"👤 {class_name} | {level}\n"
            f"💎 Самоцветы: {gems}\n"
            f"⏳ Находится в раунде"
        )
        await call.message.edit_text(text, reply_markup=profile_keyboard())
        await call.answer()

@dp.callback_query(lambda call: call.data == "forward_more")
async def forward_more(call: types.CallbackQuery):
    await call.answer("⏳ Другое количество игроков на стадии разработки!", show_alert=True)

@dp.callback_query(lambda call: call.data == "players_1")
async def players_one(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    current_time = int(time.time())
    update_player(user_id, in_round=1, round_start_time=current_time, satiety=10, is_dead=0, metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time, day_count=1, is_night=0, night_start_time=0, game_mode='single')
    
    text = "🌞 Первый день | X1\n🌿 Сытость | 10/10"
    await call.message.edit_text(text, reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "players_2")
async def players_two(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if call.message.chat.type not in ["group", "supergroup"]:
        await call.answer("👥 Двойной режим только в группах!", show_alert=True)
        return
    
    if chat_id in double_mode_data:
        await call.answer("⏳ Регистрация уже идёт!", show_alert=True)
        return
    
    user = await bot.get_chat(user_id)
    name = user.first_name or str(user_id)
    
    await call.message.edit_text(
        f"🎲 Регистрация\n⏳ У вас 30 секунд\n1. {name}",
        reply_markup=double_registration_keyboard()
    )
    
    double_mode_data[chat_id] = {"players": [user_id], "start_time": int(time.time()), "message_id": call.message.message_id}
    await call.answer()

@dp.callback_query(lambda call: call.data == "double_join")
async def double_join(call: types.CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    
    if chat_id not in double_mode_data:
        await call.answer("⏳ Регистрация не найдена!", show_alert=True)
        return
    
    if user_id in double_mode_data[chat_id]["players"]:
        await call.answer("👤 Ты уже присоединился!", show_alert=True)
        return
    
    double_mode_data[chat_id]["players"].append(user_id)
    
    players_list = double_mode_data[chat_id]["players"]
    text = "🎲 Регистрация\n⏳ У вас 30 секунд\n"
    for i, uid in enumerate(players_list, 1):
        try:
            user = await bot.get_chat(uid)
            name = user.first_name or str(uid)
        except:
            name = str(uid)
        text += f"{i}. {name}\n"
    
    await call.message.edit_text(text, reply_markup=double_registration_keyboard())
    
    if len(players_list) == 2:
        for uid in players_list:
            current_time = int(time.time())
            update_player(uid, in_round=1, round_start_time=current_time, satiety=10, is_dead=0, metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time, day_count=1, is_night=0, night_start_time=0, game_mode='double')
        
        await call.message.edit_text(
            "🌞 Первый день | X1\n🌿 Сытость | 10/10",
            reply_markup=game_keyboard()
        )
        del double_mode_data[chat_id]
    
    await call.answer()

# ====== ИГРОВЫЕ КНОПКИ ======
@dp.callback_query(lambda call: call.data == "go_forest")
async def go_forest(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    player = get_player(user_id)
    is_dead = player[6]
    
    if is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    status = check_game_status(user_id)
    if status == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    elif status == "night_soon":
        await call.message.answer("🌙 Ночь скоро наступит!")
    
    text = "🌳 Чем займёмся в лесу?\nВыбери действие:"
    await call.message.edit_text(text, reply_markup=forest_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "eat")
async def eat(call: types.CallbackQuery):
    user_id = call.from_user.id
    player = get_player(user_id)
    satiety, food, is_dead = player[3], player[12], player[6]
    
    if is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    status = check_game_status(user_id)
    if status == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    elif status == "night_soon":
        await call.message.answer("🌙 Ночь скоро наступит!")
    
    if food == 0:
        await call.answer("🍗 Недостаточно еды!", show_alert=True)
        return
    
    new_food = food - 1
    new_satiety = min(10, satiety + 2)
    update_player(user_id, food=new_food, satiety=new_satiety)
    await call.answer(f"🍗 Съедена 1 порция!", show_alert=True)
    
    player = get_player(user_id)
    satiety, day_count, is_night = player[3], player[18], player[19]
    day_text = "Первый" if day_count == 1 else f"{day_count}-й"
    time_text = "Ночь" if is_night == 1 else "День"
    day_emoji = "🌙" if is_night == 1 else "🌞"
    
    text = (
        f"{day_emoji} {day_text} {time_text} | X1\n"
        f"🌿 Сытость | {satiety}/10"
    )
    await call.message.edit_text(text, reply_markup=game_keyboard())

@dp.callback_query(lambda call: call.data == "fire")
async def fire(call: types.CallbackQuery):
    user_id = call.from_user.id
    player = get_player(user_id)
    wood, fire_level, is_dead = player[13], player[14], player[6]
    
    if is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    status = check_game_status(user_id)
    if status == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    elif status == "night_soon":
        await call.message.answer("🌙 Ночь скоро наступит!")
    
    if wood == 0:
        await call.answer(f"🪵 У тебя нет дров! 🔥 Текущий уровень: {fire_level}%", show_alert=True)
        return
    
    new_fire = min(100, fire_level + 5)
    new_wood = wood - 1
    update_player(user_id, fire_level=new_fire, wood=new_wood, fire_update_time=int(time.time()))
    await call.answer(f"🪵 Ты закинул бревно в огонь! 🔥 Текущий уровень: {new_fire}%", show_alert=True)
    
    player = get_player(user_id)
    satiety, day_count, is_night = player[3], player[18], player[19]
    day_text = "Первый" if day_count == 1 else f"{day_count}-й"
    time_text = "Ночь" if is_night == 1 else "День"
    day_emoji = "🌙" if is_night == 1 else "🌞"
    
    text = (
        f"{day_emoji} {day_text} {time_text} | X1\n"
        f"🌿 Сытость | {satiety}/10"
    )
    await call.message.edit_text(text, reply_markup=game_keyboard())

# ====== ЛЕСНЫЕ КНОПКИ ======
@dp.callback_query(lambda call: call.data == "forest_resources")
async def forest_resources(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    player = get_player(user_id)
    is_dead = player[6]
    
    if is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    status = check_game_status(user_id)
    if status == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    elif status == "night_soon":
        await call.message.answer("🌙 Ночь скоро наступит!")
    
    current_time = int(time.time())
    update_player(user_id, in_forest=1, forest_action="resources", forest_start_time=current_time)
    
    text = "🌳 Гуляем и добываем ресурсы. ⏳ Вернёмся через: 4 мин. 59 сек"
    await call.message.edit_text(text, reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "forest_wood")
async def forest_wood(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    player = get_player(user_id)
    is_dead = player[6]
    
    if is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    status = check_game_status(user_id)
    if status == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    elif status == "night_soon":
        await call.message.answer("🌙 Ночь скоро наступит!")
    
    current_time = int(time.time())
    update_player(user_id, in_forest=1, forest_action="wood", forest_start_time=current_time)
    
    text = "🪵 Рубим деревья. ⏳ Вернёмся через: 4 мин. 59 сек"
    await call.message.edit_text(text, reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "back_to_game")
async def back_to_game(call: types.CallbackQuery):
    user_id = call.from_user.id
    
    player = get_player(user_id)
    is_dead = player[6]
    
    if is_dead == 1:
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    fire_status = check_fire(user_id)
    if fire_status == "dead":
        update_player(user_id, is_dead=1, death_time=int(time.time()))
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    status = check_game_status(user_id)
    if status == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    elif status == "night_soon":
        await call.message.answer("🌙 Ночь скоро наступит!")
    
    player = get_player(user_id)
    satiety, day_count, is_night = player[3], player[18], player[19]
    day_text = "Первый" if day_count == 1 else f"{day_count}-й"
    time_text = "Ночь" if is_night == 1 else "День"
    day_emoji = "🌙" if is_night == 1 else "🌞"
    
    text = (
        f"{day_emoji} {day_text} {time_text} | X1\n"
        f"🌿 Сытость | {satiety}/10"
    )
    await call.message.edit_text(text, reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "revive")
async def revive(call: types.CallbackQuery):
    await call.answer("⏳ Функция находится на стадии разработки!", show_alert=True)

async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
