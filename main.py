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

STEAL_CONFIG = {
    "🐑 Обычная овечка": {"coins": 50, "sheep": 0},
    "🏡 Деревенская овечка": {"coins": 45, "sheep": 5},
    "🏖️ Пляжная овечка": {"coins": 45, "sheep": 5},
    "💤 Сонная овечка": {"coins": 45, "sheep": 5},
    "💥 Шизанутая овечка": {"coins": 35, "sheep": 15},
    "🎀 Милая овечка": {"coins": 35, "sheep": 15},
    "🍭 Карамельная овечка": {"coins": 35, "sheep": 15},
    "🔥 Магмовая овечка": {"coins": 15, "sheep": 35},
    "💎 Бриллиантовая овечка": {"coins": 15, "sheep": 35},
    "🐚 Жемчужная овечка": {"coins": 15, "sheep": 35},
    "👼 Священная овечка": {"coins": 0, "sheep": 50},
    "👻 Призрачная овечка": {"coins": 0, "sheep": 50},
    "🕯️ Ритуальная овечка": {"coins": 0, "sheep": 50}
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
        "last_active": now,
        "satiety": 100,
        "satiety_update": now,
        "immunity": False,
        "level": 0,
        "xp": 0,
        "pending_level_up": False,
        "talents": {
            "golden_shears": 0,
            "luxury_wool": 0,
            "appetizing_feed": 0
        },
        "inv_flashlight": 1,
        "flashlight_durability": 100,
        "flashlight_equipped": False,
        "flashlight_broken": False,
        "wolf_last_offer": 0,
        "wolf_item": None,
        "wolf_active": False,
        "wolf_auto_time": 0,
        "next_visitor": "wolf",
        "owl_active": False,
        "owl_auto_time": 0,
        "owl_advice": None,
        "bear_active": False,
        "bear_auto_time": 0,
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
        feed_level = user.get("talents", {}).get("appetizing_feed", 0)
        base_time = 3600
        bonus = feed_level * 900
        time_per_unit = base_time + bonus
        drain_per_tick = 3 if feed_level >= 10 else 1
        time_for_one = time_per_unit * drain_per_tick
        satiety_regen = int(time_passed // time_for_one)
        if satiety_regen > 0:
            user["satiety"] = max(0, user.get("satiety", 100) - satiety_regen * drain_per_tick)
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
        [InlineKeyboardButton("💩 Убрать", callback_data="clean"),
         InlineKeyboardButton("✂️ Стрижка", callback_data="shear")],
        [InlineKeyboardButton("📦 Склад", callback_data="inventory"),
         InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory_main")]
    ])

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

def xp_to_next(level: int) -> int:
    if level >= 30:
        return float('inf')
    return 25 * level + 25

def add_xp(u: dict, amount: int) -> int:
    old_level = u.get("level", 0)
    if old_level >= 30:
        return old_level
    u["xp"] = u.get("xp", 0) + amount
    while u.get("level", 0) < 30 and u["xp"] >= xp_to_next(u.get("level", 0)):
        u["xp"] -= xp_to_next(u.get("level", 0))
        u["level"] = u.get("level", 0) + 1
        u["pending_level_up"] = True
    return old_level

def profile_text(u: dict) -> str:
    now = time.time()
    skin = u.get("skin", "🐑 Обычная овечка")
    skin_emoji = skin.split()[0] if skin.split() else "🐑"
    level = u.get("level", 0)
    balance = u["balance"]
    satiety = u.get("satiety", 100)
    satiety = max(0, min(100, satiety))
    if now >= u["harvest"]:
        timer_line = "✅ Шерсть готова к сбору!"
    else:
        remaining = int(u["harvest"] - now)
        timer_line = f"⏳ Следующий сбор через: {format_time(remaining)}"
    return (
        f"{skin_emoji} Уровень: {level} | 🌿 {satiety}%\n"
        f"🐾 Копытца: {balance}\n"
        f"{timer_line}"
    )

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐑 Привет! Используй /sheep, чтобы начать.")

async def clean(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("⏳ Функция на стадии разработки!", show_alert=True)

async def show_level_up(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, level: int):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡️ Изучить талант", callback_data="learn_talent")]
    ])
    await update.message.reply_text(
        f"🎉 Musya достиг {level} уровня! +1 🍏 Яблоко\n"
        f"⭐️ Нажми, чтобы изучить талант!",
        reply_markup=kb
    )

async def learn_talent(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if not u.get("pending_level_up", False):
        await query.answer("❌ Талант уже изучен!", show_alert=True)
        return
    talents = ["golden_shears", "luxury_wool", "appetizing_feed"]
    talent_names = {
        "golden_shears": "✂️ Золотые ножницы",
        "luxury_wool": "🧶 Люксовая шерсть",
        "appetizing_feed": "🍏 Аппетитный корм"
    }
    available = [t for t in talents if u.get("talents", {}).get(t, 0) < 10]
    if not available:
        await query.answer("❌ Все таланты уже изучены до 10 уровня!", show_alert=True)
        return
    chosen = random.choice(available)
    old_level = u["talents"].get(chosen, 0)
    u["talents"][chosen] = old_level + 1
    u["pending_level_up"] = False
    await save_u(u)
    new_level = u["talents"][chosen]
    await query.answer(f"⚡️ Изучен новый талант! {talent_names[chosen]}. (Ур. {new_level}/10)", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    if await check_and_show_visitor(update, context):
        return
    if u.get("pending_level_up", False):
        await show_level_up(update, context, u, u.get("level", 0))
        return
    await update.message.reply_text(profile_text(u), reply_markup=main_kb(u))

# ===== ИНВЕНТАРЬ =====

async def inventory_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    items = []
    if u.get("inv_flashlight", 0) > 0:
        items.append(f"• 🔦 {u['inv_flashlight']} Фонарик")
    items_text = "\n".join(items) if items else "✨ Пусто"
    text = f"🎒 Инвентарь\n{items_text}\n"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("✨ Пусто", callback_data="inventory_empty")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])
    await query.edit_message_text(text, reply_markup=kb)

async def inventory_empty(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    buttons = []
    if u.get("inv_flashlight", 0) > 0 and not u.get("flashlight_broken", False):
        buttons.append([InlineKeyboardButton("🔦 Фонарик", callback_data="inventory_wear_flashlight")])
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="inventory_back")])
    text = "🎒 Что хочешь одеть?\n"
    kb = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text, reply_markup=kb)

async def inventory_wear_flashlight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u.get("flashlight_broken", False):
        await query.answer("🔦 Фонарик сломан. 🐻 Обратись к ремесленнику!", show_alert=True)
        return
    u["flashlight_equipped"] = True
    await save_u(u)
    text = "🎒 Что хочешь одеть?\n"
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔦 100%", callback_data="inventory_toggle_flashlight")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="inventory_wear_back")]
    ])
    await query.edit_message_text(text, reply_markup=kb)

async def inventory_toggle_flashlight(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    current = u.get("flashlight_equipped", False)
    u["flashlight_equipped"] = not current
    await save_u(u)
    await inventory_main(update, context)

async def inventory_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await inventory_main(update, context)

async def inventory_wear_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await inventory_main(update, context)

# ===== СКЛАД =====

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    wool = u.get("wool", 0)
    fruits = [
        ("🍏 Яблоко", u.get("inv_apple", 0)),
        ("🫐 Черника", u.get("inv_blueberry", 0)),
        ("🍉 Арбуз", u.get("inv_watermelon", 0)),
        ("🥭 Манго", u.get("inv_mango", 0)),
        ("🥝 Киви", u.get("inv_kiwi", 0)),
        ("🥥 Кокос", u.get("inv_coconut", 0))
    ]
    buttons = []
    row = []
    for name, count in fruits:
        if count > 0:
            row.append(InlineKeyboardButton(f"{name} {count}", callback_data="fruit_info"))
            if len(row) == 2:
                buttons.append(row)
                row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Назад", callback_data="back")])
    text = f"📦 Склад\n🧶 Шерсть: {wool}\n"
    kb = InlineKeyboardMarkup(buttons)
    await query.edit_message_text(text, reply_markup=kb)

# ===== РЫНОК =====

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продажа шерсти", callback_data="sell")],
        [InlineKeyboardButton("🥚 Покупка яиц", callback_data="eggs")]
    ])
    await update.message.reply_text("🐑 Овечий рынок\nВыбери раздел:", reply_markup=kb)

async def sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if await check_visitor_on_action(update, context):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продать шерсть", callback_data="sell_confirm")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text("💰 Продажа шерсти\nКурс: 1 🧶 = 10 🐾", reply_markup=kb)

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
    old_level = add_xp(u, random.randint(3, 5))
    await save_u(u)
    await query.answer(f"💰 Продано! +{v} 🐾", show_alert=True)
    await sell_menu(update, context)

async def eggs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    price = 499
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Открыть яйцо", callback_data="open_egg")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(f"🥚 Покупка яиц\nКурс: 1 🥚 = {price} 🐾", reply_markup=kb)

async def open_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    price = 499
    if u["balance"] < price:
        await query.answer(f"❌ Нужно {price} 🐾", show_alert=True)
        return
    u["balance"] -= price
    r_l = list(RARITIES.keys())
    rarity = random.choices(r_l, weights=[RARITIES[k]["w"] for k in r_l])[0]
    u["skin"] = random.choice(RARITIES[rarity]["items"])
    old_level = add_xp(u, random.randint(5, 10))
    await save_u(u)
    await query.answer(f"🥚 Выпала: {u['skin']}", show_alert=True)
    await eggs_menu(update, context)

async def market_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продажа шерсти", callback_data="sell")],
        [InlineKeyboardButton("🥚 Покупка яиц", callback_data="eggs")]
    ])
    await query.edit_message_text("🐑 Овечий рынок\nВыбери раздел:", reply_markup=kb)

# ===== ЕЖЕДНЕВНЫЙ БОНУС =====

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
        f"🎯 Ежедневный бонус\n⭐️ Серия наград: {u.get('daily_streak', 0)}",
        reply_markup=kb
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
        old_level = add_xp(u, random.randint(3, 5))
        await save_u(u)
        await query.answer(f"💰 Награда успешно получена! +{amount} 🐾", show_alert=True)
        await query.edit_message_text(
            f"🎯 Ежедневный бонус\n⭐️ Серия наград: {u.get('daily_streak', 0)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
            ])
        )
        return
    elif reward["type"] == "piggy":
        amount = random.randint(reward["min"], reward["max"])
        u["balance"] += amount
        u["daily_streak"] = day
        u["daily_last_claim"] = time.time()
        u["daily_claimed_today"] = True
        old_level = add_xp(u, random.randint(3, 5))
        await save_u(u)
        await query.answer(f"💰 Награда успешно получена! +{amount} 🐾", show_alert=True)
        await query.edit_message_text(
            f"🎯 Ежедневный бонус\n⭐️ Серия наград: {u.get('daily_streak', 0)}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
            ])
        )
        return
    items = reward["items"]
    fields = reward["fields"]
    buttons = []
    for i in range(len(items)):
        buttons.append(InlineKeyboardButton(items[i], callback_data=f"daily_fruit_{i}"))
    kb = InlineKeyboardMarkup([buttons])
    await query.edit_message_text(
        "⭐️ Выбери, какую награду ты хочешь получить?",
        reply_markup=kb
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
    old_level = add_xp(u, random.randint(3, 5))
    await save_u(u)
    await query.answer(f"💰 Награда успешно получена! +1 {fruit_name}", show_alert=True)
    await query.edit_message_text(
        f"🎯 Ежедневный бонус\n⭐️ Серия наград: {u.get('daily_streak', 0)}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Получить награду", callback_data="daily_claim")]
        ])
    )

# ===== ВОЛК =====

async def show_wolf_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, edit: bool = True):
    item = u.get("wolf_item")
    if not item:
        if edit and hasattr(update, 'callback_query'):
            await update.callback_query.answer("❌ Ошибка!", show_alert=True)
        return False
    text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
    if u.get("flashlight_equipped", False) and not u.get("flashlight_broken", False):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔦 Припугнуть", callback_data="wolf_scare")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
        ])
    else:
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
    if u.get("flashlight_equipped", False) and not u.get("flashlight_broken", False):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔦 Припугнуть", callback_data="wolf_scare")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
        ])
    else:
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
    old_level = add_xp(u, random.randint(5, 10))
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    await query.answer("💰 Товар приобретён!", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def wolf_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    skin = u.get("skin", "🐑 Обычная овечка")
    if u.get("immunity", False):
        u["immunity"] = False
        u["immunity_used"] = True
        await save_u(u)
        await query.answer("🐺 Странный торговец ушёл в глубь леса!", show_alert=True)
        u["wolf_active"] = False
        u["wolf_item"] = None
        u["next_visitor"] = "owl"
        await save_u(u)
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))
        return
    config = STEAL_CONFIG.get(skin, {"coins": 0, "sheep": 0})
    roll = random.random() * 100
    if roll < config["sheep"]:
        old_skin = u["skin"]
        u["skin"] = "🐑 Обычная овечка"
        await save_u(u)
        await query.answer(f"🐺 Странный торговец схватил твою {old_skin} и сбежал!", show_alert=True)
    elif roll < config["sheep"] + config["coins"]:
        stolen = random.randint(25, 75)
        u["balance"] = max(0, u["balance"] - stolen)
        await save_u(u)
        await query.answer(f"🐺 Странный торговец выхватил твои {stolen} 🐾 и сбежал!", show_alert=True)
    else:
        await query.answer("🐺 Странный торговец ушёл в глубь леса!", show_alert=True)
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def wolf_scare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    durability = u.get("flashlight_durability", 100)
    loss = random.randint(5, 10)
    durability = max(0, durability - loss)
    u["flashlight_durability"] = durability
    if durability == 0:
        u["flashlight_equipped"] = False
        u["flashlight_broken"] = True
        await save_u(u)
    else:
        await save_u(u)
    old_level = add_xp(u, random.randint(5, 10))
    await query.answer("🐺 Странный торговец испугался и сбежал!", show_alert=True)
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

# ===== СОВА =====

async def show_owl_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, edit: bool = True):
    advice = u.get("owl_advice")
    if not advice:
        if edit and hasattr(update, 'callback_query'):
            await update.callback_query.answer("❌ Ошибка!", show_alert=True)
        return False
    text = f"🦉 Мудрая жительница.\n«С меня совет, с тебя оплата»\n{advice['text']}"
    if u.get("flashlight_equipped", False) and not u.get("flashlight_broken", False):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔦 Припугнуть", callback_data="owl_scare")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="owl_refuse")]
        ])
    else:
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
    text = f"🦉 Мудрая жительница.\n«С меня совет, с тебя оплата»\n{advice['text']}"
    if u.get("flashlight_equipped", False) and not u.get("flashlight_broken", False):
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔦 Припугнуть", callback_data="owl_scare")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="owl_refuse")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Отблагодарить", callback_data="owl_pay")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="owl_refuse")]
        ])
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=keyboard
    )

async def owl_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    advice = u.get("owl_advice")
    if not advice:
        await query.answer("❌ Ошибка!", show_alert=True)
        return
    old_level = add_xp(u, random.randint(5, 10))
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "bear"
    await save_u(u)
    await query.answer("🦉 Спасибо за угощение!", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def owl_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u.get("immunity", False):
        u["immunity"] = False
        u["immunity_used"] = True
        await save_u(u)
        await query.answer("🦉 Мудрая жительница улетела в глубь леса!", show_alert=True)
        u["owl_active"] = False
        u["owl_advice"] = None
        u["next_visitor"] = "bear"
        await save_u(u)
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))
        return
    skin = u.get("skin", "🐑 Обычная овечка")
    config = STEAL_CONFIG.get(skin, {"coins": 0, "sheep": 0})
    roll = random.random() * 100
    if roll < config["sheep"]:
        old_skin = u["skin"]
        u["skin"] = "🐑 Обычная овечка"
        await save_u(u)
        await query.answer(f"🦉 Мудрая жительница схватила твою {old_skin} и сбежала!", show_alert=True)
    elif roll < config["sheep"] + config["coins"]:
        stolen = random.randint(25, 75)
        u["balance"] = max(0, u["balance"] - stolen)
        await save_u(u)
        await query.answer(f"🦉 Мудрая жительница выхватила твои {stolen} 🐾 и сбежала!", show_alert=True)
    else:
        await query.answer("🦉 Мудрая жительница улетела в глубь леса!", show_alert=True)
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "bear"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def owl_scare(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    durability = u.get("flashlight_durability", 100)
    loss = random.randint(5, 10)
    durability = max(0, durability - loss)
    u["flashlight_durability"] = durability
    if durability == 0:
        u["flashlight_equipped"] = False
        u["flashlight_broken"] = True
        await save_u(u)
    else:
        await save_u(u)
    old_level = add_xp(u, random.randint(5, 10))
    await query.answer("🦉 Мудрая жительница испугалась и сбежала!", show_alert=True)
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "bear"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

# ===== РЕМЕСЛЕННИК (МЕДВЕДЬ) =====

async def show_bear_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, edit: bool = True):
    durability = u.get("flashlight_durability", 100)
    broken_percent = 100 - durability
    price = broken_percent * 2
    text = f"🐻 Ремесленник\n«С тебя копытца, с меня починка»\n🔦 Фонарик – {price} 🐾"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Ремонтируем", callback_data="bear_repair")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="bear_refuse")]
    ])
    if edit and hasattr(update, 'callback_query'):
        await update.callback_query.edit_message_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text, reply_markup=keyboard)
    return True

async def show_bear_message(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    durability = u.get("flashlight_durability", 100)
    broken_percent = 100 - durability
    price = broken_percent * 2
    text = f"🐻 Ремесленник\n«С тебя копытца, с меня починка»\n🔦 Фонарик – {price} 🐾"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Ремонтируем", callback_data="bear_repair")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="bear_refuse")]
    ])
    await context.bot.send_message(
        chat_id=update.effective_user.id,
        text=text,
        reply_markup=keyboard
    )

async def bear_repair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    durability = u.get("flashlight_durability", 100)
    broken_percent = 100 - durability
    price = broken_percent * 2
    if price > 0:
        if u["balance"] < price:
            await query.answer("❌ Недостаточно копытец!", show_alert=True)
            return
        u["balance"] -= price
        u["flashlight_durability"] = 100
        u["flashlight_broken"] = False
        await save_u(u)
        await query.answer("🔦 Фонарик успешно отремонтирован!", show_alert=True)
    else:
        await query.answer("🔦 Фонарик уже полностью исправен!", show_alert=True)
    u["bear_active"] = False
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def bear_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    await query.answer("🐻 Ремесленник ушёл в глубь леса!", show_alert=True)
    u["bear_active"] = False
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

# ===== ВИЗИТОРЫ =====

async def check_and_activate_visitor(u: dict, update: Update = None, context: ContextTypes.DEFAULT_TYPE = None) -> bool:
    now = time.time()
    if u.get("wolf_active", False) or u.get("owl_active", False) or u.get("bear_active", False):
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
    elif next_visitor == "bear":
        if u.get("bear_auto_time", 0) == 0:
            u["bear_auto_time"] = now + random.randint(12 * 3600, 36 * 3600)
            await save_u(u)
            return False
        if now >= u.get("bear_auto_time", 0):
            u["bear_active"] = True
            u["bear_auto_time"] = 0
            await save_u(u)
            if update and context:
                await show_bear_message(update, context, u)
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
    elif u.get("bear_active", False):
        await show_bear_inline(update, context, u, edit=False)
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
    elif u.get("bear_active", False):
        await show_bear_inline(update, context, u)
        return True
    return False

# ===== РОЩА =====

async def grove_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    if await check_and_show_visitor(update, context):
        return
    now = time.time()
    if u.get("grove_ready", False) and u.get("grove_loot"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍃 Забрать лут", callback_data="grove_collect")]
        ])
        await update.message.reply_text(
            f"🌳 Лесная роща\n\nОвечка вернулась и принесла тебе интересные вещи!",
            reply_markup=kb
        )
        return
    if u.get("grove_activity") == "grove":
        finish = u.get("grove_activity_finish", 0)
        remaining = finish - now
        if remaining > 0:
            time_str = format_time(remaining)
            await update.message.reply_text(
                f"🌳 Лесная роща\n\nОвечка гуляет и обещает вернуться через: {time_str}"
            )
            return
        else:
            await generate_grove_loot(update, context, u)
            return
    satiety = u.get("satiety", 100)
    if satiety < 10:
        await update.message.reply_text("🌿 Овечка голодна!")
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍃 Отправить гулять", callback_data="grove_start")]
    ])
    await update.message.reply_text(
        f"🌳 Лесная роща\n\nОтличное место для выгула овечки, тут можно найти удивительные вещи!",
        reply_markup=kb
    )

async def grove_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    u = await get_u(user_id)
    now = time.time()
    satiety = u.get("satiety", 100)
    if satiety < 10:
        await query.answer("🌿 Овечка голодна!", show_alert=True)
        return
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
        f"🌳 Лесная роща\n\nОвечка гуляет и обещает вернуться через: {time_str}"
    )
    await query.answer("🌳 Овечка отправилась гулять!", show_alert=True)

async def generate_grove_loot(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    if u.get("grove_ready", False) and u.get("grove_loot"):
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍃 Забрать лут", callback_data="grove_collect")]
        ])
        await update.message.reply_text(
            f"🌳 Лесная роща\n\nОвечка вернулась и принесла тебе интересные вещи!",
            reply_markup=kb
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
    old_level = add_xp(u, random.randint(3, 5))
    await save_u(u)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍃 Забрать лут", callback_data="grove_collect")]
    ])
    await update.message.reply_text(
        f"🌳 Лесная роща\n\nОвечка вернулась и принесла тебе интересные вещи!",
        reply_markup=kb
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
        f"🌳 Лесная роща\n\nОтличное место для выгула овечки, тут можно найти удивительные вещи!",
        reply_markup=kb
    )

# ===== ОСНОВНАЯ ФУНКЦИЯ =====

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
            await query.answer("🌳 Овечка занята. ⏳ Дождись её прихода!", show_alert=True)
            return
    
    if now < u["harvest"]:
        rem = int(u["harvest"] - now)
        time_str = format_time(rem)
        await query.answer(f"❌ Овечка не готова к стрижке! Подожди: {time_str}", show_alert=True)
        return
    
    # Проверяем баффы
    mango_boost = u.get("buff_mango_wool", 0) and now < u.get("buff_mango_immunity_expires", 0)
    coconut_boost = u.get("buff_coconut_wool", 0) and now < u.get("buff_coconut_immunity_expires", 0)
    apple_boost = u.get("buff_apple_wool", 0)
    
    if mango_boost or coconut_boost:
        gain = random.randint(15, 25)
    else:
        gain = random.randint(5, 15)
    if apple_boost:
        gain += 5
    
    u["wool"] += gain
    u["harvest"] = now + 12 * 3600
    u["satiety"] = max(0, satiety - random.randint(5, 10))
    
    # Сбрасываем баффы
    u["buff_apple_wool"] = 0
    u["buff_mango_wool"] = 0
    u["buff_coconut_wool"] = 0
    
    old_level = add_xp(u, random.randint(5, 10))
    await save_u(u)
    await query.answer(f"🐑 Овечка успешно пострижена! Получено: {gain} 🧶", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u))

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("grove", grove_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("daily", daily_cmd))
    application.add_handler(CallbackQueryHandler(clean, pattern="^clean$"))
    application.add_handler(CallbackQueryHandler(shear, pattern="^shear$"))
    application.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    application.add_handler(CallbackQueryHandler(inventory_main, pattern="^inventory_main$"))
    application.add_handler(CallbackQueryHandler(inventory_empty, pattern="^inventory_empty$"))
    application.add_handler(CallbackQueryHandler(inventory_wear_flashlight, pattern="^inventory_wear_flashlight$"))
    application.add_handler(CallbackQueryHandler(inventory_toggle_flashlight, pattern="^inventory_toggle_flashlight$"))
    application.add_handler(CallbackQueryHandler(inventory_back, pattern="^inventory_back$"))
    application.add_handler(CallbackQueryHandler(inventory_wear_back, pattern="^inventory_wear_back$"))
    application.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(learn_talent, pattern="^learn_talent$"))
    application.add_handler(CallbackQueryHandler(wolf_buy, pattern="^wolf_buy$"))
    application.add_handler(CallbackQueryHandler(wolf_refuse, pattern="^wolf_refuse$"))
    application.add_handler(CallbackQueryHandler(wolf_scare, pattern="^wolf_scare$"))
    application.add_handler(CallbackQueryHandler(owl_pay, pattern="^owl_pay$"))
    application.add_handler(CallbackQueryHandler(owl_refuse, pattern="^owl_refuse$"))
    application.add_handler(CallbackQueryHandler(owl_scare, pattern="^owl_scare$"))
    application.add_handler(CallbackQueryHandler(bear_repair, pattern="^bear_repair$"))
    application.add_handler(CallbackQueryHandler(bear_refuse, pattern="^bear_refuse$"))
    application.add_handler(CallbackQueryHandler(grove_start, pattern="^grove_start$"))
    application.add_handler(CallbackQueryHandler(grove_collect, pattern="^grove_collect$"))
    application.add_handler(CallbackQueryHandler(market_main, pattern="^market_main$"))
    application.add_handler(CallbackQueryHandler(sell_menu, pattern="^sell$"))
    application.add_handler(CallbackQueryHandler(sell_confirm, pattern="^sell_confirm$"))
    application.add_handler(CallbackQueryHandler(eggs_menu, pattern="^eggs$"))
    application.add_handler(CallbackQueryHandler(open_egg, pattern="^open_egg$"))
    application.add_handler(CallbackQueryHandler(daily_claim, pattern="^daily_claim$"))
    application.add_handler(CallbackQueryHandler(daily_fruit_choice, pattern="^daily_fruit_"))
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port, debug=False, use_reloader=False), daemon=True).start()
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
