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
    "🔥 Магмовая овечка": 25,
    "💎 Бриллиантовая овечка": 25,
    "🐚 Жемчужная овечка": 25,
    "👼 Священная овечка": 50,
    "👻 Призрачная овечка": 50,
    "🕯️ Ритуальная овечка": 50
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

def xp_to_next(level: int) -> int:
    if level == 1:
        return 50
    elif level == 2:
        return 75
    elif level == 3:
        return 100
    elif level == 4:
        return 125
    elif level == 5:
        return 150
    elif level == 6:
        return 175
    elif level == 7:
        return 200
    elif level == 8:
        return 225
    elif level == 9:
        return 250
    else:
        return 50 + (level - 1) * 40

def add_xp(u: dict, amount: int):
    u["xp"] = u.get("xp", 0) + amount
    old_level = u.get("level", 1)
    while u["xp"] >= xp_to_next(u.get("level", 1)):
        u["xp"] -= xp_to_next(u.get("level", 1))
        u["level"] = u.get("level", 1) + 1
    return old_level

def get_default_user(uid: int):
    now = time.time()
    return {
        "id": uid,
        "name": "овечка",
        "level": 1,
        "xp": 0,
        "skin": "🐑 Обычная овечка",
        "balance": 0,
        "wool": 0,
        "harvest": now,
        "shearing": 0,
        "s_finish": 0,
        "last_active": now,
        "wolf_last_offer": 0,
        "wolf_item": None,
        "wolf_active": False,
        "wolf_auto_time": 0,
        "next_visitor": "wolf",
        "owl_active": False,
        "owl_auto_time": 0,
        "owl_advice": None,
        "map_activity": None,
        "map_activity_finish": 0,
        "inv_apple": 0,
        "inv_blueberry": 0,
        "inv_watermelon": 0,
        "inv_mango": 0,
        "inv_kiwi": 0,
        "inv_coconut": 0,
        "buff_treat_boost": 0,
        "buff_treat_boost_expires": 0,
        "buff_luck_boost": 0,
        "buff_luck_boost_expires": 0,
        "buff_wolf_immunity": 0,
        "buff_wolf_immunity_expires": 0,
        "buff_wool_boost": 0,
        "buff_wool_boost_expires": 0,
        "buff_market_discount": 0,
        "buff_market_discount_expires": 0,
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
    rows = []
    rows.append([InlineKeyboardButton("✂️ Стрижка", callback_data="shear")])
    rows.append([InlineKeyboardButton("📦 Склад", callback_data="inventory")])
    return InlineKeyboardMarkup(rows)

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
        discount += 10
    if u.get("buff_kiwi_immunity", 0) and now < u.get("buff_kiwi_discount_expires", 0):
        discount += 10
    if u.get("buff_coconut_immunity", 0) and now < u.get("buff_coconut_discount_expires", 0):
        discount += 10
    if u.get("buff_market_discount", 0) and now < u.get("buff_market_discount_expires", 0):
        discount += u.get("buff_market_discount", 0)
    return min(discount, 50)

def format_hms(seconds: int) -> str:
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

def profile_text(u: dict) -> str:
    now = time.time()
    skin = u.get("skin", "🐑 Обычная овечка")
    skin_parts = skin.split()
    emoji = skin_parts[0] if skin_parts else "🐑"
    name = u.get("name", "овечка")
    if name == "овечка":
        name = skin_parts[1].lower() if len(skin_parts) > 1 else "овечка"
    level = u.get("level", 1)
    balance = u["balance"]
    
    if now >= u["harvest"]:
        timer_line = "✅ <b>Шерсть готова к сбору!</b>"
    else:
        remaining = int(u["harvest"] - now)
        timer_str = format_hms(remaining)
        timer_line = f"⏳ <i>До следующего сбора:</i>\n<b>{timer_str}</b>"
    
    return (
        f"<b>{emoji} {name} | ⭐ {level}</b>\n"
        f"<i>🐾 Копытца:</i> <b>{balance}</b>\n"
        f"{timer_line}"
    )

async def check_level_up(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict, old_level: int):
    new_level = u.get("level", 1)
    if new_level > old_level:
        msg = f"# {u.get('name', 'овечка')} достиг {new_level} уровня!\nПолучено: ✅ Яблоко"
        
        if new_level == 5:
            msg += "\n🦉 Совиный базар открыт"
        elif new_level == 10:
            msg += "\n⚙️ Мельница открыта"
        
        await context.bot.send_message(
            chat_id=update.effective_user.id,
            text=msg
        )
        return True
    return False

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐑 Привет! Используй /sheep, чтобы начать.")

ADMIN_ID = 1864104580

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
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

# ============= ВОЛК =============

async def show_wolf_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    query = update.callback_query
    item = u.get("wolf_item")
    if not item:
        await query.answer("❌ Ошибка!", show_alert=True)
        return
    text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
    if u["balance"] < item["price"]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
        ])
    else:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
            [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
        ])
    await query.edit_message_text(text, reply_markup=keyboard)

async def show_wolf_message(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    item = u.get("wolf_item")
    if not item:
        return
    text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
    if u["balance"] < item["price"]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
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

# ============= СОВА =============

async def show_owl_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    query = update.callback_query
    advice = u.get("owl_advice")
    if not advice:
        await query.answer("❌ Ошибка!", show_alert=True)
        return
    text = f"🦉 Мудрая сова.\n«С меня совет, с тебя оплата»\n{advice['text']}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Отблагодарить", callback_data="owl_pay")],
        [InlineKeyboardButton("❌ Отказаться", callback_data="owl_refuse")]
    ])
    await query.edit_message_text(text, reply_markup=keyboard)

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
        await query.answer("❌ Сова уже улетела!", show_alert=True)
        return
    text = (
        f"⚡️ Выбери, чем хочешь отблагодарить.\n"
        f"🍏 <b>{u.get('inv_apple', 0)}</b> | 🫐 <b>{u.get('inv_blueberry', 0)}</b> | 🍉 <b>{u.get('inv_watermelon', 0)}</b>\n"
        f"🥭 <b>{u.get('inv_mango', 0)}</b> | 🥝 <b>{u.get('inv_kiwi', 0)}</b> | 🥥 <b>{u.get('inv_coconut', 0)}</b>"
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
        await query.answer("❌ Сова уже улетела!", show_alert=True)
        return
    inv_field = f"inv_{fruit_key}"
    if u.get(inv_field, 0) <= 0:
        await query.answer("❌ У тебя нет этого угощения!", show_alert=True)
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
    if not u.get("owl_active", False):
        await query.answer("❌ Сова уже улетела!", show_alert=True)
        return
    stolen = random.randint(25, 125)
    u["balance"] = max(0, u["balance"] - stolen)
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "wolf"
    await save_u(u)
    await query.answer(f"🦉 Мудрая сова выхватила твои {stolen} 🐾 и сбежала!", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def owl_back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if not u.get("owl_active", False):
        await query.answer("❌ Сова уже улетела!", show_alert=True)
        await back(update, context)
        return
    await show_owl_inline(update, context, u)

# ============= ВИЗИТОР =============

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
    await query.answer("💰 Товар успешно приобретён!", show_alert=True)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def wolf_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    skin = u.get("skin", "🐑 Обычная овечка")
    now = time.time()
    has_wolf_immunity = u.get("buff_wolf_immunity", 0) and now < u.get("buff_wolf_immunity_expires", 0)
    has_fruit_immunity = (
        (u.get("buff_apple_immunity", 0) and now < u.get("buff_apple_immunity_expires", 0)) or
        (u.get("buff_blueberry_immunity", 0) and now < u.get("buff_blueberry_immunity_expires", 0)) or
        (u.get("buff_watermelon_immunity", 0) and now < u.get("buff_watermelon_immunity_expires", 0)) or
        (u.get("buff_mango_immunity", 0) and now < u.get("buff_mango_immunity_expires", 0)) or
        (u.get("buff_kiwi_immunity", 0) and now < u.get("buff_kiwi_immunity_expires", 0)) or
        (u.get("buff_coconut_immunity", 0) and now < u.get("buff_coconut_immunity_expires", 0))
    )
    if has_wolf_immunity or has_fruit_immunity:
        steal_chance = 0
    else:
        steal_chance = WOLF_STEAL_CHANCES.get(skin, 0)
    if random.random() * 100 < steal_chance:
        old_skin = u["skin"]
        u["skin"] = "🐑 Обычная овечка"
        await save_u(u)
        await query.answer(f"🐺 Странный торговец схватил твою {old_skin} и сбежал!", show_alert=True)
    else:
        await query.answer("🐺 Странный торговец ушел в глубь леса..", show_alert=True)
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

# ============= ОСНОВНЫЕ КОМАНДЫ =============

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    await check_and_activate_visitor(u, update, context)
    if u.get("wolf_active", False) or u.get("owl_active", False):
        return
    await update.message.reply_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продажа шерсти", callback_data="sell")],
        [InlineKeyboardButton("🥚 Покупка яиц", callback_data="eggs")]
    ])
    await update.message.reply_text(
        "<b>🐑 Овечий рынок</b>\n<i>Выбери раздел:</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    text = (
        f"<b>📦 Склад</b>\n"
        f"<i>🍏 <b>{u.get('inv_apple', 0)}</b> | 🫐 <b>{u.get('inv_blueberry', 0)}</b> | 🍉 <b>{u.get('inv_watermelon', 0)}</b></i>\n"
        f"<i>🥭 <b>{u.get('inv_mango', 0)}</b> | 🥝 <b>{u.get('inv_kiwi', 0)}</b> | 🥥 <b>{u.get('inv_coconut', 0)}</b></i>"
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
    text = f"<b>⚡️ Использовать угощение</b>\n<i>Активный эффект: {effect}</i>"
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
        await query.answer("❌ У тебя нет этого угощения!", show_alert=True)
        return
    u[inv_field] -= 1
    now = time.time()
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
        u["buff_apple_immunity_expires"] = now + 6 * 3600
        u["buff_apple_wool"] = 1
    elif fruit_key == "blueberry":
        u["buff_blueberry_immunity"] = 1
        u["buff_blueberry_immunity_expires"] = now + 6 * 3600
        u["buff_blueberry_discount_expires"] = now + 6 * 3600
    elif fruit_key == "watermelon":
        u["buff_watermelon_immunity"] = 1
        u["buff_watermelon_immunity_expires"] = now + 12 * 3600
        u["buff_watermelon_passive_expires"] = now + 12 * 3600
    elif fruit_key == "mango":
        u["buff_mango_immunity"] = 1
        u["buff_mango_immunity_expires"] = now + 12 * 3600
        u["buff_mango_wool"] = 1
    elif fruit_key == "kiwi":
        u["buff_kiwi_immunity"] = 1
        u["buff_kiwi_immunity_expires"] = now + 18 * 3600
        u["buff_kiwi_passive_expires"] = now + 12 * 3600
        u["buff_kiwi_discount_expires"] = now + 6 * 3600
    elif fruit_key == "coconut":
        u["buff_coconut_immunity"] = 1
        u["buff_coconut_immunity_expires"] = now + 18 * 3600
        u["buff_coconut_wool"] = 1
        u["buff_coconut_discount_expires"] = now + 6 * 3600
    else:
        return
    old_level = add_xp(u, random.randint(3, 5))
    await save_u(u)
    await check_level_up(update, context, u, old_level)
    await query.answer("⭐️ Угощение успешно активировано!", show_alert=True)
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

async def eggs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 299 * (100 - discount) // 100
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Открыть яйцо", callback_data="open_egg")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(
        f"<b>🥚 Покупка яиц</b>\n<i>Курс: 1 🥚 = {price} 🐾</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def open_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 299 * (100 - discount) // 100
    if u["balance"] < price:
        await query.answer(f"❌ Недостаточно копытц! Нужно {price} 🐾", show_alert=True)
        return
    u["balance"] -= price
    r_l = list(RARITIES.keys())
    rarity = random.choices(r_l, weights=[RARITIES[k]["w"] for k in r_l])[0]
    u["skin"] = random.choice(RARITIES[rarity]["items"])
    old_level = add_xp(u, random.randint(3, 5))
    await save_u(u)
    await check_level_up(update, context, u, old_level)
    await query.answer(f"🥚 Ты открыл яйцо! Тебе выпала: {u['skin']}.", show_alert=True)
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
        "<b>💰 Продажа шерсти</b>\n<i>Курс: 1 🧶 = 10 🐾</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def sell_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    if u["wool"] <= 0:
        await query.answer("🐑 Мее! Сначала постриги овечку.", show_alert=True)
        return
    v = u["wool"] * 10
    u["balance"] += v
    u["wool"] = 0
    old_level = add_xp(u, random.randint(3, 5))
    await save_u(u)
    await check_level_up(update, context, u, old_level)
    await query.answer(f"💰 Ты успешно продал всю шерсть!\nПолучено: {v} 🐾", show_alert=True)
    await sell_menu(update, context)

async def shear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    now = time.time()
    wool_boost = u.get("buff_wool_boost", 0) and now < u.get("buff_wool_boost_expires", 0)
    if u["shearing"]:
        if now >= u["s_finish"]:
            if wool_boost:
                gain = random.randint(15, 25)
            elif u.get("buff_mango_wool", 0) or u.get("buff_coconut_wool", 0):
                gain = random.randint(15, 25)
            else:
                gain = random.randint(5, 15)
            if u.get("buff_apple_wool", 0):
                gain += 5
            u["wool"] += gain
            u["shearing"] = 0
            u["harvest"] = now + 12 * 3600
            if u.get("buff_apple_wool", 0):
                u["buff_apple_wool"] = 0
            if u.get("buff_mango_wool", 0):
                u["buff_mango_wool"] = 0
            if u.get("buff_coconut_wool", 0):
                u["buff_coconut_wool"] = 0
            old_level = add_xp(u, random.randint(5, 10))
            await save_u(u)
            await check_level_up(update, context, u, old_level)
            await query.answer(f"🐑 Овечка успешно пострижена! Получено: {gain} 🧶", show_alert=True)
            await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")
        else:
            rem = int(u["s_finish"] - now)
            m, s = divmod(rem, 60)
            await query.answer(f"✂️ Стрижём твою овечку. ⏳ Процесс займет: {m} мин. {s} сек.", show_alert=True)
    elif now < u["harvest"]:
        await query.answer("❌ Ещё не готова!", show_alert=True)
    else:
        u["shearing"] = 1
        u["s_finish"] = now + 300
        await save_u(u)
        await query.answer("✂️ Стрижём твою овечку. ⏳ Процесс займет: 5 мин.", show_alert=True)

async def market_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продажа шерсти", callback_data="sell")],
        [InlineKeyboardButton("🥚 Покупка яиц", callback_data="eggs")]
    ])
    await query.edit_message_text(
        "<b>🐑 Овечий рынок</b>\n<i>Выбери раздел:</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    u = await get_u(query.from_user.id)
    await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

# ============= КАРТА =============

LILY_DURATION = 90 * 60

LILY_LOOT_TABLE = [
    (12.5, "🍏 Яблоко", "inv_apple"),
    (12.5, "🫐 Черника", "inv_blueberry"),
    (7.5, "🍉 Арбуз", "inv_watermelon"),
    (7.5, "🥭 Манго", "inv_mango"),
    (2.5, "🥝 Киви", "inv_kiwi"),
    (2.5, "🥥 Кокос", "inv_coconut"),
]

async def map_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_u(update.effective_user.id)
    name = u.get("name", "овечка")
    level = u.get("level", 1)
    
    buttons = [
        [InlineKeyboardButton("🌱 Кувшинки", callback_data="map_lily")]
    ]
    
    if level >= 5:
        buttons.append([InlineKeyboardButton("🦉 Совиный базар", callback_data="map_owl_bazaar")])
    
    if level >= 10:
        buttons.append([InlineKeyboardButton("⚙️ Мельница", callback_data="map_mill")])
    
    kb = InlineKeyboardMarkup(buttons)
    await update.message.reply_text(
        f"🗺️ <b>Лесная карта</b>\n<i>Куда отправим {name} сегодня?</i>",
        reply_markup=kb,
        parse_mode="HTML"
    )

async def map_owl_bazaar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🦉 Совиный базар пока в разработке!", show_alert=True)

async def map_mill(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("⚙️ Мельница пока в разработке!", show_alert=True)

async def map_lily(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    now = time.time()
    
    if u.get("map_activity") == "lily":
        finish = u.get("map_activity_finish", 0)
        remaining = finish - now
        if remaining > 0:
            await query.answer(
                f"🌱 Овечка гуляет по кувшинкам. ⏳ Осталось: {format_hms(remaining)}",
                show_alert=True,
            )
            return
        u["map_activity"] = None
        u["map_activity_finish"] = 0
        old_level = add_xp(u, random.randint(5, 10))
        roll = random.random() * 100
        cumulative = 0
        fruit_name = None
        inv_field = None
        for chance, f_name, f_field in LILY_LOOT_TABLE:
            cumulative += chance
            if roll < cumulative:
                fruit_name, inv_field = f_name, f_field
                break
        if fruit_name:
            u[inv_field] = u.get(inv_field, 0) + 1
            msg = f"🐑 Овечка вернулась с кувшинок! Получено: {fruit_name}"
        else:
            reward = random.randint(5, 35)
            u["balance"] += reward
            msg = f"🐑 Овечка вернулась с кувшинок! Получено: {reward} 🐾"
        await save_u(u)
        await check_level_up(update, context, u, old_level)
        await query.answer(msg, show_alert=True)
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")
    else:
        u["map_activity"] = "lily"
        u["map_activity_finish"] = now + LILY_DURATION
        await save_u(u)
        await query.answer(
            f"🌱 Овечка отправлена на кувшинки. ⏳ Процесс займет: {format_hms(LILY_DURATION)}",
            show_alert=True,
        )
        await query.edit_message_text(profile_text(u), reply_markup=main_kb(u), parse_mode="HTML")

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("map", map_cmd))
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("reave", reave_cmd))
    
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
    application.add_handler(CallbackQueryHandler(map_lily, pattern="^map_lily$"))
    application.add_handler(CallbackQueryHandler(map_owl_bazaar, pattern="^map_owl_bazaar$"))
    application.add_handler(CallbackQueryHandler(map_mill, pattern="^map_mill$"))
    
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "apple"), pattern="^owl_pay_fruit_apple$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "blueberry"), pattern="^owl_pay_fruit_blueberry$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "watermelon"), pattern="^owl_pay_fruit_watermelon$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "mango"), pattern="^owl_pay_fruit_mango$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "kiwi"), pattern="^owl_pay_fruit_kiwi$"))
    application.add_handler(CallbackQueryHandler(lambda update, context: owl_pay_fruit(update, context, "coconut"), pattern="^owl_pay_fruit_coconut$"))
    
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()
