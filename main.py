from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from flask import Flask
import asyncio
import sqlite3
import time
import os
import threading

BOT_TOKEN = os.getenv("BOT_TOKEN")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = Flask(__name__)

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
        [InlineKeyboardButton(text="🎲 Создать раунд", callback_data="create_round"),
         InlineKeyboardButton(text="💰 Покупка класса", callback_data="buy_class")]
    ])

def round_setup_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="1️⃣ Один", callback_data="players_1"),
         InlineKeyboardButton(text="2️⃣ Два", callback_data="players_2")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile"),
         InlineKeyboardButton(text="➡️ Вперёд", callback_data="forward_more")]
    ])

def game_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌳 Отправиться в лес", callback_data="go_forest")],
        [InlineKeyboardButton(text="🍗 Съесть", callback_data="eat"),
         InlineKeyboardButton(text="🪵 Огонь", callback_data="fire")]
    ])

def forest_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🍃 За ресурсами", callback_data="forest_resources")],
        [InlineKeyboardButton(text="🪵 Рубка дерева", callback_data="forest_wood")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_game")]
    ])

def death_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💎 Возродиться", callback_data="revive")]
    ])

def double_registration_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👤 Присоединиться", callback_data="double_join")]
    ])

# ====== НОВАЯ УПРОЩЁННАЯ ЛОГИКА ======
def check_status(user_id):
    """Универсальная проверка статуса игрока"""
    player = get_player(user_id)
    satiety = player[3]
    in_round = player[4]
    round_start_time = player[5]
    is_dead = player[6]
    fire_level = player[16]
    fire_update_time = player[17]
    day_count = player[18]
    is_night = player[19]
    night_start_time = player[20]
    
    # Если не в игре или мёртв
    if in_round == 0 or is_dead == 1:
        return {"status": "idle", "player": player}
    
    current_time = int(time.time())
    
    # ====== ОГОНЬ ======
    if fire_update_time == 0:
        update_player(user_id, fire_update_time=current_time)
        fire_update_time = current_time
    
    minutes_passed_fire = (current_time - fire_update_time) // 60
    if minutes_passed_fire > 0:
        new_fire = max(0, fire_level - minutes_passed_fire)
        update_player(user_id, fire_level=new_fire, fire_update_time=current_time)
        fire_level = new_fire
        
        if fire_level == 0:
            update_player(user_id, is_dead=1, death_time=current_time)
            return {"status": "dead", "player": get_player(user_id)}
    
    # ====== СЫТОСТЬ ======
    minutes_passed_satiety = (current_time - round_start_time) // 60
    if minutes_passed_satiety > 0:
        new_satiety = max(0, satiety - minutes_passed_satiety)
        update_player(user_id, satiety=new_satiety)
        satiety = new_satiety
        
        if satiety == 0:
            update_player(user_id, is_dead=1, death_time=current_time)
            return {"status": "dead", "player": get_player(user_id)}
    
    # ====== ДЕНЬ/НОЧЬ ======
    night_message = None
    if is_night == 0:
        time_in_day = current_time - round_start_time
        if time_in_day >= 150 and time_in_day < 180:
            night_message = "🌙 Ночь скоро наступит!"
        elif time_in_day >= 180:
            update_player(user_id, is_night=1, night_start_time=current_time)
            is_night = 1
            night_message = "🌙 Наступила ночь!"
    else:
        time_in_night = current_time - night_start_time
        if time_in_night >= 90:
            new_day = day_count + 1
            update_player(user_id, is_night=0, day_count=new_day, round_start_time=current_time)
            is_night = 0
            day_count = new_day
            night_message = f"🌞 Наступил {new_day}-й день!"
    
    return {
        "status": "alive",
        "player": get_player(user_id),
        "night_message": night_message
    }

# ====== ЭКРАН СМЕРТИ ======
async def show_death_screen(message, user_id):
    player = get_player(user_id)
    class_name, level, gems, death_time = player[1], player[2], player[3], player[7]
    current_time = int(time.time())
    
    if current_time - death_time >= 30:
        update_player(user_id, in_round=0, is_dead=0, satiety=10, round_start_time=0, death_time=0,
                      in_forest=0, forest_action="", forest_start_time=0, metal=0, food=0, wood=0,
                      fire_level=100, fire_update_time=current_time, day_count=1, is_night=0,
                      night_start_time=0, game_mode='single')
        text = f"👤 {class_name} | {level}\n💎 Самоцветы: {gems}\n⏳ Находится в раунде"
        await message.answer(text, reply_markup=profile_keyboard())
    else:
        remaining = 30 - (current_time - death_time)
        await message.answer(f"💀 Вы проиграли!\n⏳ У вас {remaining} секунд.", reply_markup=death_keyboard())

# ====== ОБРАБОТКА ЛЕСА ======
async def handle_forest_check(message, user_id):
    player = get_player(user_id)
    forest_action = player[9]
    forest_start_time = player[10]
    remaining = max(0, 300 - (int(time.time()) - forest_start_time))
    
    if remaining == 0:
        if forest_action == "resources":
            update_player(user_id, metal=player[11]+5, food=player[12]+1, in_forest=0, forest_action="", forest_start_time=0)
            await message.answer("🌳 Поиск окончен! 🔩 +5 металла, 🍗 +1 еда", reply_markup=game_keyboard())
        else:
            update_player(user_id, wood=player[13]+5, in_forest=0, forest_action="", forest_start_time=0)
            await message.answer("🌳 Рубка окончена! 🪵 +5 брёвен", reply_markup=game_keyboard())
    else:
        minutes = remaining // 60
        secs = remaining % 60
        action_text = "Гуляем и добываем ресурсы" if forest_action == "resources" else "Рубим деревья"
        await message.answer(f"🌳 {action_text}. ⏳ Вернёмся через: {minutes} мин. {secs} сек", reply_markup=game_keyboard())

# ====== КОМАНДА /PROFILE ======
@dp.message(Command("profile"))
async def profile_handler(message: types.Message):
    user_id = message.from_user.id
    result = check_status(user_id)
    player = result["player"]
    
    if result["status"] == "dead":
        await show_death_screen(message, user_id)
        return
    
    if result["status"] == "idle":
        class_name, level, gems = player[1], player[2], player[3]
        await message.answer(f"👤 {class_name} | {level}\n💎 Самоцветы: {gems}\n⏳ Находится в раунде",
                            reply_markup=profile_keyboard())
        return
    
    # Живой игрок в раунде
    if result.get("night_message"):
        await message.answer(result["night_message"])
    
    if player[8] == 1:  # in_forest
        await handle_forest_check(message, user_id)
        return
    
    day_text = "Первый" if player[18] == 1 else f"{player[18]}-й"
    time_text = "Ночь" if player[19] == 1 else "День"
    emoji = "🌙" if player[19] == 1 else "🌞"
    await message.answer(f"{emoji} {day_text} {time_text} | X1\n🌿 Сытость | {player[3]}/10",
                        reply_markup=game_keyboard())

# ====== ВСЕ КНОПКИ ======
@dp.callback_query(lambda call: call.data == "buy_class")
async def buy_class(call: types.CallbackQuery):
    await call.answer("⏳ Функция находится на стадии разработки!", show_alert=True)

@dp.callback_query(lambda call: call.data == "create_round")
async def create_round(call: types.CallbackQuery):
    user_id = call.from_user.id
    if call.message.chat.type in ["group", "supergroup"]:
        await call.message.edit_text("🎲 Создание раунда\nВыбери количество игроков:", reply_markup=round_setup_keyboard())
        await call.answer()
    else:
        if get_player(user_id)[4] == 1:
            await call.answer("⏳ Вы уже в игре!", show_alert=True)
            return
        current_time = int(time.time())
        update_player(user_id, in_round=1, round_start_time=current_time, satiety=10, is_dead=0,
                      metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time,
                      day_count=1, is_night=0, night_start_time=0, game_mode='single')
        await call.message.edit_text("🌞 Первый день | X1\n🌿 Сытость | 10/10", reply_markup=game_keyboard())
        await call.answer()

@dp.callback_query(lambda call: call.data == "back_to_profile")
async def back_to_profile(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    player = result["player"]
    
    if result["status"] == "dead":
        await show_death_screen(call.message, user_id)
        await call.answer()
        return
    
    if result["status"] == "idle":
        class_name, level, gems = player[1], player[2], player[3]
        await call.message.edit_text(f"👤 {class_name} | {level}\n💎 Самоцветы: {gems}\n⏳ Находится в раунде",
                                     reply_markup=profile_keyboard())
        await call.answer()
        return
    
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    
    if player[8] == 1:
        await handle_forest_check(call.message, user_id)
        await call.answer()
        return
    
    day_text = "Первый" if player[18] == 1 else f"{player[18]}-й"
    time_text = "Ночь" if player[19] == 1 else "День"
    emoji = "🌙" if player[19] == 1 else "🌞"
    await call.message.edit_text(f"{emoji} {day_text} {time_text} | X1\n🌿 Сытость | {player[3]}/10",
                                 reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "forward_more")
async def forward_more(call: types.CallbackQuery):
    await call.answer("⏳ Другое количество игроков на стадии разработки!", show_alert=True)

@dp.callback_query(lambda call: call.data == "players_1")
async def players_one(call: types.CallbackQuery):
    user_id = call.from_user.id
    current_time = int(time.time())
    update_player(user_id, in_round=1, round_start_time=current_time, satiety=10, is_dead=0,
                  metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time,
                  day_count=1, is_night=0, night_start_time=0, game_mode='single')
    await call.message.edit_text("🌞 Первый день | X1\n🌿 Сытость | 10/10", reply_markup=game_keyboard())
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
    await call.message.edit_text(f"🎲 Регистрация\n⏳ У вас 30 секунд\n1. {name}",
                                 reply_markup=double_registration_keyboard())
    double_mode_data[chat_id] = {"players": [user_id], "start_time": int(time.time())}
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
        current_time = int(time.time())
        for uid in players_list:
            update_player(uid, in_round=1, round_start_time=current_time, satiety=10, is_dead=0,
                          metal=0, food=0, wood=0, fire_level=100, fire_update_time=current_time,
                          day_count=1, is_night=0, night_start_time=0, game_mode='double')
        await call.message.edit_text("🌞 Первый день | X1\n🌿 Сытость | 10/10", reply_markup=game_keyboard())
        del double_mode_data[chat_id]
    
    await call.answer()

# ====== ИГРОВЫЕ И ЛЕСНЫЕ КНОПКИ ======
@dp.callback_query(lambda call: call.data == "go_forest")
async def go_forest(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    if result["status"] != "alive":
        await show_death_screen(call.message, user_id) if result["status"] == "dead" else None
        await call.answer()
        return
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    await call.message.edit_text("🌳 Чем займёмся в лесу?\nВыбери действие:", reply_markup=forest_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "eat")
async def eat(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    if result["status"] != "alive":
        await show_death_screen(call.message, user_id) if result["status"] == "dead" else None
        await call.answer()
        return
    
    player = result["player"]
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    
    if player[12] == 0:  # food
        await call.answer("🍗 Недостаточно еды!", show_alert=True)
        return
    
    new_food = player[12] - 1
    new_satiety = min(10, player[3] + 2)
    update_player(user_id, food=new_food, satiety=new_satiety)
    await call.answer("🍗 Съедена 1 порция!", show_alert=True)
    
    # Обновляем экран
    result = check_status(user_id)
    player = result["player"]
    day_text = "Первый" if player[18] == 1 else f"{player[18]}-й"
    time_text = "Ночь" if player[19] == 1 else "День"
    emoji = "🌙" if player[19] == 1 else "🌞"
    await call.message.edit_text(f"{emoji} {day_text} {time_text} | X1\n🌿 Сытость | {player[3]}/10",
                                 reply_markup=game_keyboard())

@dp.callback_query(lambda call: call.data == "fire")
async def fire(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    if result["status"] != "alive":
        await show_death_screen(call.message, user_id) if result["status"] == "dead" else None
        await call.answer()
        return
    
    player = result["player"]
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    
    if player[13] == 0:  # wood
        await call.answer(f"🪵 У тебя нет дров! 🔥 Текущий уровень: {player[16]}%", show_alert=True)
        return
    
    new_fire = min(100, player[16] + 5)
    new_wood = player[13] - 1
    update_player(user_id, fire_level=new_fire, wood=new_wood, fire_update_time=int(time.time()))
    await call.answer(f"🪵 Ты закинул бревно в огонь! 🔥 Текущий уровень: {new_fire}%", show_alert=True)
    
    # Обновляем экран
    result = check_status(user_id)
    player = result["player"]
    day_text = "Первый" if player[18] == 1 else f"{player[18]}-й"
    time_text = "Ночь" if player[19] == 1 else "День"
    emoji = "🌙" if player[19] == 1 else "🌞"
    await call.message.edit_text(f"{emoji} {day_text} {time_text} | X1\n🌿 Сытость | {player[3]}/10",
                                 reply_markup=game_keyboard())

@dp.callback_query(lambda call: call.data == "forest_resources")
async def forest_resources(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    if result["status"] != "alive":
        await show_death_screen(call.message, user_id) if result["status"] == "dead" else None
        await call.answer()
        return
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    
    current_time = int(time.time())
    update_player(user_id, in_forest=1, forest_action="resources", forest_start_time=current_time)
    await call.message.edit_text("🌳 Гуляем и добываем ресурсы. ⏳ Вернёмся через: 4 мин. 59 сек",
                                 reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "forest_wood")
async def forest_wood(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    if result["status"] != "alive":
        await show_death_screen(call.message, user_id) if result["status"] == "dead" else None
        await call.answer()
        return
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    
    current_time = int(time.time())
    update_player(user_id, in_forest=1, forest_action="wood", forest_start_time=current_time)
    await call.message.edit_text("🪵 Рубим деревья. ⏳ Вернёмся через: 4 мин. 59 сек",
                                 reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "back_to_game")
async def back_to_game(call: types.CallbackQuery):
    user_id = call.from_user.id
    result = check_status(user_id)
    if result["status"] != "alive":
        await show_death_screen(call.message, user_id) if result["status"] == "dead" else None
        await call.answer()
        return
    
    player = result["player"]
    if result.get("night_message"):
        await call.message.answer(result["night_message"])
    
    day_text = "Первый" if player[18] == 1 else f"{player[18]}-й"
    time_text = "Ночь" if player[19] == 1 else "День"
    emoji = "🌙" if player[19] == 1 else "🌞"
    await call.message.edit_text(f"{emoji} {day_text} {time_text} | X1\n🌿 Сытость | {player[3]}/10",
                                 reply_markup=game_keyboard())
    await call.answer()

@dp.callback_query(lambda call: call.data == "revive")
async def revive(call: types.CallbackQuery):
    await call.answer("⏳ Функция находится на стадии разработки!", show_alert=True)

# ====== FLASK ДЛЯ RENDER ======
@app.route('/')
def index():
    return "Bot is running!", 200

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ====== ЗАПУСК ======
async def main():
    print("✅ Бот успешно запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    threading.Thread(target=run_flask, daemon=True).start()
    asyncio.run(main())
