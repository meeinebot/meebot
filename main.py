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
    "🔵 Редкая": 5,
    "🟣 Эпическая": 15,
    "🟡 Легендарная": 25,
    "🔴 Мифическая": 50
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
        "inv_apple": 0,
        "inv_blueberry": 0,
        "inv_watermelon": 0,
        "inv_mango": 0,
        "inv_kiwi": 0,
        "inv_coconut": 0,
        "buff_apple": 0,
        "buff_apple_immunity_expires": 0,
        "buff_apple_wool": 0,
        "buff_blueberry": 0,
        "buff_blueberry_immunity_expires": 0,
        "buff_blueberry_discount_expires": 0,
        "buff_watermelon": 0,
        "buff_watermelon_immunity_expires": 0,
        "buff_watermelon_passive_expires": 0,
        "buff_mango": 0,
        "buff_mango_immunity_expires": 0,
        "buff_mango_wool": 0,
        "buff_kiwi": 0,
        "buff_kiwi_immunity_expires": 0,
        "buff_kiwi_passive_expires": 0,
        "buff_kiwi_discount_expires": 0,
        "buff_coconut": 0,
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
        if user.get("buff_watermelon", 0) and now < user.get("buff_watermelon_passive_expires", 0):
            income_per_hour *= 2
        if user.get("buff_kiwi", 0) and now < user.get("buff_kiwi_passive_expires", 0):
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
    if u.get("buff_apple", 0) and now < u.get("buff_apple_immunity_expires", 0):
        return "🍏 Яблоко"
    if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_immunity_expires", 0):
        return "🫐 Черника"
    if u.get("buff_watermelon", 0) and now < u.get("buff_watermelon_immunity_expires", 0):
        return "🍉 Арбуз"
    if u.get("buff_mango", 0) and now < u.get("buff_mango_immunity_expires", 0):
        return "🥭 Манго"
    if u.get("buff_kiwi", 0) and now < u.get("buff_kiwi_immunity_expires", 0):
        return "🥝 Киви"
    if u.get("buff_coconut", 0) and now < u.get("buff_coconut_immunity_expires", 0):
        return "🥥 Кокос"
    return "🚫 Неактивен"

def get_discount(u: dict) -> int:
    now = time.time()
    discount = 0
    if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_discount_expires", 0):
        discount = max(discount, 10)
    if u.get("buff_kiwi", 0) and now < u.get("buff_kiwi_discount_expires", 0):
        discount = max(discount, 10)
    if u.get("buff_coconut", 0) and now < u.get("buff_coconut_discount_expires", 0):
        discount = max(discount, 10)
    return discount

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    now = time.time()
    
    # Принудительный Волк
    if context.user_data.get("wolf_active", False):
        item = context.user_data.get("wolf_item")
        if item:
            text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
            if u['balance'] < item['price']:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy_no_money")],
                    [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
                ])
            else:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
                    [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
                ])
            await update.message.reply_text(text, reply_markup=keyboard)
            return
    
    # Обычный Волк (50% шанс)
    msk = timezone(timedelta(hours=3))
    last_offer = u.get("wolf_last_offer", 0)
    last_date = datetime.fromtimestamp(last_offer, tz=msk).date() if last_offer else None
    today = datetime.now(tz=msk).date()
    
    if last_date != today and random.random() < 0.5:
        u["wolf_last_offer"] = now
        await save_u(u)
        item = random.choice(WOLF_ITEMS)
        context.user_data["wolf_item"] = item
        context.user_data["wolf_active"] = True
        text = f"🐺 Странный торговец.\n«Товары на любой вкус»\n{item['name']} – {item['price']} 🐾"
        if u['balance'] < item['price']:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy_no_money")],
                [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
            ])
        else:
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("💰 Приобрести", callback_data="wolf_buy")],
                [InlineKeyboardButton("❌ Отказаться", callback_data="wolf_refuse")]
            ])
        await update.message.reply_text(text, reply_markup=keyboard)
        return
    
    # Профиль
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    await update.message.reply_text(f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}", reply_markup=main_kb())

async def wolf_buy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    item = context.user_data.get("wolf_item")
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
    
    await save_u(u)
    await query.answer("💰 Товар успешно приобретён!", show_alert=True)
    
    context.user_data["wolf_active"] = False
    context.user_data.pop("wolf_item", None)
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

async def wolf_buy_no_money(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("❌ Недостаточно средств!", show_alert=True)

async def wolf_refuse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    skin = u.get("skin", "🐑 Обычная овечка")
    
    now = time.time()
    has_immunity = (
        (u.get("buff_apple", 0) and now < u.get("buff_apple_immunity_expires", 0)) or
        (u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_immunity_expires", 0)) or
        (u.get("buff_watermelon", 0) and now < u.get("buff_watermelon_immunity_expires", 0)) or
        (u.get("buff_mango", 0) and now < u.get("buff_mango_immunity_expires", 0)) or
        (u.get("buff_kiwi", 0) and now < u.get("buff_kiwi_immunity_expires", 0)) or
        (u.get("buff_coconut", 0) and now < u.get("buff_coconut_immunity_expires", 0))
    )
    
    if has_immunity:
        steal_chance = 0
    else:
        steal_chance = WOLF_STEAL_CHANCES.get(skin, 0)
    
    context.user_data["wolf_active"] = False
    context.user_data.pop("wolf_item", None)
    
    if random.random() * 100 < steal_chance:
        old_skin = u["skin"]
        u["skin"] = "🐑 Обычная овечка"
        await save_u(u)
        await query.answer(f"🐺 Странный торговец схватил твою {old_skin} и сбежал!", show_alert=True)
    else:
        await query.answer("🐺 Странный торговец ушёл..", show_alert=True)  # ДВЕ ТОЧКИ!
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

async def wolf_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != OWNER_ID:
        return
    args = context.args
    if len(args) < 2:
        await update.message.reply_text("❌ Использование: /wolf <фрукт> <user_id>\nПример: /wolf 🥝 1542663387")
        return
    try:
        fruit_emoji = args[0]
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: ID должен быть числом.")
        return
    fruit_map = {
        "🍏": {"name": "🍏 Яблоко", "price": 49},
        "🫐": {"name": "🫐 Черника", "price": 99},
        "🍉": {"name": "🍉 Арбуз", "price": 149},
        "🥭": {"name": "🥭 Манго", "price": 199},
        "🥝": {"name": "🥝 Киви", "price": 249},
        "🥥": {"name": "🥥 Кокос", "price": 299},
    }
    if fruit_emoji not in fruit_map:
        await update.message.reply_text("❌ Неизвестный фрукт. Доступные: 🍏 🫐 🍉 🥭 🥝 🥥")
        return
    u = await get_u(target_id)
    if not u:
        await update.message.reply_text("❌ Игрок с таким ID не найден.")
        return
    u["wolf_last_offer"] = time.time() - 86400
    await save_u(u)
    context.user_data["wolf_item"] = {"name": fruit_map[fruit_emoji]["name"], "price": fruit_map[fruit_emoji]["price"]}
    context.user_data["wolf_active"] = True
    await update.message.reply_text(f"🐺 Волк с товаром {fruit_emoji} будет ждать игрока с ID {target_id} при следующем /sheep.")

async def clan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Создать", callback_data="clan_create"),
         InlineKeyboardButton("🔍 Поиск", callback_data="clan_find")]
    ])
    await update.message.reply_text("⭐️ Ты ещё не в клане!\nВыбери, что хочешь сделать.", reply_markup=kb)

async def clan_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🛠️ В разработке", show_alert=True)

async def clan_find(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🛠️ В разработке", show_alert=True)

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚", callback_data="eggs"),
         InlineKeyboardButton("💰", callback_data="sell"),
         InlineKeyboardButton("🍭", callback_data="treats"),
         InlineKeyboardButton("⭐️", callback_data="premium")]
    ])
    await update.message.reply_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def premium_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🛠️ В разработке", show_alert=True)

async def treats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    discount = get_discount(u)
    price = 100 * (100 - discount) // 100
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍭 Купить сладость", callback_data="buy_treat")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(f"🍭 Покупка сладостей.\n💸 Курс: 1 🍭 = {price} 🐾", reply_markup=kb)

async def buy_treat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
    await query.answer(f"🍭 Ты купил сладость!\n✨ Получено: {treat}", show_alert=True)
    await treats_menu(update, context)

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
    u = await get_u(query.from_user.id)
    if u.get(inv_field, 0) <= 0:
        await query.answer("❌ У тебя нет этого угощения!", show_alert=True)
        return
    u[inv_field] -= 1
    now = time.time()
    
    u["buff_apple"] = 0
    u["buff_apple_immunity_expires"] = 0
    u["buff_apple_wool"] = 0
    u["buff_blueberry"] = 0
    u["buff_blueberry_immunity_expires"] = 0
    u["buff_blueberry_discount_expires"] = 0
    u["buff_watermelon"] = 0
    u["buff_watermelon_immunity_expires"] = 0
    u["buff_watermelon_passive_expires"] = 0
    u["buff_mango"] = 0
    u["buff_mango_immunity_expires"] = 0
    u["buff_mango_wool"] = 0
    u["buff_kiwi"] = 0
    u["buff_kiwi_immunity_expires"] = 0
    u["buff_kiwi_passive_expires"] = 0
    u["buff_kiwi_discount_expires"] = 0
    u["buff_coconut"] = 0
    u["buff_coconut_immunity_expires"] = 0
    u["buff_coconut_wool"] = 0
    u["buff_coconut_discount_expires"] = 0
    
    if fruit_key == "apple":
        u["buff_apple"] = 1
        u["buff_apple_immunity_expires"] = now + 6 * 3600
        u["buff_apple_wool"] = 1
    elif fruit_key == "blueberry":
        u["buff_blueberry"] = 1
        u["buff_blueberry_immunity_expires"] = now + 6 * 3600
        u["buff_blueberry_discount_expires"] = now + 6 * 3600
    elif fruit_key == "watermelon":
        u["buff_watermelon"] = 1
        u["buff_watermelon_immunity_expires"] = now + 12 * 3600
        u["buff_watermelon_passive_expires"] = now + 12 * 3600
    elif fruit_key == "mango":
        u["buff_mango"] = 1
        u["buff_mango_immunity_expires"] = now + 12 * 3600
        u["buff_mango_wool"] = 1
    elif fruit_key == "kiwi":
        u["buff_kiwi"] = 1
        u["buff_kiwi_immunity_expires"] = now + 18 * 3600
        u["buff_kiwi_passive_expires"] = now + 12 * 3600
        u["buff_kiwi_discount_expires"] = now + 6 * 3600
    elif fruit_key == "coconut":
        u["buff_coconut"] = 1
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
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Продать шерсть", callback_data="sell_confirm")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text("💰 Продажа шерсти.\n💸 Курс: 1 🧶 = 10 🐾", reply_markup=kb)

async def sell_confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
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
    u = await get_u(query.from_user.id)
    now = time.time()
    if u['shearing']:
        if now >= u['s_finish']:
            if u.get("buff_mango", 0) or u.get("buff_coconut", 0):
                gain = random.randint(15, 25)
            else:
                gain = random.randint(5, 15)
            if u.get("buff_apple", 0):
                gain += 5
            u['wool'] += gain
            u['shearing'] = 0
            u['harvest'] = now + 12 * 3600
            if u.get("buff_apple", 0):
                u["buff_apple_wool"] = 0
            if u.get("buff_mango", 0):
                u["buff_mango_wool"] = 0
            if u.get("buff_coconut", 0):
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
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚", callback_data="eggs"),
         InlineKeyboardButton("💰", callback_data="sell"),
         InlineKeyboardButton("🍭", callback_data="treats")]
    ])
    await query.edit_message_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def back(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    await query.edit_message_text(f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}", reply_markup=main_kb())

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
    u["buff_apple"] = 0
    u["buff_apple_immunity_expires"] = 0
    u["buff_apple_wool"] = 0
    u["buff_blueberry"] = 0
    u["buff_blueberry_immunity_expires"] = 0
    u["buff_blueberry_discount_expires"] = 0
    u["buff_watermelon"] = 0
    u["buff_watermelon_immunity_expires"] = 0
    u["buff_watermelon_passive_expires"] = 0
    u["buff_mango"] = 0
    u["buff_mango_immunity_expires"] = 0
    u["buff_mango_wool"] = 0
    u["buff_kiwi"] = 0
    u["buff_kiwi_immunity_expires"] = 0
    u["buff_kiwi_passive_expires"] = 0
    u["buff_kiwi_discount_expires"] = 0
    u["buff_coconut"] = 0
    u["buff_coconut_immunity_expires"] = 0
    u["buff_coconut_wool"] = 0
    u["buff_coconut_discount_expires"] = 0
    await save_u(u)
    await update.message.reply_text(f"✅ Эффекты обнулены у игрока с ID {target_id}.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("clan", clan_cmd))
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CommandHandler("effect", effect_cmd))
    application.add_handler(CommandHandler("wolf", wolf_cmd))
    application.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    application.add_handler(CallbackQueryHandler(use_menu, pattern="^use_menu$"))
    application.add_handler(CallbackQueryHandler(use_apple, pattern="^use_apple$"))
    application.add_handler(CallbackQueryHandler(use_blueberry, pattern="^use_blueberry$"))
    application.add_handler(CallbackQueryHandler(use_watermelon, pattern="^use_watermelon$"))
    application.add_handler(CallbackQueryHandler(use_mango, pattern="^use_mango$"))
    application.add_handler(CallbackQueryHandler(use_kiwi, pattern="^use_kiwi$"))
    application.add_handler(CallbackQueryHandler(use_coconut, pattern="^use_coconut$"))
    application.add_handler(CallbackQueryHandler(wolf_buy, pattern="^wolf_buy$"))
    application.add_handler(CallbackQueryHandler(wolf_buy_no_money, pattern="^wolf_buy_no_money$"))
    application.add_handler(CallbackQueryHandler(wolf_refuse, pattern="^wolf_refuse$"))
    application.add_handler(CallbackQueryHandler(eggs_menu, pattern="^eggs$"))
    application.add_handler(CallbackQueryHandler(open_egg, pattern="^open_egg$"))
    application.add_handler(CallbackQueryHandler(sell_menu, pattern="^sell$"))
    application.add_handler(CallbackQueryHandler(sell_confirm, pattern="^sell_confirm$"))
    application.add_handler(CallbackQueryHandler(treats_menu, pattern="^treats$"))
    application.add_handler(CallbackQueryHandler(buy_treat, pattern="^buy_treat$"))
    application.add_handler(CallbackQueryHandler(market_main, pattern="^market_main$"))
    application.add_handler(CallbackQueryHandler(premium_placeholder, pattern="^premium$"))
    application.add_handler(CallbackQueryHandler(clan_create, pattern="^clan_create$"))
    application.add_handler(CallbackQueryHandler(clan_find, pattern="^clan_find$"))
    application.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(shear, pattern="^shear$"))
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()
