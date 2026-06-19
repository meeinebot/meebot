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

TREATS = ["🍏 Яблоко", "🫐 Черника", "🍉 Арбуз", "🥭 Манго", "🥝 Киви", "🥥 Кокос", "🍋‍🟩 Лайм", "🍋 Лимон"]
TREAT_WEIGHTS = [40, 30, 20, 10, 10, 10, 5, 5]

WOLF_ITEMS = [
    {"name": "🫐 Черника", "price": 49},
    {"name": "🍉 Арбуз", "price": 99},
    {"name": "🥝 Киви", "price": 149},
    {"name": "🍋‍🟩 Лайм", "price": 199},
    {"name": "🍉 Арбуз + 🥝 Киви", "price": 249},
    {"name": "🫐 Черника + 🍋‍🟩 Лайм", "price": 249},
    {"name": "🍉 Арбуз + 🥝 Киви + 🍋‍🟩 Лайм", "price": 349},
    {"name": "🟡 Легендарное яйцо", "price": 249},
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
        "inv_lime": 0,
        "inv_lemon": 0,
        "buff_apple": 0,
        "buff_blueberry": 0,
        "buff_blueberry_expires": 0,
        "buff_watermelon": 0,
        "buff_mango": 0,
        "buff_mango_expires": 0,
        "buff_kiwi": 0,
        "buff_coconut": 0,
        "buff_lime": 0,
        "buff_lemon": 0
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
        if user.get("buff_blueberry", 0) and now < user.get("buff_blueberry_expires", 0):
            income_per_hour *= 2
        if user.get("buff_mango", 0) and now < user.get("buff_mango_expires", 0):
            income_per_hour *= 2
        if user.get("buff_kiwi", 0):
            income_per_hour *= 2
        if user.get("buff_lime", 0):
            income_per_hour *= 2
        if user.get("buff_lemon", 0):
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
    if u.get("buff_lemon", 0):
        return "🍋 Лимон"
    if u.get("buff_coconut", 0):
        return "🥥 Кокос"
    if u.get("buff_mango", 0) and now < u.get("buff_mango_expires", 0):
        return "🥭 Манго"
    if u.get("buff_apple", 0):
        return "🍏 Яблоко"
    if u.get("buff_watermelon", 0):
        return "🍉 Арбуз"
    if u.get("buff_kiwi", 0):
        return "🥝 Киви"
    if u.get("buff_lime", 0):
        return "🍋‍🟩 Лайм"
    if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_expires", 0):
        return "🫐 Черника"
    return "🚫 Неактивен"

def get_discount(u: dict) -> int:
    now = time.time()
    discount = 0
    if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_expires", 0):
        discount = max(discount, 5)      # Черника 5%
    if u.get("buff_mango", 0) and now < u.get("buff_mango_expires", 0):
        discount = max(discount, 10)     # Манго 10%
    if u.get("buff_coconut", 0):
        discount = max(discount, 15)     # Кокос 15%
    if u.get("buff_lime", 0):
        discount = max(discount, 20)     # Лайм 20%
    if u.get("buff_lemon", 0):
        discount = max(discount, 25)     # Лимон 25%
    return discount

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    u = await get_u(user_id)
    now = time.time()
    
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
    
    msk = timezone(timedelta(hours=3))
    last_offer = u.get("wolf_last_offer", 0)
    last_date = datetime.fromtimestamp(last_offer, tz=msk).date() if last_offer else None
    today = datetime.now(tz=msk).date()
    
    if last_date != today and random.random() < 0.75:
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
    
    if "Легендарное яйцо" in item['name']:
        legendary_items = RARITIES["🟡 Легендарная"]["items"]
        new_skin = random.choice(legendary_items)
        u['skin'] = new_skin
        await save_u(u)
        await query.answer(f"🥚 Ты открыл яйцо! Тебе выпала: {new_skin}.", show_alert=True)
    else:
        if "Черника" in item['name']:
            u['inv_blueberry'] = u.get('inv_blueberry', 0) + 1
        elif "Арбуз" in item['name']:
            u['inv_watermelon'] = u.get('inv_watermelon', 0) + 1
        elif "Киви" in item['name']:
            u['inv_kiwi'] = u.get('inv_kiwi', 0) + 1
        elif "Лайм" in item['name']:
            u['inv_lime'] = u.get('inv_lime', 0) + 1
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
    
    if u.get("buff_apple", 0) or u.get("buff_mango", 0) or u.get("buff_coconut", 0) or u.get("buff_lemon", 0):
        steal_chance = 0
    else:
        steal_chance = WOLF_STEAL_CHANCES.get(skin, 0)
    
    context.user_data["wolf_active"] = False
    context.user_data.pop("wolf_item", None)
    
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    text = f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}"
    await query.edit_message_text(text, reply_markup=main_kb())

async def clan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤝 Создать", callback_data="clan_create")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="clan_find")]
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
        [InlineKeyboardButton("🍭 Купить гостинец", callback_data="buy_treat")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text(f"🍭 Покупка гостинцев.\n💸 Курс: 1 🍭 = {price} 🐾", reply_markup=kb)

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
    elif treat == "🍋‍🟩 Лайм":
        u['inv_lime'] = u.get('inv_lime', 0) + 1
    elif treat == "🍋 Лимон":
        u['inv_lemon'] = u.get('inv_lemon', 0) + 1
    await save_u(u)
    await query.answer(f"🍭 Ты купил гостинец!\n✨ Получено: {treat}", show_alert=True)
    await treats_menu(update, context)

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    text = (f"🎒 Инвентарь.\n"
            f"🍏 {u.get('inv_apple',0)} | 🫐 {u.get('inv_blueberry',0)} | 🍉 {u.get('inv_watermelon',0)} | 🥭 {u.get('inv_mango',0)}\n"
            f"🥝 {u.get('inv_kiwi',0)} | 🥥 {u.get('inv_coconut',0)} | 🍋‍🟩 {u.get('inv_lime',0)} | 🍋 {u.get('inv_lemon',0)}")
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
         InlineKeyboardButton("🍉", callback_data="use_watermelon"),
         InlineKeyboardButton("🥭", callback_data="use_mango")],
        [InlineKeyboardButton("🥝", callback_data="use_kiwi"),
         InlineKeyboardButton("🥥", callback_data="use_coconut"),
         InlineKeyboardButton("🍋‍🟩", callback_data="use_lime"),
         InlineKeyboardButton("🍋", callback_data="use_lemon")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="inventory")]
    ])
    await query.edit_message_text(text, reply_markup=kb)

async def use_fruit(update: Update, context: ContextTypes.DEFAULT_TYPE, fruit_key: str, inv_field: str, buff_field: str):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u.get(inv_field, 0) <= 0:
        await query.answer("❌ У тебя нет этого угощения!", show_alert=True)
        return
    u[inv_field] -= 1
    now = time.time()
    
    # Сбрасываем все активные баффы
    u["buff_apple"] = 0
    u["buff_blueberry"] = 0
    u["buff_watermelon"] = 0
    u["buff_kiwi"] = 0
    u["buff_coconut"] = 0
    u["buff_lime"] = 0
    u["buff_lemon"] = 0
    u["buff_mango"] = 0
    
    # Активируем новый бафф
    if fruit_key == "apple":
        u[buff_field] = 1
    elif fruit_key == "blueberry":
        u[buff_field] = 1
        u["buff_blueberry_expires"] = now + 6 * 3600
    elif fruit_key == "watermelon":
        u[buff_field] = 1
    elif fruit_key == "mango":
        u[buff_field] = 1
        u["buff_mango_expires"] = now + 6 * 3600
    elif fruit_key == "kiwi":
        u[buff_field] = 1
    elif fruit_key == "coconut":
        u[buff_field] = 1
    elif fruit_key == "lime":
        u[buff_field] = 1
    elif fruit_key == "lemon":
        u[buff_field] = 1
    else:
        return
    
    await save_u(u)
    await query.answer("⭐️ Угощение успешно активировано!", show_alert=True)
    await use_menu(update, context)

async def use_apple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "apple", "inv_apple", "buff_apple")

async def use_blueberry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "blueberry", "inv_blueberry", "buff_blueberry")

async def use_watermelon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "watermelon", "inv_watermelon", "buff_watermelon")

async def use_mango(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "mango", "inv_mango", "buff_mango")

async def use_kiwi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "kiwi", "inv_kiwi", "buff_kiwi")

async def use_coconut(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "coconut", "inv_coconut", "buff_coconut")

async def use_lime(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "lime", "inv_lime", "buff_lime")

async def use_lemon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_fruit(update, context, "lemon", "inv_lemon", "buff_lemon")

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
            gain = random.randint(5, 15)
            if u.get('buff_kiwi', 0) or u.get('buff_lime', 0):
                gain = random.randint(15, 25)
            u['wool'] += gain
            u['shearing'] = 0
            base_cooldown = 6 * 3600 if u.get('buff_watermelon', 0) else 12 * 3600
            u['harvest'] = now + base_cooldown
            u['buff_watermelon'] = 0
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
        await update.message.reply_text("❌ Использование: /give <количество> <user_id>")
        return
    try:
        amount = int(args[0])
        target_id = int(args[1])
    except ValueError:
        await update.message.reply_text("❌ Ошибка: количество и ID должны быть числами.")
        return
    u = await get_u(target_id)
    u['balance'] += amount
    await save_u(u)
    await update.message.reply_text(f"✅ Передано {amount} 🐾 игроку с ID {target_id}.")

def main():
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CommandHandler("clan", clan_cmd))
    application.add_handler(CommandHandler("give", give_cmd))
    application.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    application.add_handler(CallbackQueryHandler(use_menu, pattern="^use_menu$"))
    application.add_handler(CallbackQueryHandler(use_apple, pattern="^use_apple$"))
    application.add_handler(CallbackQueryHandler(use_blueberry, pattern="^use_blueberry$"))
    application.add_handler(CallbackQueryHandler(use_watermelon, pattern="^use_watermelon$"))
    application.add_handler(CallbackQueryHandler(use_mango, pattern="^use_mango$"))
    application.add_handler(CallbackQueryHandler(use_kiwi, pattern="^use_kiwi$"))
    application.add_handler(CallbackQueryHandler(use_coconut, pattern="^use_coconut$"))
    application.add_handler(CallbackQueryHandler(use_lime, pattern="^use_lime$"))
    application.add_handler(CallbackQueryHandler(use_lemon, pattern="^use_lemon$"))
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
