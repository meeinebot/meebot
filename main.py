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
    if u.get("buff_apple", 0):
        return "🍏 Яблоко"
    if u.get("buff_watermelon", 0):
        return "🍉 Арбуз"
    if u.get("buff_kiwi", 0):
        return "🥝 Киви"
    if u.get("buff_coconut", 0):
        return "🥥 Кокос"
    if u.get("buff_lime", 0):
        return "🍋‍🟩 Лайм"
    if u.get("buff_lemon", 0):
        return "🍋 Лимон"
    if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_expires", 0):
        return "🫐 Черника"
    if u.get("buff_mango", 0) and now < u.get("buff_mango_expires", 0):
        return "🥭 Манго"
    return "🚫 Неактивен"

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
    
    # Волк раз в день (00:00 МСК), шанс 50%
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
        await query.answer("❌ Ошибка", show_alert=True)
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
         InlineKeyboardButton("⭐️", callback_data="premium")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])
    await update.message.reply_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def premium_placeholder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer("🛠️ В разработке", show_alert=True)

async def treats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍭 Купить гостинец", callback_data="buy_treat")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text("🍭 Покупка гостинцев.\n💸 Курс: 1 🍭 = 100 🐾", reply_markup=kb)

# Остальные функции (inventory, use_menu, use_fruit, eggs, sell, buy_treat, shear, back, give_cmd) без изменений, они уже есть в предыдущем коде

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
