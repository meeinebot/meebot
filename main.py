import asyncio
import random
import time
import threading
import os
import re
from datetime import datetime, timedelta, timezone
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
from pymongo import MongoClient

TOKEN = os.environ.get("BOT_TOKEN")
MONGO_URI = os.environ.get("MONGO_URI")
OWNER_ID = 1864104580

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

FRUIT_NAMES = {
    "apple": "🍏 Яблоко",
    "blueberry": "🫐 Черника",
    "watermelon": "🍉 Арбуз",
    "mango": "🥭 Манго",
    "kiwi": "🥝 Киви",
    "coconut": "🥥 Кокос"
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
        "effect": "treat_boost",
        "effects": {
            "rare": {"chance": 5, "duration": 6 * 3600},
            "epic": {"chance": 10, "duration": 12 * 3600},
            "legendary": {"chance": 15, "duration": 24 * 3600}
        }
    },
    {
        "id": "luck_boost",
        "text": "🎲 Удача на твоей стороне!",
        "effect": "luck_boost",
        "effects": {
            "rare": {"chance": 5, "duration": 6 * 3600},
            "epic": {"chance": 10, "duration": 12 * 3600},
            "legendary": {"chance": 15, "duration": 24 * 3600}
        }
    },
    {
        "id": "wolf_immunity",
        "text": "🐺 Странный торговец сегодня не голоден!",
        "effect": "wolf_immunity",
        "effects": {
            "rare": {"duration": 6 * 3600},
            "epic": {"duration": 12 * 3600},
            "legendary": {"duration": 24 * 3600}
        }
    },
    {
        "id": "wool_boost",
        "text": "✂️ Шерсть сегодня ценнее!",
        "effect": "wool_boost",
        "effects": {
            "rare": {"duration": 6 * 3600},
            "epic": {"duration": 12 * 3600},
            "legendary": {"duration": 24 * 3600}
        }
    },
    {
        "id": "market_discount",
        "text": "💰 Рынок сегодня переполнен!",
        "effect": "market_discount",
        "effects": {
            "rare": {"discount": 5, "duration": 6 * 3600},
            "epic": {"discount": 10, "duration": 12 * 3600},
            "legendary": {"discount": 15, "duration": 24 * 3600}
        }
    }
]

# Соответствие эмодзи фруктов → названия
FRUIT_EMOJI_TO_NAME = {
    "🍏": "🍏 Яблоко",
    "🫐": "🫐 Черника",
    "🍉": "🍉 Арбуз",
    "🥭": "🥭 Манго",
    "🥝": "🥝 Киви",
    "🥥": "🥥 Кокос"
}

# Соответствие эмодзи фруктов → ключи инвентаря
FRUIT_EMOJI_TO_KEY = {
    "🍏": "inv_apple",
    "🫐": "inv_blueberry",
    "🍉": "inv_watermelon",
    "🥭": "inv_mango",
    "🥝": "inv_kiwi",
    "🥥": "inv_coconut"
}

# Цены для каждого фрукта
FRUIT_PRICES = {
    "🍏": 49,
    "🫐": 99,
    "🍉": 149,
    "🥭": 199,
    "🥝": 249,
    "🥥": 299
}

# Цены для комбинаций
COMBO_PRICES = {
    "🍏🫐": 149,
    "🍉🥭": 399,
    "🥝🥥": 549
}

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
        "wolf_last_offer": 0,
        "wolf_item": None,
        "wolf_active": False,
        "wolf_auto_time": 0,
        "visitor_type": None,
        "next_visitor": "wolf",
        "owl_active": False,
        "owl_item": None,
        "owl_auto_time": 0,
        "owl_advice": None,
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

def main_kb():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("✂️ Стрижка", callback_data="shear")],
        [InlineKeyboardButton("🎒 Инвентарь", callback_data="inventory")]
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
        discount += 10
    if u.get("buff_kiwi_immunity", 0) and now < u.get("buff_kiwi_discount_expires", 0):
        discount += 10
    if u.get("buff_coconut_immunity", 0) and now < u.get("buff_coconut_discount_expires", 0):
        discount += 10
    
    if u.get("buff_market_discount", 0) and now < u.get("buff_market_discount_expires", 0):
        discount += u.get("buff_market_discount", 0)
    
    return min(discount, 50)

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🐑 Привет! Используй /sheep, чтобы начать.")

# ============= КОМАНДА /wolf (ТОЛЬКО ДЛЯ ВЛАДЕЛЬЦА) =============

async def wolf_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Принудительный вызов волка игроку (только для владельца)"""
    user_id = update.effective_user.id
    
    if user_id != OWNER_ID:
        await update.message.reply_text("❌ У тебя нет прав на эту команду!")
        return
    
    args = context.args
    if len(args) < 2:
        await update.message.reply_text(
            "❌ Использование: /wolf <фрукты> <user_id>\n\n"
            "Примеры:\n"
            "/wolf 🍏 593919682 - Яблоко (49 🐾)\n"
            "/wolf 🫐 593919682 - Черника (99 🐾)\n"
            "/wolf 🍉 593919682 - Арбуз (149 🐾)\n"
            "/wolf 🥭 593919682 - Манго (199 🐾)\n"
            "/wolf 🥝 593919682 - Киви (249 🐾)\n"
            "/wolf 🥥 593919682 - Кокос (299 🐾)\n"
            "/wolf 🍏🫐 593919682 - Яблоко+Черника (149 🐾)\n"
            "/wolf 🍉🥭 593919682 - Арбуз+Манго (399 🐾)\n"
            "/wolf 🥝🥥 593919682 - Киви+Кокос (549 🐾)"
        )
        return
    
    fruit_part = args[0]
    try:
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ ID должен быть числом!")
        return
    
    # Определяем фрукты и цену
    fruits = []
    price = 0
    
    # Проверяем комбинации
    if fruit_part in COMBO_PRICES:
        price = COMBO_PRICES[fruit_part]
        # Разбираем комбинацию на отдельные фрукты
        for emoji in fruit_part:
            if emoji in FRUIT_EMOJI_TO_NAME:
                fruits.append(FRUIT_EMOJI_TO_NAME[emoji])
    else:
        # Одиночный фрукт
        if fruit_part in FRUIT_PRICES:
            price = FRUIT_PRICES[fruit_part]
            fruits.append(FRUIT_EMOJI_TO_NAME.get(fruit_part, fruit_part))
        else:
            await update.message.reply_text(f"❌ Неизвестный фрукт: {fruit_part}")
            return
    
    if not fruits:
        await update.message.reply_text("❌ Не удалось распознать фрукты!")
        return
    
    # Получаем игрока
    try:
        u = await get_u(target_id)
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при получении игрока: {e}")
        return
    
    # Проверяем, не активен ли уже волк или сова
    if u.get("wolf_active", False) or u.get("owl_active", False):
        await update.message.reply_text(f"❌ У игрока уже активен визитёр! Подожди, пока он решит.")
        return
    
    # Создаём волка
    item_name = " + ".join(fruits)
    wolf_item = {"name": item_name, "price": price}
    
    u["wolf_item"] = wolf_item
    u["wolf_active"] = True
    u["wolf_auto_time"] = 0
    u["next_visitor"] = "owl"  # после принудительного волка — сова
    
    await save_u(u)
    
    # Отправляем уведомление владельцу
    await update.message.reply_text(
        f"✅ Волк принудительно вызван игроку {target_id}!\n"
        f"📦 Товар: {item_name}\n"
        f"💰 Цена: {price} 🐾"
    )
    
    # Отправляем уведомление игроку
    try:
        await context.bot.send_message(
            chat_id=target_id,
            text=f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item_name} – {price} 🐾\n\n*Принудительный визит*",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
                [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
            ])
        )
    except Exception as e:
        await update.message.reply_text(f"⚠️ Не удалось отправить сообщение игроку: {e}")

# ============= ВОЛК =============

async def show_wolf_inline(update: Update, context: ContextTypes.DEFAULT_TYPE, u: dict):
    query = update.callback_query
    item = u.get("wolf_item")
    if not item:
        await query.answer("❌ Ошибка!", show_alert=True)
        return
    
    text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
    
    if u['balance'] < item['price']:
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
    
    if u['balance'] < item['price']:
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
    
    text = (f"⚡️ Выбери, чем хочешь отблагодарить.\n"
            f"🍏 {u.get('inv_apple',0)} | 🫐 {u.get('inv_blueberry',0)} | 🍉 {u.get('inv_watermelon',0)}\n"
            f"🥭 {u.get('inv_mango',0)} | 🥝 {u.get('inv_kiwi',0)} | 🥥 {u.get('inv_coconut',0)}")
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍏", callback_data="owl_pay_fruit_apple"),
         InlineKeyboardButton("🫐", callback_data="owl_pay_fruit_blueberry"),
         InlineKeyboardButton("🍉", callback_data="owl_pay_fruit_watermelon")],
        [InlineKeyboardButton("🥭", callback_data="owl_pay_fruit_mango"),
         InlineKeyboardButton("🥝", callback_data="owl_pay_fruit_kiwi"),
         InlineKeyboardButton("🥥", callback_data="owl_pay_fruit_coconut")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="owl_back")]
    ])
    
    await query.edit_message_text(text, reply_markup=keyboard)

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
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

async def owl_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    
    if not u.get("owl_active", False):
        await query.answer("❌ Сова уже улетела!", show_alert=True)
        return
    
    stolen = random.randint(25, 125)
    u['balance'] = max(0, u['balance'] - stolen)
    
    u["owl_active"] = False
    u["owl_advice"] = None
    u["next_visitor"] = "wolf"
    
    await save_u(u)
    
    await query.answer(f"🦉 Мудрая сова выхватила твои {stolen} 🐾 и сбежала!", show_alert=True)
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

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
    
    if u['balance'] < item['price']:
        await query.answer("❌ Недостаточно средств!", show_alert=True)
        return
    
    u['balance'] -= item['price']
    
    if "+" in item['name']:
        items = item['name'].split(" + ")
        for it in items:
            if it == "🍏 Яблоко":
                u['inv_apple'] = u.get('inv_apple', 0) + 1
            elif it == "🫐 Черника":
                u['inv_blueberry'] = u.get('inv_blueberry', 0) + 1
            elif it == "🍉 Арбуз":
                u['inv_watermelon'] = u.get('inv_watermelon', 0) + 1
            elif it == "🥭 Манго":
                u['inv_mango'] = u.get('inv_mango', 0) + 1
            elif it == "🥝 Киви":
                u['inv_kiwi'] = u.get('inv_kiwi', 0) + 1
            elif it == "🥥 Кокос":
                u['inv_coconut'] = u.get('inv_coconut', 0) + 1
    else:
        if "Яблоко" in item['name']:
            u['inv_apple'] = u.get('inv_apple', 0) + 1
        elif "Черника" in item['name']:
            u['inv_blueberry'] = u.get('inv_blueberry', 0) + 1
        elif "Арбуз" in item['name']:
            u['inv_watermelon'] = u.get('inv_watermelon', 0) + 1
        elif "Манго" in item['name']:
            u['inv_mango'] = u.get('inv_mango', 0) + 1
        elif "Киви" in item['name']:
            u['inv_kiwi'] = u.get('inv_kiwi', 0) + 1
        elif "Кокос" in item['name']:
            u['inv_coconut'] = u.get('inv_coconut', 0) + 1
    
    u["wolf_active"] = False
    u["wolf_item"] = None
    u["next_visitor"] = "owl"
    await save_u(u)
    
    await query.answer("💰 Товар успешно приобретён!", show_alert=True)
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

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
    
    print(f"Скин: {skin}, Шанс кражи: {steal_chance}%")
    
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
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

# ============= ОСНОВНЫЕ КОМАНДЫ =============

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    now = time.time()
    
    await check_and_activate_visitor(u, update, context)
    
    if u.get("wolf_active", False) or u.get("owl_active", False):
        return
    
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    
    await update.message.reply_text(f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}", reply_markup=main_kb())

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰", callback_data="sell"),
         InlineKeyboardButton("🥚", callback_data="eggs"),
         InlineKeyboardButton("🍭", callback_data="treats"),
         InlineKeyboardButton("⭐️", callback_data="premium")]
    ])
    await update.message.reply_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def premium_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🛠️ В разработке", show_alert=True)

async def treats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 100 * (100 - discount) // 100
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍭 Купить угощение", callback_data="buy_treat")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(f"🍭 Покупка угощений.\n💸 Курс: 1 🍭 = {price} 🐾", reply_markup=kb)

async def buy_treat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 100 * (100 - discount) // 100
    
    if u['balance'] < price:
        await query.answer(f"❌ Недостаточно копытц! Нужно {price} 🐾", show_alert=True)
        return
    
    u['balance'] -= price
    treat = random.choices(TREATS, weights=TREAT_WEIGHTS)[0]
    
    if treat == "🍏 Яблоко":
        u['inv_apple'] = u.get('inv_apple', 0) + 1
    elif treat == "🫐 Черника":
        u['inv_blueberry'] = u.get('inv_blueberry', 0) + 1
    elif treat == "🍉 Арбуз":
        u['inv_watermelon'] = u.get('inv_watermelon', 0) + 1
    elif treat == "🥭 Манго":
        u['inv_mango'] = u.get('inv_mango', 0) + 1
    elif treat == "🥝 Киви":
        u['inv_kiwi'] = u.get('inv_kiwi', 0) + 1
    elif treat == "🥥 Кокос":
        u['inv_coconut'] = u.get('inv_coconut', 0) + 1
    
    await save_u(u)
    await query.answer(f"🍭 Ты купил угощение!\n✨ Получено: {treat}", show_alert=True)
    await treats_menu(update, context)

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    text = (f"🎒 Инвентарь.\n"
            f"🍏 {u.get('inv_apple',0)} | 🫐 {u.get('inv_blueberry',0)} | 🍉 {u.get('inv_watermelon',0)}\n"
            f"🥭 {u.get('inv_mango',0)} | 🥝 {u.get('inv_kiwi',0)} | 🥥 {u.get('inv_coconut',0)}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚡️ Использовать", callback_data="use_menu")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])
    await query.edit_message_text(text, reply_markup=kb)

async def use_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    effect = get_current_effect(u)
    text = (f"⚡️ Выбери, что хочешь использовать.\n"
            f"⭐️ Эффект: {effect}\n")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍏", callback_data="use_apple"),
         InlineKeyboardButton("🫐", callback_data="use_blueberry"),
         InlineKeyboardButton("🍉", callback_data="use_watermelon")],
        [InlineKeyboardButton("🥭", callback_data="use_mango"),
         InlineKeyboardButton("🥝", callback_data="use_kiwi"),
         InlineKeyboardButton("🥥", callback_data="use_coconut")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="inventory")]
    ])
    await query.edit_message_text(text, reply_markup=kb)

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
    
    await save_u(u)
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
    price = 200 * (100 - discount) // 100
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Купить яйцо", callback_data="open_egg")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(f"🥚 Покупка яиц.\n💸 Курс: 1 🥚 = {price} 🐾", reply_markup=kb)

async def open_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 200 * (100 - discount) // 100
    
    if u['balance'] < price:
        await query.answer(f"❌ Недостаточно копытц! Нужно {price} 🐾", show_alert=True)
        return
    
    u['balance'] -= price
    r_l = list(RARITIES.keys())
    rarity = random.choices(r_l, weights=[RARITIES[k]["w"] for k in r_l])[0]
    u['skin'] = random.choice(RARITIES[rarity]['items'])
    await save_u(u)
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
    await query.edit_message_text("💰 Продажа шерсти.\n💸 Курс: 1 🧶 = 10 🐾", reply_markup=kb)

async def sell_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    if u['wool'] <= 0:
        await query.answer("🐑 Мее! Сначала постриги овечку.", show_alert=True)
        return
    
    v = u['wool'] * 10
    u['balance'] += v
    u['wool'] = 0
    await save_u(u)
    await query.answer(f"💰 Ты успешно продал всю шерсть!\nПолучено: {v} 🐾", show_alert=True)
    await sell_menu(update, context)

async def shear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    now = time.time()
    
    wool_boost = u.get("buff_wool_boost", 0) and now < u.get("buff_wool_boost_expires", 0)
    
    if u['shearing']:
        if now >= u['s_finish']:
            if wool_boost:
                gain = random.randint(15, 25)
            elif u.get("buff_mango_wool", 0) or u.get("buff_coconut_wool", 0):
                gain = random.randint(15, 25)
            else:
                gain = random.randint(5, 15)
            
            if u.get("buff_apple_wool", 0):
                gain += 5
            
            u['wool'] += gain
            u['shearing'] = 0
            u['harvest'] = now + 12 * 3600
            
            if u.get("buff_apple_wool", 0):
                u["buff_apple_wool"] = 0
            if u.get("buff_mango_wool", 0):
                u["buff_mango_wool"] = 0
            if u.get("buff_coconut_wool", 0):
                u["buff_coconut_wool"] = 0
            
            await save_u(u)
            await query.edit_message_text(f"🐑 Овечка успешно пострижена! Получено: {gain} 🧶", reply_markup=main_kb())
        else:
            rem = int(u['s_finish'] - now)
            m, s = divmod(rem, 60)
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("⌛️ Проверить время", callback_data="shear")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
            ])
            await query.edit_message_text(f"✂️ Стрижём твою овечку. ⏳ Процесс займет: {m} мин. {s} сек.", reply_markup=kb)
    elif now < u['harvest']:
        await query.answer("❌ Ещё не готова!", show_alert=True)
    else:
        u['shearing'] = 1
        u['s_finish'] = now + 300
        await save_u(u)
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⌛️ Проверить время", callback_data="shear")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
        ])
        await query.edit_message_text("✂️ Стрижём твою овечку. ⏳ Процесс займет: 5 мин.", reply_markup=kb)

async def market_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰", callback_data="sell"),
         InlineKeyboardButton("🥚", callback_data="eggs"),
         InlineKeyboardButton("🍭", callback_data="treats")]
    ])
    await query.edit_message_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if await check_visitor_on_action(update, context):
        return
    
    u = await get_u(query.from_user.id)
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    await query.edit_message_text(f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}", reply_markup=main_kb())

# ============= АДМИН КОМАНДЫ =============

async def give_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Использование: /give <сумма> <user_id>\nПример: /give 500 50302058")
        return
    try:
        amount = int(args[0])
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: сумма и ID должны быть числами.")
        return
    if amount <= 0:
        await update.message.reply_text("❌ Сумма должна быть больше 0.")
        return
    u = await get_u(target_id)
    u['balance'] += amount
    await save_u(u)
    await update.message.reply_text(f"✅ Добавлено {amount} 🐾 игроку с ID {target_id}.")

async def effect_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Использование: /effect 0 <user_id>\nПример: /effect 0 5030258")
        return
    try:
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом.")
        return
    u = await get_u(target_id)
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
    u["buff_treat_boost"] = 0
    u["buff_treat_boost_expires"] = 0
    u["buff_luck_boost"] = 0
    u["buff_luck_boost_expires"] = 0
    u["buff_wolf_immunity"] = 0
    u["buff_wolf_immunity_expires"] = 0
    u["buff_wool_boost"] = 0
    u["buff_wool_boost_expires"] = 0
    u["buff_market_discount"] = 0
    u["buff_market_discount_expires"] = 0
    await save_u(u)
    await update.message.reply_text(f"✅ Эффекты обнулены у игрока с ID {target_id}.")

def main():
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("wolf", wolf_cmd))  # Только для владельца
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("effect", effect_cmd))
    
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
    application.add_handler(CallbackQueryHandler(treats_menu, pattern="^treats$"))
    application.add_handler(CallbackQueryHandler(buy_treat, pattern="^buy_treat$"))
    application.add_handler(CallbackQueryHandler(market_main, pattern="^market_main$"))
    application.add_handler(CallbackQueryHandler(premium_placeholder, pattern="^premium$"))
    application.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(shear, pattern="^shear$"))
    
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
