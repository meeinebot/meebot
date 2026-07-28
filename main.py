import asyncio
import random
import time
import threading
import os
import json
import aiosqlite
from datetime import datetime, timedelta, timezone
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
DB_PATH = "sheep_farm.db"

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
        "buff_coconut_discount_expires": 0,
        "shears_total": 0,
        "wool_sold_total": 0,
        "eggs_opened_total": 0,
        "fruits_used_total": 0,
        "compensation_claimed": False,
        "total_spent_on_upgrades": 0
    }

async def get_u(uid: int) -> dict:
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data FROM players WHERE id = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        user = get_default_user(uid)
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT INTO players VALUES (?, ?)", (uid, json.dumps(user)))
            await db.commit()
    else:
        user = json.loads(row[0])
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
        async with aiosqlite.connect(DB_PATH) as db:
            await db.execute("INSERT OR REPLACE INTO players VALUES (?, ?)", (uid, json.dumps(user)))
            await db.commit()
    return user

async def save_u(u: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("INSERT OR REPLACE INTO players VALUES (?, ?)", (u["id"], json.dumps(u)))
        await db.commit()

async def db_init():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("CREATE TABLE IF NOT EXISTS players (id INTEGER PRIMARY KEY, data TEXT)")
        await db.commit()

app = Flask(__name__)

@app.route('/')
def h():
    return "OK"

def main_kb(u: dict = None):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✂️ Стрижка", callback_data="shear"),
         InlineKeyboardButton("📦 Склад", callback_data="inventory")],
        [InlineKeyboardButton("💰 Компенсация", callback_data="compensation")],
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

def get_skin_level(skin: str) -> int:
    return SKIN_LEVELS.get(skin, 0)

def get_wool_price(u: dict) -> int:
    return 10

def get_shear_cooldown(u: dict) -> int:
    return 12

def profile_text(u: dict) -> str:
    now = time.time()
    skin = u.get("skin", "🐑 Обычная овечка")
    display = get_skin_display(skin)
    
    balance = u["balance"]
    satiety = u.get("satiety", 100)
    satiety = max(0, min(100, satiety))

    if now >= u["harvest"]:
        timer_line = "✅ <i>Шерсть готова к сбору!</i>"
    else:
        remaining = int(u["harvest"] - now)
        timer_line = f"⏳ <i>Шерсть будет готова к сбору через: {format_time(remaining)}</i>"

    return (
        f"<i>{display} | 🌿 {satiety}%</i>\n"
        f"<i>🐾 Копытца: {balance}</i>\n"
        f"{timer_line}"
    )

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐑 Привет! Используй /sheep, чтобы начать.")

# ===== КОМПЕНСАЦИЯ =====

async def compensation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    
    total_spent = u.get("total_spent_on_upgrades", 0)
    
    if total_spent <= 0:
        await update.message.reply_text("⭐️ У вас нет компенсации!")
        return
    
    if u.get("compensation_claimed", False):
        await update.message.reply_text("💰 Компенсация уже получена!")
        return
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Забрать компенсацию", callback_data="claim_compensation")]
    ])
    await update.message.reply_text(
        f"⭐️ Тебе выдана компенсация за навыки: {total_spent} 🐾",
        reply_markup=kb
    )

async def claim_compensation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    
    total_spent = u.get("total_spent_on_upgrades", 0)
    
    if total_spent <= 0:
        await query.answer("💰 Компенсация доставлена не вам!", show_alert=True)
        return
    
    if u.get("compensation_claimed", False):
        await query.answer("💰 Компенсация уже получена!", show_alert=True)
        return
    
    u["balance"] += total_spent
    u["compensation_claimed"] = True
    await save_u(u)
    
    await query.answer(f"💰 Компенсация успешно получена! +{total_spent} 🐾", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

# ===== АДМИН КОМАНДЫ ДЛЯ ВЫДАЧИ КОМПЕНСАЦИИ =====

async def give_compensation_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ У вас нет прав!")
        return
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("Использование: /give_comp <id> <сумма>")
        return
    try:
        target_id = int(args[0])
        amount = int(args[1])
    except ValueError:
        await update.message.reply_text("id и сумма должны быть числами.")
        return
    u = await get_u(target_id)
    u["total_spent_on_upgrades"] = amount
    await save_u(u)
    await update.message.reply_text(f"✅ Компенсация {amount} 🐾 выдана пользователю {target_id}.")

# ===== ОСНОВНЫЕ КОМАНДЫ =====

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    await save_u(u)
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

# ===== ДНЕВНОЙ БОНУС =====

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
        await query.answer("❌ Недостаточно копытц!", show_alert=True)
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

# ===== ИНВЕНТАРЬ (ПЛЕЙСХОЛДЕР) =====

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    await query.answer("🛠️ Инвентарь в разработке!", show_alert=True)

async def inventory_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer("🛠️ Инвентарь в разработке!", show_alert=True)

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

def get_egg_reward(current_skin: str):
    skin_level = get_skin_level(current_skin)
    
    all_rarities = [
        ("🔵 Редкая", ["🏡 Деревенская овечка", "🏖️ Пляжная овечка", "💤 Сонная овечка"], ["🍏 Яблоко", "🫐 Черника"]),
        ("🟣 Эпическая", ["💥 Шизанутая овечка", "🎀 Милая овечка", "🍭 Карамельная овечка"], ["🍉 Арбуз", "🥭 Манго"]),
        ("🟡 Легендарная", ["🔥 Магмовая овечка", "💎 Бриллиантовая овечка", "🐚 Жемчужная овечка"], ["🥝 Киви", "🥥 Кокос"]),
        ("🔴 Мифическая", ["👼 Священная овечка", "👻 Призрачная овечка", "🕯️ Ритуальная овечка"], [])
    ]
    
    if skin_level == 0:
        weights = [40, 30, 20, 10]
    elif skin_level == 1:
        weights = [40, 30, 20, 10]
    elif skin_level == 2:
        weights = [0, 40, 30, 10]
    elif skin_level == 3:
        weights = [0, 0, 40, 10]
    elif skin_level == 4:
        weights = [0, 0, 0, 40]
    else:
        weights = [40, 30, 20, 10]
    
    total_weight = sum(weights)
    if total_weight == 0:
        weights = [0, 0, 0, 40]
    
    rarities = ["🔵 Редкая", "🟣 Эпическая", "🟡 Легендарная", "🔴 Мифическая"]
    chosen_rarity = random.choices(rarities, weights=weights, k=1)[0]
    rarity_index = rarities.index(chosen_rarity)
    
    if skin_level > rarity_index:
        fruits = all_rarities[rarity_index][2]
        if fruits:
            fruit_name = random.choice(fruits)
            return {"type": "fruit", "name": fruit_name, "skin": None}
        else:
            skins = all_rarities[rarity_index][1]
            new_skin = random.choice(skins)
            return {"type": "skin", "name": None, "skin": new_skin}
    else:
        skins = all_rarities[rarity_index][1]
        new_skin = random.choice(skins)
        return {"type": "skin", "name": None, "skin": new_skin}

async def open_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 399 * (100 - discount) // 100
    if u["balance"] < price:
        await query.answer("❌ Недостаточно копытц!", show_alert=True)
        return
    u["balance"] -= price
    
    current_skin = u.get("skin", "🐑 Обычная овечка")
    reward = get_egg_reward(current_skin)
    
    if reward["type"] == "skin":
        new_skin = reward["skin"]
        u["skin"] = new_skin
        await save_u(u)
        await query.answer(f"🥚 Ты открыл яйцо! Тебе выпала: {new_skin}", show_alert=True)
    elif reward["type"] == "fruit" and reward["name"]:
        fruit_name = reward["name"]
        if "Яблоко" in fruit_name:
            u["inv_apple"] = u.get("inv_apple", 0) + 1
        elif "Черника" in fruit_name:
            u["inv_blueberry"] = u.get("inv_blueberry", 0) + 1
        elif "Арбуз" in fruit_name:
            u["inv_watermelon"] = u.get("inv_watermelon", 0) + 1
        elif "Манго" in fruit_name:
            u["inv_mango"] = u.get("inv_mango", 0) + 1
        elif "Киви" in fruit_name:
            u["inv_kiwi"] = u.get("inv_kiwi", 0) + 1
        elif "Кокос" in fruit_name:
            u["inv_coconut"] = u.get("inv_coconut", 0) + 1
        await save_u(u)
        await query.answer(f"🥚 Ты открыл яйцо! Тебе выпало: {fruit_name}", show_alert=True)
    else:
        await query.answer("🥚 Ты открыл яйцо! Тебе выпало: 🍏 Яблоко", show_alert=True)
        u["inv_apple"] = u.get("inv_apple", 0) + 1
        await save_u(u)
    
    u["eggs_opened_total"] = u.get("eggs_opened_total", 0) + 1
    await save_u(u)
    await eggs_menu(update, context)

async def sell_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    wool_price = get_wool_price(u)
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продать шерсть", callback_data="sell_confirm")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(
        f"<i>💰 Продажа шерсти</i>\n<i>Курс: 1 🧶 = 10 🐾</i>",
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
    wool_amount = u["wool"]
    v = wool_amount * 10
    u["balance"] += v
    u["wool"] = 0
    u["wool_sold_total"] = u.get("wool_sold_total", 0) + wool_amount
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
            await query.answer("🌳 Овечка занята. ⏳ Дождись её прихода!", show_alert=True)
            return

    if now < u["harvest"]:
        rem = int(u["harvest"] - now)
        time_str = format_time(rem)
        await query.answer(f"❌ Овечка не готова к стрижке! Подожди: {time_str}", show_alert=True)
        return

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
    u["satiety"] = max(0, u.get("satiety", 100) - random.randint(5, 10))
    u["shears_total"] = u.get("shears_total", 0) + 1

    u["buff_apple_wool"] = 0
    u["buff_mango_wool"] = 0
    u["buff_coconut_wool"] = 0

    await save_u(u)
    await query.answer(f"🐑 Овечка успешно пострижена! Получено: {gain} 🧶", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

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
            f"<i>🌳 Лесная роща</i>\n\n"
            f"<i>Овечка вернулась и принесла тебе интересные вещи!</i>",
            reply_markup=kb,
            parse_mode="HTML"
        )
        return

    if u.get("grove_activity") == "grove":
        finish = u.get("grove_activity_finish", 0)
        remaining = finish - now
        if remaining > 0:
            time_str = format_time(remaining)
            await update.message.reply_text(
                f"<i>🌳 Лесная роща</i>\n\n"
                f"<i>Овечка гуляет и обещает вернуться через: {time_str}</i>",
                parse_mode="HTML"
            )
            return
        else:
            await generate_grove_loot(update, context, u)
            return

    satiety = u.get("satiety", 100)
    if satiety < 10:
        await update.message.reply_text("❌ Овечка голодна!")
        return

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

    satiety = u.get("satiety", 100)
    if satiety < 10:
        await query.answer("❌ Овечка голодна!", show_alert=True)
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

# ===== ТОП ИГРОКОВ =====

async def top_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT data FROM players") as cursor:
            rows = await cursor.fetchall()
    players_data = []
    for row in rows:
        try:
            players_data.append(json.loads(row[0]))
        except Exception:
            pass
    players_data.sort(key=lambda x: x.get("balance", 0), reverse=True)
    top = players_data[:10]
    medals = ["🥇","🥈","🥉","4️⃣","5️⃣","6️⃣","7️⃣","8️⃣","9️⃣","🔟"]
    text = "🏅 <b>Топ-10 фермеров</b>\n\n"
    for i, p in enumerate(top):
        skin = p.get("skin","🐑")
        display = get_skin_display(skin)
        bal = p.get("balance", 0)
        text += f"{medals[i]} {display} — {bal} 🐾\n"
    if not top:
        text += "<i>Пока никого нет.</i>"
    await update.message.reply_text(text, parse_mode="HTML")

# ===== ОСНОВНАЯ ФУНКЦИЯ =====

def main():
    application = Application.builder().token(TOKEN).post_init(lambda app: db_init()).build()

    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("grove", grove_cmd))
    application.add_handler(CommandHandler("daily", daily_cmd))
    application.add_handler(CommandHandler("top", top_cmd))

    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("reave", reave_cmd))
    application.add_handler(CommandHandler("reave_time", reave_time_cmd))
    application.add_handler(CommandHandler("reave_grove", reave_grove_cmd))
    application.add_handler(CommandHandler("give_comp", give_compensation_cmd))

    application.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    application.add_handler(CallbackQueryHandler(inventory_placeholder, pattern="^inventory_placeholder$"))
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
    application.add_handler(CallbackQueryHandler(compensation_cmd, pattern="^compensation$"))
    application.add_handler(CallbackQueryHandler(claim_compensation, pattern="^claim_compensation$"))

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
