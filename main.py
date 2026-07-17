import asyncio
import random
import time
import threading
import os
from datetime import datetime, timedelta, timezone
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from pymongo import MongoClient

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")

client = MongoClient(MONGO_URI)
db = client["sheep_farm"]
players = db["players"]

ADMIN_ID = 1864104580

RARITIES = {
    "🔵 Редкая": {"items": ["🏡 Деревенская овечка", "🏖️ Пляжная овечка", "💤 Сонная овечка"], "w": 40},
    "🟣 Эпическая": {"items": ["💥 Шизанутая овечка", "🎀 Милая овечка", "🍭 Карамельная овечка"], "w": 30},
    "🟡 Легендарная": {"items": ["🔥 Магмовая овечка", "💎 Бриллиантовая овечка", "🐚 Жемчужная овечка"], "w": 20},
    "🔴 Мифическая": {"items": ["👼 Священная овечка", "👻 Призрачная овечка", "🕯️ Ритуальная овечка"], "w": 10}
}

TREATS = ["🍏 Яблоко", "🫐 Черника", "🍉 Арбуз", "🥭 Манго", "🥝 Киви", "🥥 Кокос"]
TREAT_WEIGHTS = [50, 50, 35, 35, 15, 15]

FRUIT_RARITY = {
    "apple": "rare",
    "blueberry": "rare",
    "watermelon": "epic",
    "mango": "epic",
    "kiwi": "legendary",
    "coconut": "legendary"
}

WOLF_ITEMS = [
    {"name": "🍏 Яблоко", "price": 49},
    {"name": "🫐 Черника", "price": 99},
    {"name": "🍉 Арбуз", "price": 149},
    {"name": "🥭 Манго", "price": 199},
    {"name": "🥝 Киви", "price": 249},
    {"name": "🥥 Кокос", "price": 299},
    {"name": "🍏 Яблоко + 🫐 Черника", "price": 149},
    {"name": "🍉 Арбуз + 🥭 Манго", "price": 399},
    {"name": "🥝 Киви + 🥥 Кокос", "price": 549},
]

WOLF_STEAL_CHANCES = {
    "🐑 Обычная овечка": 0,
    "🏡 Деревенская овечка": 5,
    "🏖️ Пляжная овечка": 5,
    "💤 Сонная овечка": 5,
    "💥 Шизанутая овечка": 15,
    "🎀 Милая овечка": 15,
    "🍭 Карамельная овечка": 15,
    "🔥 Магмовая овечка": 35,
    "💎 Бриллиантовая овечка": 35,
    "🐚 Жемчужная овечка": 35,
    "👼 Священная овечка": 50,
    "👻 Призрачная овечка": 50,
    "🕯️ Ритуальная овечка": 50
}

WOLF_SATIETY_LOSS = {
    "🐑 Обычная овечка": (45, 55),
    "🏡 Деревенская овечка": (35, 45),
    "🏖️ Пляжная овечка": (35, 45),
    "💤 Сонная овечка": (35, 45),
    "💥 Шизанутая овечка": (25, 35),
    "🎀 Милая овечка": (25, 35),
    "🍭 Карамельная овечка": (25, 35),
    "🔥 Магмовая овечка": (15, 25),
    "💎 Бриллиантовая овечка": (15, 25),
    "🐚 Жемчужная овечка": (15, 25),
    "👼 Священная овечка": (5, 15),
    "👻 Призрачная овечка": (5, 15),
    "🕯️ Ритуальная овечка": (5, 15)
}

OWL_ADVICE = [
    {
        "id": "treat_boost",
        "text": "🍭 Угощения сегодня слаще!",
        "effects": {
            "rare": {"chance": 5, "duration": 6 * 3600},
            "epic": {"chance": 10, "duration": 12 * 3600},
            "legendary": {"chance": 15, "duration": 24 * 3600}
        }
    },
    {
        "id": "luck_boost",
        "text": "🎲 Удача на твоей стороне!",
        "effects": {
            "rare": {"chance": 5, "duration": 6 * 3600},
            "epic": {"chance": 10, "duration": 12 * 3600},
            "legendary": {"chance": 15, "duration": 24 * 3600}
        }
    },
    {
        "id": "wolf_immunity",
        "text": "🐺 Странный торговец сегодня не голоден!",
        "effects": {
            "rare": {"duration": 6 * 3600},
            "epic": {"duration": 12 * 3600},
            "legendary": {"duration": 24 * 3600}
        }
    },
    {
        "id": "wool_boost",
        "text": "✂️ Шерсть сегодня ценнее!",
        "effects": {
            "rare": {"duration": 6 * 3600},
            "epic": {"duration": 12 * 3600},
            "legendary": {"duration": 24 * 3600}
        }
    },
    {
        "id": "market_discount",
        "text": "💰 Рынок сегодня переполнен!",
        "effects": {
            "rare": {"discount": 5, "duration": 6 * 3600},
            "epic": {"discount": 10, "duration": 12 * 3600},
            "legendary": {"discount": 15, "duration": 24 * 3600}
        }
    }
]

GROVE_DURATION = 89 * 60

def get_default_user(uid: int):
    now = time.time()
    return {
        "id": uid,
        "skin": "🐑 Обычная овечка",
        "balance": 0,
        "wool": 0,
        "harvest": now,
        "shearing": 0,
        "s_finish": 0,
        "last_active": now,
        "satiety": 100,
        "satiety_update": now,
        "immunity": False,
        "immunity_used": False,
        "wolf_last_offer": 0,
        "wolf_item": None,
        "wolf_active": False,
        "wolf_auto_time": 0,
        "next_visitor": "wolf",
        "owl_active": False,
        "owl_auto_time": 0,
        "owl_advice": None,
        "grove_activity": None,
        "grove_activity_finish": 0,
        "grove_ready": False,
        "grove_loot": None,
        "inv_apple": 0,
        "inv_blueberry": 0,
        "inv_watermelon": 0,
        "inv_mango": 0,
        "inv_kiwi": 0,
        "inv_coconut": 0,
        "daily_streak": 0,
        "daily_last_claim": 0,
        "daily_claimed_today": False,
        "buff_apple_immunity": 0,
        "buff_apple_immunity_expires": 0,
        "buff_apple_wool": 0,
        "buff_blueberry_immunity": 0,
        "buff_blueberry_immunity_expires": 0,
        "buff_blueberry_discount_expires": 0,
        "buff_watermelon_immunity": 0,
        "buff_watermelon_immunity_expires": 0,
        "buff_watermelon_passive_expires": 0,
        "buff_mango_immunity": 0,
        "buff_mango_immunity_expires": 0,
        "buff_mango_wool": 0,
        "buff_kiwi_immunity": 0,
        "buff_kiwi_immunity_expires": 0,
        "buff_kiwi_passive_expires": 0,
        "buff_kiwi_discount_expires": 0,
        "buff_coconut_immunity": 0,
        "buff_coconut_immunity_expires": 0,
        "buff_coconut_wool": 0,
        "buff_coconut_discount_expires": 0
    }

async def get_u(uid: int) -> dict:
    now = time.time()
    user = players.find_one({"id": uid})
    if not user:
        user = get_default_user(uid)
        players.insert_one(user)
    else:
        default = get_default_user(uid)
        for key, value in default.items():
            if key not in user:
                user[key] = value
        
        passed_time = now - user.get("last_active", now)
        hours = min(passed_time / 3600, 6)
        income_per_hour = 0
        skin = user.get("skin", "")
        if any(s in skin for s in ["Шизанутая", "Милая", "Карамельная"]):
            income_per_hour = 1
        elif any(s in skin for s in ["Магмовая", "Бриллиантовая", "Жемчужная"]):
            income_per_hour = 3
        elif any(s in skin for s in ["Священная", "Призрачная", "Ритуальная"]):
            income_per_hour = 5
        if user.get("buff_watermelon_immunity", 0) and now < user.get("buff_watermelon_passive_expires", 0):
            income_per_hour *= 2
        if user.get("buff_kiwi_immunity", 0) and now < user.get("buff_kiwi_passive_expires", 0):
            income_per_hour *= 2
        if hours > 0 and income_per_hour > 0:
            total_income = int(hours * income_per_hour)
            if total_income > 0:
                user["balance"] += total_income
        
        satiety_update = user.get("satiety_update", now)
        time_passed = now - satiety_update
        satiety_regen = int(time_passed // 3600)
        if satiety_regen > 0:
            user["satiety"] = min(100, user.get("satiety", 100) + satiety_regen)
            user["satiety_update"] = now
        
        user["last_active"] = now
        players.update_one({"id": uid}, {"$set": user})
    return user

async def save_u(u: dict):
    players.update_one({"id": u["id"]}, {"$set": u}, upsert=True)

app = Flask(__name__)

@app.route('/')
def h():
    return "OK"

def main_kb(u: dict = None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✂️ Стрижка", callback_data="shear"),
         InlineKeyboardButton("📦 Склад", callback_data="inventory")]
    ])

def get_current_effect(u: dict) -> str:
    now = time.time()
    if u.get("buff_apple_immunity", 0) and now < u.get("buff_apple_immunity_expires", 0):
        return "🍏 Яблоко (иммунитет)"
    if u.get("buff_blueberry_immunity", 0) and now < u.get("buff_blueberry_immunity_expires", 0):
        return "🫐 Черника (иммунитет)"
    if u.get("buff_watermelon_immunity", 0) and now < u.get("buff_watermelon_immunity_expires", 0):
        return "🍉 Арбуз (иммунитет)"
    if u.get("buff_mango_immunity", 0) and now < u.get("buff_mango_immunity_expires", 0):
        return "🥭 Манго (иммунитет)"
    if u.get("buff_kiwi_immunity", 0) and now < u.get("buff_kiwi_immunity_expires", 0):
        return "🥝 Киви (иммунитет)"
    if u.get("buff_coconut_immunity", 0) and now < u.get("buff_coconut_immunity_expires", 0):
        return "🥥 Кокос (иммунитет)"
    return "🚫 Неактивен"

def get_discount(u: dict) -> int:
    now = time.time()
    discount = 0
    if u.get("buff_blueberry_immunity", 0) and now < u.get("buff_blueberry_discount_expires", 0):
        discount += 15
    if u.get("buff_kiwi_immunity", 0) and now < u.get("buff_kiwi_discount_expires", 0):
        discount += 25
    if u.get("buff_coconut_immunity", 0) and now < u.get("buff_coconut_discount_expires", 0):
        discount += 25
    if u.get("buff_market_discount", 0) and now < u.get("buff_market_discount_expires", 0):
        discount += u.get("buff_market_discount", 0)
    return min(discount, 50)

def format_time(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 0:
        seconds = 0
    
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60
    
    parts = []
    if hours > 0:
        if hours == 1:
            parts.append("1 час")
        elif 2 <= hours <= 4:
            parts.append(f"{hours} часа")
        else:
            parts.append(f"{hours} часов")
    
    if minutes > 0:
        if minutes == 1:
            parts.append("1 минута")
        elif 2 <= minutes <= 4:
            parts.append(f"{minutes} минуты")
        else:
            parts.append(f"{minutes} минут")
    
    if hours == 0 and minutes == 0 and secs > 0:
        if secs == 1:
            parts.append("1 секунда")
        elif 2 <= secs <= 4:
            parts.append(f"{secs} секунды")
        else:
            parts.append(f"{secs} секунд")
    
    return " ".join(parts) if parts else "0 секунд"

def get_skin_display(skin: str) -> str:
    return skin.replace(" овечка", "")

def profile_text(u: dict) -> str:
    now = time.time()
    skin = u.get("skin", "🐑 Обычная овечка")
    skin_display = get_skin_display(skin)
    balance = u["balance"]
    satiety = u.get("satiety", 100)
    satiety = max(0, min(100, satiety))
    
    if now >= u["harvest"]:
        timer_line = "✅ <i>Шерсть готова к сбору!</i>"
    else:
        remaining = int(u["harvest"] - now)
        timer_line = f"⏳ <i>Шерсть будет готова к сбору через: {format_time(remaining)}</i>"
    
    return (
        f"<i>{skin_display} | 🌿 {satiety}%</i>\n"
        f"<i>🐾 Копытца: {balance}</i>\n"
        f"{timer_line}"
    )

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐑 Привет! Используй /sheep, чтобы начать.")

# ===== АДМИН КОМАНДЫ =====

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Использование: /give <кол-во> <id>")
        return
    try:
        amount = int(args[0])
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("Кол-во и id должны быть числами.")
        return
    u = await get_u(target_id)
    u["balance"] += amount
    await save_u(u)
    await update.message.reply_text(f"✅ Выдано {amount} 🐾 пользователю {target_id}.")

async def reave_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("Использование: /reave <id>")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Id должен быть числом.")
        return
    players.delete_one({"id": target_id})
    await update.message.reply_text(f"🗑️ Все данные игрока {target_id} удалены.")

async def reave_time_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Использование: /reave_time <user_id>")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")
        return
    u = await get_u(target_id)
    now = time.time()
    u["grove_activity"] = "grove"
    u["grove_activity_finish"] = now + 15
    u["grove_ready"] = False
    u["grove_loot"] = None
    await save_u(u)
    await update.message.reply_text(f"✅ Роща сброшена до 15 секунд для {target_id}!")

async def reave_grove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("❌ Использование: /reave_grove <user_id>")
        return
    try:
        target_id = int(args[0])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")
        return
    u = await get_u(target_id)
    u["grove_activity"] = None
    u["grove_activity_finish"] = 0
    u["grove_ready"] = False
    u["grove_loot"] = None
    await save_u(u)
    await update.message.reply_text(f"✅ Роща полностью сброшена у {target_id}!")

# ===== ОСНОВНЫЕ КОМАНДЫ =====

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    if await check_and_show_visitor(update, context):
        return
    await update.message.reply_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if await check_and_show_visitor(update, context):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продажа шерсти", callback_data="sell")],
        [InlineKeyboardButton("🥚 Покупка яиц", callback_data="eggs")]
    ])
    await update.message.reply_text("<i>🐑 Овечий рынок</i>\n<i>Выбери раздел:</i>", reply_markup=kb, parse_mode="HTML")

# ===== ДНЕВНОЙ БОНУС (ОБНОВЛЁННЫЙ) =====

DAILY_REWARDS = [
    {"day": 1, "type": "coins", "amount": 25},
    {"day": 2, "type": "choice", "items": ["🍏 Яблоко", "🫐 Черника"], "fields": ["inv_apple", "inv_blueberry"]},
    {"day": 3, "type": "coins", "amount": 50},
    {"day": 4, "type": "choice", "items": ["🍉 Арбуз", "🥭 Манго"], "fields": ["inv_watermelon", "inv_mango"]},
    {"day": 5, "type": "coins", "amount": 75},
    {"day": 6, "type": "choice", "items": ["🥝 Киви", "🥥 Кокос"], "fields": ["inv_kiwi", "inv_coconut"]},
    {"day": 7, "type": "piggy", "min": 35, "max": 135}
]

def can_claim_daily(u: dict) -> bool:
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    today_noon = now.replace(hour=10, minute=0, second=0, microsecond=0)
    last_claim = u.get("daily_last_claim", 0)
    last_claim_dt = datetime.fromtimestamp(last_claim, tz=timezone.utc) + timedelta(hours=3)
    return now >= today_noon and last_claim_dt < today_noon

def get_daily_reward(day: int) -> dict:
    idx = (day - 1) % 7
    return DAILY_REWARDS[idx]

async def daily_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_u(update.effective_user.id)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
    ])
    await update.message.reply_text(
        f"<i>🎯 Ежедневный бонус</i>\n<i>⭐️ Серия наград: {u.get('daily_streak', 0)}</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def daily_claim(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    
    last_claim = u.get("daily_last_claim", 0)
    last_claim_dt = datetime.fromtimestamp(last_claim, tz=timezone.utc) + timedelta(hours=3)
    now = datetime.now(timezone.utc) + timedelta(hours=3)
    today_noon = now.replace(hour=10, minute=0, second=0, microsecond=0)
    
    if last_claim_dt < today_noon - timedelta(days=1):
        u["daily_streak"] = 0
        await save_u(u)
    
    if u.get("daily_claimed_today", False) and not can_claim_daily(u):
        await query.answer("💰 Награда уже получена. ⏳ Приходи позже!", show_alert=True)
        return
    
    day = u.get("daily_streak", 0) + 1
    reward = get_daily_reward(day)
    
    if reward["type"] == "coins":
        amount = reward["amount"]
        u["balance"] += amount
        u["daily_streak"] = day
        u["daily_last_claim"] = time.time()
        u["daily_claimed_today"] = True
        await save_u(u)
        await query.answer(f"💰 Награда успешно получена! +{amount} 🐾", show_alert=True)
        await query.edit_message_text(
            f"<i>🎯 Ежедневный бонус</i>\n<i>⭐️ Серия наград: {u.get('daily_streak', 0)}</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
            ]),
            parse_mode="HTML"
        )
        return
    
    elif reward["type"] == "piggy":
        amount = random.randint(reward["min"], reward["max"])
        u["balance"] += amount
        u["daily_streak"] = day
        u["daily_last_claim"] = time.time()
        u["daily_claimed_today"] = True
        await save_u(u)
        await query.answer(f"💰 Награда успешно получена! +{amount} 🐾", show_alert=True)
        await query.edit_message_text(
            f"<i>🎯 Ежедневный бонус</i>\n<i>⭐️ Серия наград: {u.get('daily_streak', 0)}</i>",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
            ]),
            parse_mode="HTML"
        )
        return
    
    # Выбор фрукта
    items = reward["items"]
    fields = reward["fields"]
    buttons = []
    for i in range(len(items)):
        buttons.append(InlineKeyboardButton(items[i], callback_data=f"daily_fruit_{i}"))
    kb = InlineKeyboardMarkup([buttons])
    await query.edit_message_text(
        f"<i>⭐️ Выбери, какую награду ты хочешь получить?</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def daily_fruit_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    
    if u.get("daily_claimed_today", False) and not can_claim_daily(u):
        await query.answer("💰 Награда уже получена. ⏳ Приходи позже!", show_alert=True)
        return
    
    idx = int(query.data.split("_")[-1])
    day = u.get("daily_streak", 0) + 1
    reward = get_daily_reward(day)
    
    if reward["type"] != "choice":
        await query.answer("❌ Ошибка!", show_alert=True)
        return
    
    fruit_name = reward["items"][idx]
    fruit_field = reward["fields"][idx]
    
    u[fruit_field] = u.get(fruit_field, 0) + 1
    u["daily_streak"] = day
    u["daily_last_claim"] = time.time()
    u["daily_claimed_today"] = True
    await save_u(u)
    
    await query.answer(f"💰 Награда успешно получена! +1 {fruit_name}", show_alert=True)
    
    await query.edit_message_text(
        f"<i>🎯 Ежедневный бонус</i>\n<i>⭐️ Серия наград: {u.get('daily_streak', 0)}</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
        ]),
        parse_mode="HTML"
    )

# ===== ВОЛК =====

async def show_wolf_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, edit: bool = True):
    item = u.get("wolf_item")
    if not item:
        if edit and hasattr(update, 'callback_query'):
            await update.callback_query.answer("❌ Ошибка!", show_alert=True)
        return False
    text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
    ])
    if edit and hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)
    return True

async def show_wolf_message(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    item = u.get("wolf_item")
    if not item:
        return
    text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
    ])
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=keyboard
    )

async def wolf_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    item = u.get("wolf_item")
    if not item:
        await query.answer("❌ Ошибка!", show_alert=True)
        return
    if u["balance"] < item["price"]:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    u["balance"] -= item["price"]
    if "+" in item["name"]:
        items = item["name"].split(" + ")
        for it in items:
            if it == "🍏 Яблоко":
                u["inv_apple"] = u.get("inv_apple", 0) + 1
            elif it == "🫐 Черника":
                u["inv_blueberry"] = u.get("inv_blueberry", 0) + 1
            elif it == "🍉 Арбуз":
                u["inv_watermelon"] = u.get("inv_watermelon", 0) + 1
            elif it == "🥭 Манго":
                u["inv_mango"] = u.get("inv_mango", 0) + 1
            elif it == "🥝 Киви":
                u["inv_kiwi"] = u.get("inv_kiwi", 0) + 1
            elif it == "🥥 Кокос":
                u["inv_coconut"] = u.get("inv_coconut", 0) + 1
    else:
        if "Яблоко" in item["name"]:
            u["inv_apple"] = u.get("inv_apple", 0) + 1
        elif "Черника" in item["name"]:
            u["inv_blueberry"] = u.get("inv_blueberry", 0) + 1
        elif "Арбуз" in item["name"]:
            u["inv_watermelon"] = u.get("inv_watermelon", 0) + 1
        elif "Манго" in item["name"]:
            u["inv_mango"] = u.get("inv_mango", 0) + 1
        elif "Киви" in item["name"]:
            u["inv_kiwi"] = u.get("inv_kiwi", 0) + 1
        elif "Кокос" in item["name"]:
            u["inv_coconut"] = u.get("inv_coconut", 0) + 1
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    await query.answer("💰 Товар приобретён!", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def wolf_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    skin = u.get("skin", "🐑 Обычная овечка")
    now = time.time()
    
    if u.get("immunity", False):
        u["immunity"] = False
        u["immunity_used"] = True
        await save_u(u)
        await query.answer("🐺 Странный торговец ушёл в глубь леса!", show_alert=True)
        u["wolf_active"] = False
        u["wolf_item"] = None
        u["next_visitor"] = "owl"
        await save_u(u)
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")
        return
    
    steal_chance = WOLF_STEAL_CHANCES.get(skin, 0)
    if random.random() * 100 < steal_chance:
        old_skin = u["skin"]
        u["skin"] = "🐑 Обычная овечка"
        await save_u(u)
        await query.answer(f"🐺 Странный торговец схватил твою {old_skin} и сбежал!", show_alert=True)
        u["wolf_active"] = False
        u["wolf_item"] = None
        u["next_visitor"] = "owl"
        await save_u(u)
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")
        return
    
    satiety_loss_range = WOLF_SATIETY_LOSS.get(skin, (45, 55))
    satiety_loss = random.randint(satiety_loss_range[0], satiety_loss_range[1])
    u["satiety"] = max(0, u.get("satiety", 100) - satiety_loss)
    await save_u(u)
    await query.answer("🐺 Странный торговец ушёл в глубь леса!", show_alert=True)
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

# ===== СОВА =====

async def show_owl_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, edit: bool = True):
    advice = u.get("owl_advice")
    if not advice:
        if edit and hasattr(update, 'callback_query'):
            await update.callback_query.answer("❌ Ошибка!", show_alert=True)
        return False
    text = f"🦉 Мудрая сова.\n«С меня совет, с тебя оплата»\n{advice['text']}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Отблагодарить", callback_data="owl_pay")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="owl_refuse")]
    ])
    if edit and hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)
    return True

async def show_owl_message(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    advice = u.get("owl_advice")
    if not advice:
        return
    text = f"🦉 Мудрая сова.\n«С меня совет, с тебя оплата»\n{advice['text']}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Отблагодарить", callback_data="owl_pay")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="owl_refuse")]
    ])
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=keyboard
    )

async def owl_pay_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if not u.get("owl_active", False):
        await query.answer("❌ Сова улетела!", show_alert=True)
        return
    text = (
        f"<i>⚡️ Выбери угощение</i>\n"
        f"<i>🍏 {u.get('inv_apple', 0)} | 🫐 {u.get('inv_blueberry', 0)} | 🍉 {u.get('inv_watermelon', 0)}</i>\n"
        f"<i>🥭 {u.get('inv_mango', 0)} | 🥝 {u.get('inv_kiwi', 0)} | 🥥 {u.get('inv_coconut', 0)}</i>"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍏", callback_data="owl_pay_fruit_apple"),
         InlineKeyboardButton("🫐", callback_data="owl_pay_fruit_blueberry"),
         InlineKeyboardButton("🍉", callback_data="owl_pay_fruit_watermelon")],
        [InlineKeyboardButton("🥭", callback_data="owl_pay_fruit_mango"),
         InlineKeyboardButton("🥝", callback_data="owl_pay_fruit_kiwi"),
         InlineKeyboardButton("🥥", callback_data="owl_pay_fruit_coconut")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="owl_back")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard, parse_mode="HTML")

async def owl_pay_fruit(update: Update, context: ContextTypes.DEFAULT_TYPE, fruit_key: str):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if not u.get("owl_active", False):
        await query.answer("❌ Сова улетела!", show_alert=True)
        return
    inv_field = f"inv_{fruit_key}"
    if u.get(inv_field, 0) <= 0:
        await query.answer("❌ Нет этого угощения!", show_alert=True)
        return
    u[inv_field] -= 1
    fruit_rarity = FRUIT_RARITY.get(fruit_key, "rare")
    advice = u.get("owl_advice")
    if advice:
        effects = advice.get("effects", {})
        effect_data = effects.get(fruit_rarity, {})
        if advice["id"] == "treat_boost":
            u["buff_treat_boost"] = effect_data.get("chance", 5)
            u["buff_treat_boost_expires"] = time.time() + effect_data.get("duration", 6 * 3600)
        elif advice["id"] == "luck_boost":
            u["buff_luck_boost"] = effect_data.get("chance", 5)
            u["buff_luck_boost_expires"] = time.time() + effect_data.get("duration", 6 * 3600)
        elif advice["id"] == "wolf_immunity":
            u["buff_wolf_immunity"] = 1
            u["buff_wolf_immunity_expires"] = time.time() + effect_data.get("duration", 6 * 3600)
        elif advice["id"] == "wool_boost":
            u["buff_wool_boost"] = 1
            u["buff_wool_boost_expires"] = time.time() + effect_data.get("duration", 6 * 3600)
        elif advice["id"] == "market_discount":
            u["buff_market_discount"] = effect_data.get("discount", 5)
            u["buff_market_discount_expires"] = time.time() + effect_data.get("duration", 6 * 3600)
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "wolf"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def owl_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    now = time.time()
    
    if not u.get("owl_active", False):
        await query.answer("❌ Сова улетела!", show_alert=True)
        return
    
    if u.get("immunity", False):
        u["immunity"] = False
        u["immunity_used"] = True
        await save_u(u)
        await query.answer("🦉 Мудрая сова улетела в глубь леса!", show_alert=True)
        u["owl_active"] = False
        u["owl_advice"] = None
        u["next_visitor"] = "wolf"
        await save_u(u)
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")
        return
    
    if random.random() < 0.5:
        stolen = random.randint(25, 75)
        u["balance"] = max(0, u["balance"] - stolen)
        await save_u(u)
        await query.answer(f"🦉 Мудрая сова выхватила твои {stolen} 🐾 и сбежала!", show_alert=True)
    else:
        satiety_loss = random.randint(10, 30)
        u["satiety"] = max(0, u.get("satiety", 100) - satiety_loss)
        await save_u(u)
        await query.answer("🦉 Мудрая сова улетела в глубь леса!", show_alert=True)
    
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "wolf"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def owl_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if not u.get("owl_active", False):
        await query.answer("❌ Сова улетела!", show_alert=True)
        await back(update, context)
        return
    await show_owl_inline(update, context, u)

# ===== ВИЗИТОРЫ =====

async def check_and_activate_visitor(u: dict, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None) -> bool:
    now = time.time()
    if u.get("wolf_active", False) or u.get("owl_active", False):
        return True
    next_visitor = u.get("next_visitor", "wolf")
    if next_visitor == "wolf":
        if u.get("wolf_auto_time", 0) == 0:
            u["wolf_auto_time"] = now + random.randint(12 * 3600, 36 * 3600)
            await save_u(u)
            return False
        if now >= u.get("wolf_auto_time", 0):
            item = random.choice(WOLF_ITEMS)
            u["wolf_item"] = item
            u["wolf_active"] = True
            u["wolf_auto_time"] = 0
            await save_u(u)
            if update and context:
                await show_wolf_message(update, context, u)
            return True
    elif next_visitor == "owl":
        if u.get("owl_auto_time", 0) == 0:
            u["owl_auto_time"] = now + random.randint(12 * 3600, 36 * 3600)
            await save_u(u)
            return False
        if now >= u.get("owl_auto_time", 0):
            advice = random.choice(OWL_ADVICE)
            u["owl_advice"] = advice
            u["owl_active"] = True
            u["owl_auto_time"] = 0
            await save_u(u)
            if update and context:
                await show_owl_message(update, context, u)
            return True
    return False

async def check_and_show_visitor(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user_id = update.effective_user.id
    u = await get_u(user_id)
    await check_and_activate_visitor(u, update, context)
    if u.get("wolf_active", False):
        await show_wolf_inline(update, context, u, edit=False)
        return True
    elif u.get("owl_active", False):
        await show_owl_inline(update, context, u, edit=False)
        return True
    return False

async def check_visitor_on_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    query = update.callback_query
    u = await get_u(query.from_user.id)
    await check_and_activate_visitor(u, update, context)
    if u.get("wolf_active", False):
        await show_wolf_inline(update, context, u)
        return True
    elif u.get("owl_active", False):
        await show_owl_inline(update, context, u)
        return True
    return False

# ===== ИНВЕНТАРЬ =====

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    text = (
        f"<i>📦 Склад</i>\n"
        f"<i>🍏 {u.get('inv_apple', 0)} | 🫐 {u.get('inv_blueberry', 0)} | 🍉 {u.get('inv_watermelon', 0)}</i>\n"
        f"<i>🥭 {u.get('inv_mango', 0)} | 🥝 {u.get('inv_kiwi', 0)} | 🥥 {u.get('inv_coconut', 0)}</i>"
    )
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡️ Использовать", callback_data="use_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

async def use_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    effect = get_current_effect(u)
    text = f"<i>⚡️ Использовать угощение</i>\n<i>Активный эффект: {effect}</i>"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍏", callback_data="use_apple"),
         InlineKeyboardButton("🫐", callback_data="use_blueberry"),
         InlineKeyboardButton("🍉", callback_data="use_watermelon")],
        [InlineKeyboardButton("🥭", callback_data="use_mango"),
         InlineKeyboardButton("🥝", callback_data="use_kiwi"),
         InlineKeyboardButton("🥥", callback_data="use_coconut")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="inventory")]
    ])
    await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

async def use_fruit(update: Update, context: ContextTypes.DEFAULT_TYPE, fruit_key: str, inv_field: str):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    if u.get(inv_field, 0) <= 0:
        await query.answer("❌ Нет угощения!", show_alert=True)
        return
    u[inv_field] -= 1
    now = time.time()
    
    satiety_restore = {
        "apple": 25,
        "blueberry": 25,
        "watermelon": 50,
        "mango": 50,
        "kiwi": 75,
        "coconut": 75
    }.get(fruit_key, 0)
    u["satiety"] = min(100, u.get("satiety", 100) + satiety_restore)
    
    u["immunity"] = True
    u["immunity_used"] = False
    
    u["buff_apple_immunity"] = 0
    u["buff_apple_immunity_expires"] = 0
    u["buff_apple_wool"] = 0
    u["buff_blueberry_immunity"] = 0
    u["buff_blueberry_immunity_expires"] = 0
    u["buff_blueberry_discount_expires"] = 0
    u["buff_watermelon_immunity"] = 0
    u["buff_watermelon_immunity_expires"] = 0
    u["buff_watermelon_passive_expires"] = 0
    u["buff_mango_immunity"] = 0
    u["buff_mango_immunity_expires"] = 0
    u["buff_mango_wool"] = 0
    u["buff_kiwi_immunity"] = 0
    u["buff_kiwi_immunity_expires"] = 0
    u["buff_kiwi_passive_expires"] = 0
    u["buff_kiwi_discount_expires"] = 0
    u["buff_coconut_immunity"] = 0
    u["buff_coconut_immunity_expires"] = 0
    u["buff_coconut_wool"] = 0
    u["buff_coconut_discount_expires"] = 0
    
    if fruit_key == "apple":
        u["buff_apple_immunity"] = 1
        u["buff_apple_wool"] = 1
    elif fruit_key == "blueberry":
        u["buff_blueberry_immunity"] = 1
        u["buff_blueberry_discount_expires"] = now + 6 * 3600
    elif fruit_key == "watermelon":
        u["buff_watermelon_immunity"] = 1
        u["buff_watermelon_passive_expires"] = now + 24 * 3600
    elif fruit_key == "mango":
        u["buff_mango_immunity"] = 1
        u["buff_mango_wool"] = 1
    elif fruit_key == "kiwi":
        u["buff_kiwi_immunity"] = 1
        u["buff_kiwi_passive_expires"] = now + 24 * 3600
        u["buff_kiwi_discount_expires"] = now + 12 * 3600
    elif fruit_key == "coconut":
        u["buff_coconut_immunity"] = 1
        u["buff_coconut_wool"] = 1
        u["buff_coconut_discount_expires"] = now + 12 * 3600
    
    await save_u(u)
    await query.answer("⭐️ Угощение активировано!", show_alert=True)
    await use_menu(update, context)

async def use_apple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "apple", "inv_apple")

async def use_blueberry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "blueberry", "inv_blueberry")

async def use_watermelon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "watermelon", "inv_watermelon")

async def use_mango(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "mango", "inv_mango")

async def use_kiwi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "kiwi", "inv_kiwi")

async def use_coconut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "coconut", "inv_coconut")

# ===== РЫНОК =====

async def eggs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 399 * (100 - discount) // 100
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Открыть яйцо", callback_data="open_egg")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(
        f"<i>🥚 Покупка яиц</i>\n<i>Курс: 1 🥚 = {price} 🐾</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def open_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 399 * (100 - discount) // 100
    if u["balance"] < price:
        await query.answer(f"❌ Нужно {price} 🐾", show_alert=True)
        return
    u["balance"] -= price
    r_l = list(RARITIES.keys())
    rarity = random.choices(r_l, weights=[RARITIES[k]["w"] for k in r_l])[0]
    u["skin"] = random.choice(RARITIES[rarity]["items"])
    await save_u(u)
    await query.answer(f"🥚 Выпала: {u['skin']}", show_alert=True)
    await eggs_menu(update, context)

async def sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продать шерсть", callback_data="sell_confirm")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(
        "<i>💰 Продажа шерсти</i>\n<i>Курс: 1 🧶 = 10 🐾</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def sell_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    if u["wool"] <= 0:
        await query.answer("❌ Нет шерсти!", show_alert=True)
        return
    v = u["wool"] * 10
    u["balance"] += v
    u["wool"] = 0
    await save_u(u)
    await query.answer(f"💰 Продано! +{v} 🐾", show_alert=True)
    await sell_menu(update, context)

async def market_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продажа шерсти", callback_data="sell")],
        [InlineKeyboardButton("🥚 Покупка яиц", callback_data="eggs")]
    ])
    await query.edit_message_text(
        "<i>🐑 Овечий рынок</i>\n<i>Выбери раздел:</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def shear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    now = time.time()
    
    satiety = u.get("satiety", 100)
    if satiety < 5:
        await query.answer("❌ Овечка голодна!", show_alert=True)
        return
    
    if u.get("grove_activity") == "grove":
        finish = u.get("grove_activity_finish", 0)
        if now < finish:
            await query.answer("🌳 Овечка занята. ⏳ Дождись её возвращения!", show_alert=True)
            return
    
    wool_boost = u.get("buff_wool_boost", 0) and now < u.get("buff_wool_boost_expires", 0)
    mango_boost = u.get("buff_mango_wool", 0) and now < u.get("buff_mango_immunity_expires", 0)
    coconut_boost = u.get("buff_coconut_wool", 0) and now < u.get("buff_coconut_immunity_expires", 0)
    apple_boost = u.get("buff_apple_wool", 0)
    
    if u["shearing"]:
        if now >= u["s_finish"]:
            if wool_boost or mango_boost or coconut_boost:
                gain = random.randint(15, 25)
            else:
                gain = random.randint(5, 15)
            if apple_boost:
                gain += 5
            
            u["wool"] += gain
            u["shearing"] = 0
            u["harvest"] = now + 12 * 3600
            u["satiety"] = max(0, u.get("satiety", 100) - random.randint(5, 10))
            
            u["buff_apple_wool"] = 0
            u["buff_mango_wool"] = 0
            u["buff_coconut_wool"] = 0
            
            await save_u(u)
            await query.answer(f"🐑 Овечка успешно пострижена! Получено: {gain} 🧶", show_alert=True)
            await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")
        else:
            rem = int(u["s_finish"] - now)
            actual_rem = rem - 60
            if actual_rem < 0:
                actual_rem = 0
            time_str = format_time(actual_rem)
            await query.answer(f"✂️ Стрижём овечку. ⏳ Процесс займет: {time_str}", show_alert=True)
    elif now < u["harvest"]:
        rem = int(u["harvest"] - now)
        time_str = format_time(rem)
        await query.answer(f"❌ Шерсть ещё не готова! Подожди: {time_str}", show_alert=True)
    else:
        u["shearing"] = 1
        u["s_finish"] = now + 300
        await save_u(u)
        await query.answer("✂️ Стрижём овечку. ⏳ Процесс займет: 4 минуты 59 секунд", show_alert=True)

# ===== РОЩА =====

async def grove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    
    if await check_and_show_visitor(update, context):
        return
    
    now = time.time()
    
    # Проверяем, есть ли не забранная шерсть
    if u.get("shearing", 0) == 0 and u.get("wool", 0) > 0:
        # Если есть шерсть, но стрижка не активна - даём забрать
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍃 Отправить гулять", callback_data="grove_start")]
        ])
        await update.message.reply_text(
            f"<i>🌳 Лесная роща</i>\n\n"
            f"<i>Отличное место для выгула овечки, тут можно найти удивительные вещи!</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return
    
    if u.get("grove_ready", False) and u.get("grove_loot"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍃 Забрать лут", callback_data="grove_collect")]
        ])
        await update.message.reply_text(
            f"<i>🌳 Лесная роща</i>\n\n"
            f"<i>Овечка вернулась и принесла тебе интересные вещи!</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return
    
    satiety = u.get("satiety", 100)
    if satiety < 10:
        await update.message.reply_text("❌ Овечка голодна!")
        return
    
    # Всегда показываем главный экран с кнопкой
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍃 Отправить гулять", callback_data="grove_start")]
    ])
    await update.message.reply_text(
        f"<i>🌳 Лесная роща</i>\n\n"
        f"<i>Отличное место для выгула овечки, тут можно найти удивительные вещи!</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def grove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    u = await get_u(user_id)
    
    now = time.time()
    
    # Проверяем, не занята ли овечка стрижкой
    if u.get("shearing", 0) == 1:
        rem = int(u["s_finish"] - now)
        if rem > 0:
            await query.answer("✂️ Овечка занята. ⏳ Дождись её возвращения!", show_alert=True)
            return
    
    # Проверяем, есть ли не забранная шерсть
    if u.get("wool", 0) > 0:
        await query.answer("✂️ Сначала забери шерсть от стрижки!", show_alert=True)
        return
    
    satiety = u.get("satiety", 100)
    if satiety < 10:
        await query.answer("❌ Овечка голодна!", show_alert=True)
        return
    
    # Проверяем, активна ли уже прогулка
    if u.get("grove_activity") == "grove":
        finish = u.get("grove_activity_finish", 0)
        remaining = finish - now
        if remaining > 0:
            await query.answer("🌳 Овечка уже гуляет! ⏳ Подожди её возвращения!", show_alert=True)
            return
    
    duration = GROVE_DURATION
    u["grove_activity"] = "grove"
    u["grove_activity_finish"] = now + duration
    u["grove_ready"] = False
    u["grove_loot"] = None
    await save_u(u)
    
    time_str = format_time(duration)
    
    await query.edit_message_text(
        f"<i>🌳 Лесная роща</i>\n\n"
        f"<i>Овечка гуляет и обещает вернуться через: {time_str}</i>",
        parse_mode="HTML"
    )
    await query.answer("🌳 Овечка отправилась гулять!", show_alert=True)

async def generate_grove_loot(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    if u.get("grove_ready", False) and u.get("grove_loot"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍃 Забрать лут", callback_data="grove_collect")]
        ])
        await update.message.reply_text(
            f"<i>🌳 Лесная роща</i>\n\n"
            f"<i>Овечка вернулась и принесла тебе интересные вещи!</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return
    
    coins = random.randint(5, 35)
    roll = random.random() * 100
    loot = None
    
    if roll < 70:
        loot = {"type": "coins", "value": coins}
    elif roll < 85:
        fruit_name, fruit_field = random.choice([("🍏 Яблоко", "inv_apple"), ("🫐 Черника", "inv_blueberry")])
        loot = {"type": "fruit", "name": fruit_name, "field": fruit_field}
    elif roll < 95:
        fruit_name, fruit_field = random.choice([("🍉 Арбуз", "inv_watermelon"), ("🥭 Манго", "inv_mango")])
        loot = {"type": "fruit", "name": fruit_name, "field": fruit_field}
    else:
        fruit_name, fruit_field = random.choice([("🥝 Киви", "inv_kiwi"), ("🥥 Кокос", "inv_coconut")])
        loot = {"type": "fruit", "name": fruit_name, "field": fruit_field}
    
    u["grove_loot"] = loot
    u["grove_ready"] = True
    u["grove_activity"] = None
    u["grove_activity_finish"] = 0
    await save_u(u)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍃 Забрать лут", callback_data="grove_collect")]
    ])
    await update.message.reply_text(
        f"<i>🌳 Лесная роща</i>\n\n"
        f"<i>Овечка вернулась и принесла тебе интересные вещи!</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def grove_collect(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    loot = u.get("grove_loot")
    
    if not loot or not u.get("grove_ready", False):
        await query.answer("❌ Ничего нет!", show_alert=True)
        return
    
    if loot["type"] == "coins":
        u["balance"] += loot["value"]
        result_msg = f"🌳 Успешно получено! +{loot['value']} 🐾"
    else:
        u[loot["field"]] = u.get(loot["field"], 0) + 1
        result_msg = f"🌳 Успешно получено! +{loot['name']}"
    
    u["satiety"] = max(0, u.get("satiety", 100) - random.randint(10, 15))
    
    u["grove_ready"] = False
    u["grove_loot"] = None
    u["grove_activity"] = None
    u["grove_activity_finish"] = 0
    await save_u(u)
    
    await query.answer(result_msg, show_alert=True)
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍃 Отправить гулять", callback_data="grove_start")]
    ])
    await query.edit_message_text(
        f"<i>🌳 Лесная роща</i>\n\n"
        f"<i>Отличное место для выгула овечки, тут можно найти удивительные вещи!</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

# ===== ОСНОВНАЯ ФУНКЦИЯ =====

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("grove", grove_cmd))
    application.add_handler(CommandHandler("daily", daily_cmd))
    
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("reave", reave_cmd))
    application.add_handler(CommandHandler("reave_time", reave_time_cmd))
    application.add_handler(CommandHandler("reave_grove", reave_grove_cmd))
    
    application.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    application.add_handler(CallbackQueryHandler(use_menu, pattern="^use_menu$"))
    application.add_handler(CallbackQueryHandler(use_apple, pattern="^use_apple$"))
    application.add_handler(CallbackQueryHandler(use_blueberry, pattern="^use_blueberry$"))
    application.add_handler(CallbackQueryHandler(use_watermelon, pattern="^use_watermelon$"))
    application.add_handler(CallbackQueryHandler(use_mango, pattern="^use_mango$"))
    application.add_handler(CallbackQueryHandler(use_kiwi, pattern="^use_kiwi$"))
    application.add_handler(CallbackQueryHandler(use_coconut, pattern="^use_coconut$"))
    application.add_handler(CallbackQueryHandler(wolf_buy, pattern="^wolf_buy$"))
    application.add_handler(CallbackQueryHandler(wolf_refuse, pattern="^wolf_refuse$"))
    application.add_handler(CallbackQueryHandler(owl_pay_menu, pattern="^owl_pay$"))
    application.add_handler(CallbackQueryHandler(owl_refuse, pattern="^owl_refuse$"))
    application.add_handler(CallbackQueryHandler(owl_back, pattern="^owl_back$"))
    application.add_handler(CallbackQueryHandler(eggs_menu, pattern="^eggs$"))
    application.add_handler(CallbackQueryHandler(open_egg, pattern="^open_egg$"))
    application.add_handler(CallbackQueryHandler(sell_menu, pattern="^sell$"))
    application.add_handler(CallbackQueryHandler(sell_confirm, pattern="^sell_confirm$"))
    application.add_handler(CallbackQueryHandler(market_main, pattern="^market_main$"))
    application.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(shear, pattern="^shear$"))
    application.add_handler(CallbackQueryHandler(daily_claim, pattern="^daily_claim$"))
    application.add_handler(CallbackQueryHandler(daily_fruit_choice, pattern="^daily_fruit_"))
    application.add_handler(CallbackQueryHandler(grove_start, pattern="^grove_start$"))
    application.add_handler(CallbackQueryHandler(grove_collect, pattern="^grove_collect$"))
    
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "apple"), pattern="^owl_pay_fruit_apple$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "blueberry"), pattern="^owl_pay_fruit_blueberry$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "watermelon"), pattern="^owl_pay_fruit_watermelon$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "mango"), pattern="^owl_pay_fruit_mango$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "kiwi"), pattern="^owl_pay_fruit_kiwi$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "coconut"), pattern="^owl_pay_fruit_coconut$"))
    
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False), daemon=True).start()
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
