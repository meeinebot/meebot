import asyncio
import random
import time
import threading
import os
import aiosqlite
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")
DB_PATH = "sheep_farm.db"
OWNER_ID = 1864104580  # твой ID

RARITIES = {
    "🔵 Редкая": {"items": ["🏡 Деревенская овечка", "🏖️ Пляжная овечка", "💤 Сонная овечка"], "w": 40},
    "🟣 Эпическая": {"items": ["💥 Шизанутая овечка", "🎀 Милая овечка", "🍭 Карамельная овечка"], "w": 30},
    "🟡 Легендарная": {"items": ["🔥 Магмовая овечка", "💎 Бриллиантовая овечка", "🐚 Жемчужная овечка"], "w": 20},
    "🔴 Мифическая": {"items": ["👼 Священная овечка", "👻 Призрачная овечка", "🕯️ Ритуальная овечка"], "w": 10}
}

TREATS = ["🍏 Яблоко", "🫐 Черника", "🍉 Арбуз", "🥭 Манго", "🥝 Киви", "🥥 Кокос", "🍋‍🟩 Лайм", "🍋 Лимон"]
TREAT_WEIGHTS = [40, 30, 20, 10, 10, 10, 5, 5]

FRUIT_EFFECTS = {
    "apple": "🍏 Яблоко: иммунитет от волков 6ч",
    "blueberry": "🫐 Черника: скидка 10% в магазине 6ч",
    "watermelon": "🍉 Арбуз: пассивка x2 12ч",
    "mango": "🥭 Манго: иммунитет 12ч + скидка 10% 6ч",
    "kiwi": "🥝 Киви: удвоение шерсти + пассивка x2 12ч",
    "coconut": "🥥 Кокос: иммунитет 24ч + скидка 15% 12ч",
    "lime": "🍋‍🟩 Лайм: пассивка x2 12ч + удвоение шерсти + скидка 10% 6ч",
    "lemon": "🍋 Лимон: иммунитет 48ч + пассивка x2 12ч + скидка 10% 12ч"
}

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY,
                skin TEXT NOT NULL DEFAULT '🐑 Обычная овечка',
                balance INTEGER NOT NULL DEFAULT 0,
                wool INTEGER NOT NULL DEFAULT 0,
                harvest REAL NOT NULL DEFAULT 0,
                shearing INTEGER NOT NULL DEFAULT 0,
                s_finish REAL NOT NULL DEFAULT 0,
                last_active REAL NOT NULL DEFAULT 0,
                inv_apple INTEGER DEFAULT 0,
                inv_blueberry INTEGER DEFAULT 0,
                inv_watermelon INTEGER DEFAULT 0,
                inv_mango INTEGER DEFAULT 0,
                inv_kiwi INTEGER DEFAULT 0,
                inv_coconut INTEGER DEFAULT 0,
                inv_lime INTEGER DEFAULT 0,
                inv_lemon INTEGER DEFAULT 0,
                buff_apple INTEGER DEFAULT 0,
                buff_blueberry INTEGER DEFAULT 0,
                buff_blueberry_expires REAL DEFAULT 0,
                buff_watermelon INTEGER DEFAULT 0,
                buff_mango INTEGER DEFAULT 0,
                buff_mango_expires REAL DEFAULT 0,
                buff_kiwi INTEGER DEFAULT 0,
                buff_coconut INTEGER DEFAULT 0,
                buff_lime INTEGER DEFAULT 0,
                buff_lemon INTEGER DEFAULT 0
            )
        """)
        cols = ["inv_apple", "inv_blueberry", "inv_watermelon", "inv_mango", "inv_kiwi", "inv_coconut", "inv_lime", "inv_lemon",
                "buff_apple", "buff_blueberry", "buff_blueberry_expires", "buff_watermelon", "buff_mango", "buff_mango_expires",
                "buff_kiwi", "buff_coconut", "buff_lime", "buff_lemon"]
        for col in cols:
            try:
                await db.execute(f"ALTER TABLE players ADD COLUMN {col} INTEGER DEFAULT 0")
            except:
                pass
        await db.commit()

async def get_u(uid: int) -> dict:
    now = time.time()
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM players WHERE id = ?", (uid,)) as cursor:
            row = await cursor.fetchone()
        if not row:
            u = {
                "id": uid,
                "skin": "🐑 Обычная овечка",
                "balance": 0,
                "wool": 0,
                "harvest": now,
                "shearing": 0,
                "s_finish": 0,
                "last_active": now,
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
            await db.execute(
                "INSERT INTO players (id, skin, balance, wool, harvest, shearing, s_finish, last_active, "
                "inv_apple, inv_blueberry, inv_watermelon, inv_mango, inv_kiwi, inv_coconut, inv_lime, inv_lemon, "
                "buff_apple, buff_blueberry, buff_blueberry_expires, buff_watermelon, buff_mango, buff_mango_expires, "
                "buff_kiwi, buff_coconut, buff_lime, buff_lemon) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (u["id"], u["skin"], u["balance"], u["wool"], u["harvest"], u["shearing"],
                 u["s_finish"], u["last_active"],
                 u["inv_apple"], u["inv_blueberry"], u["inv_watermelon"], u["inv_mango"],
                 u["inv_kiwi"], u["inv_coconut"], u["inv_lime"], u["inv_lemon"],
                 u["buff_apple"], u["buff_blueberry"], u["buff_blueberry_expires"],
                 u["buff_watermelon"], u["buff_mango"], u["buff_mango_expires"],
                 u["buff_kiwi"], u["buff_coconut"], u["buff_lime"], u["buff_lemon"])
            )
            await db.commit()
            return u
        u = dict(row)
        passed_time = now - u["last_active"]
        hours = min(passed_time / 3600, 6)
        income_per_hour = 0
        skin = u.get("skin", "")
        if any(s in skin for s in ["Шизанутая", "Милая", "Карамельная"]):
            income_per_hour = 1
        elif any(s in skin for s in ["Магмовая", "Бриллиантовая", "Жемчужная"]):
            income_per_hour = 3
        elif any(s in skin for s in ["Священная", "Призрачная", "Ритуальная"]):
            income_per_hour = 5
        if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_expires", 0):
            income_per_hour *= 2
        if u.get("buff_mango", 0) and now < u.get("buff_mango_expires", 0):
            income_per_hour *= 2
        if u.get("buff_kiwi", 0):
            income_per_hour *= 2
        if u.get("buff_lime", 0):
            income_per_hour *= 2
        if u.get("buff_lemon", 0):
            income_per_hour *= 2
        if hours > 0 and income_per_hour > 0:
            total_income = int(hours * income_per_hour)
            if total_income > 0:
                u["balance"] += total_income
        u["last_active"] = now
        await _save(db, u)
        return u

async def save_u(u: dict):
    async with aiosqlite.connect(DB_PATH) as db:
        await _save(db, u)

async def _save(db, u: dict):
    await db.execute(
        "INSERT INTO players (id, skin, balance, wool, harvest, shearing, s_finish, last_active, "
        "inv_apple, inv_blueberry, inv_watermelon, inv_mango, inv_kiwi, inv_coconut, inv_lime, inv_lemon, "
        "buff_apple, buff_blueberry, buff_blueberry_expires, buff_watermelon, buff_mango, buff_mango_expires, "
        "buff_kiwi, buff_coconut, buff_lime, buff_lemon) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "skin=excluded.skin, balance=excluded.balance, wool=excluded.wool, "
        "harvest=excluded.harvest, shearing=excluded.shearing, "
        "s_finish=excluded.s_finish, last_active=excluded.last_active, "
        "inv_apple=excluded.inv_apple, inv_blueberry=excluded.inv_blueberry, "
        "inv_watermelon=excluded.inv_watermelon, inv_mango=excluded.inv_mango, "
        "inv_kiwi=excluded.inv_kiwi, inv_coconut=excluded.inv_coconut, "
        "inv_lime=excluded.inv_lime, inv_lemon=excluded.inv_lemon, "
        "buff_apple=excluded.buff_apple, buff_blueberry=excluded.buff_blueberry, "
        "buff_blueberry_expires=excluded.buff_blueberry_expires, buff_watermelon=excluded.buff_watermelon, "
        "buff_mango=excluded.buff_mango, buff_mango_expires=excluded.buff_mango_expires, "
        "buff_kiwi=excluded.buff_kiwi, buff_coconut=excluded.buff_coconut, "
        "buff_lime=excluded.buff_lime, buff_lemon=excluded.buff_lemon",
        (u["id"], u["skin"], u["balance"], u["wool"], u["harvest"], u["shearing"],
         u["s_finish"], u["last_active"],
         u.get("inv_apple", 0), u.get("inv_blueberry", 0), u.get("inv_watermelon", 0), u.get("inv_mango", 0),
         u.get("inv_kiwi", 0), u.get("inv_coconut", 0), u.get("inv_lime", 0), u.get("inv_lemon", 0),
         u.get("buff_apple", 0), u.get("buff_blueberry", 0), u.get("buff_blueberry_expires", 0),
         u.get("buff_watermelon", 0), u.get("buff_mango", 0), u.get("buff_mango_expires", 0),
         u.get("buff_kiwi", 0), u.get("buff_coconut", 0), u.get("buff_lime", 0), u.get("buff_lemon", 0))
    )
    await db.commit()

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
        return "🍏 Яблоко (иммунитет от волков 6ч)"
    if u.get("buff_kiwi", 0):
        return "🥝 Киви (удвоение шерсти + пассивка x2 12ч)"
    if u.get("buff_coconut", 0):
        return "🥥 Кокос (иммунитет 24ч + скидка 15% 12ч)"
    if u.get("buff_lime", 0):
        return "🍋‍🟩 Лайм (пассивка x2 12ч + удвоение шерсти + скидка 10% 6ч)"
    if u.get("buff_lemon", 0):
        return "🍋 Лимон (иммунитет 48ч + пассивка x2 12ч + скидка 10% 12ч)"
    if u.get("buff_blueberry", 0) and now < u.get("buff_blueberry_expires", 0):
        return "🫐 Черника (скидка 10% в магазине 6ч)"
    if u.get("buff_mango", 0) and now < u.get("buff_mango_expires", 0):
        return "🥭 Манго (иммунитет 12ч + скидка 10% 6ч)"
    return "🚫 Неактивен"

async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    pass

async def sheep_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = await get_u(update.effective_user.id)
    now = time.time()
    if now >= u['harvest']:
        t = "✅ Шерсть готова к сбору."
    else:
        t = f"⏳ Шерсть будет готова к сбору через: {time.strftime('%H:%M:%S', time.gmtime(int(u['harvest'] - now)))}"
    await update.message.reply_text(f"{u['skin']}.\n🐾 Копытца: {u['balance']}\n{t}", reply_markup=main_kb())

async def inventory(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    text = (f"🎒 Инвентарь.\n"
            f"🍏 {u.get('inv_apple',0)} | 🍉 {u.get('inv_watermelon',0)} | 🥝 {u.get('inv_kiwi',0)} | 🍋‍🟩 {u.get('inv_lime',0)}\n"
            f"🫐 {u.get('inv_blueberry',0)} | 🥭 {u.get('inv_mango',0)} | 🥥 {u.get('inv_coconut',0)} | 🍋 {u.get('inv_lemon',0)}")
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
    if fruit_key == "apple":
        u[buff_field] = 1
    elif fruit_key == "blueberry":
        u[buff_field] = 1
        u["buff_blueberry_expires"] = now + 6 * 3600
    elif fruit_key == "watermelon":
        u[buff_field] = 1
    elif fruit_key == "mango":
        u[buff_field] = 1
        u["buff_mango_expires"] = now + 12 * 3600
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

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚", callback_data="eggs"),
         InlineKeyboardButton("💰", callback_data="sell"),
         InlineKeyboardButton("🍬", callback_data="treats")]
    ])
    await update.message.reply_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def eggs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Купить яйцо", callback_data="open_egg")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text("🥚 Покупка яиц.\n💸 Курс: 1 🥚 = 200 🐾", reply_markup=kb)

async def open_egg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u['balance'] < 200:
        await query.answer("❌ Недостаточно копытц!", show_alert=True)
        return
    u['balance'] -= 200
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

async def treats_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🍬 Купить угощение", callback_data="buy_treat")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text("🍬 Покупка угощений.\n💸 Курс: 1 🍬 = 100 🐾", reply_markup=kb)

async def buy_treat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u['balance'] < 100:
        await query.answer("❌ Недостаточно копытц!", show_alert=True)
        return
    u['balance'] -= 100
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
    await query.answer(f"🍬 Ты купил угощение!\n✨ Получено: {treat}", show_alert=True)
    await treats_menu(update, context)

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
         InlineKeyboardButton("🍬", callback_data="treats")]
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

# Команда /give только для владельца (можно дарить и себе)
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
    # Теперь можно дарить и себе
    u = await get_u(target_id)
    u['balance'] += amount
    await save_u(u)
    await update.message.reply_text(f"✅ Передано {amount} 🐾 игроку с ID {target_id}.")

def main():
    asyncio.get_event_loop().run_until_complete(init_db())
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
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
    application.add_handler(CallbackQueryHandler(eggs_menu, pattern="^eggs$"))
    application.add_handler(CallbackQueryHandler(open_egg, pattern="^open_egg$"))
    application.add_handler(CallbackQueryHandler(sell_menu, pattern="^sell$"))
    application.add_handler(CallbackQueryHandler(sell_confirm, pattern="^sell_confirm$"))
    application.add_handler(CallbackQueryHandler(treats_menu, pattern="^treats$"))
    application.add_handler(CallbackQueryHandler(buy_treat, pattern="^buy_treat$"))
    application.add_handler(CallbackQueryHandler(market_main, pattern="^market_main$"))
    application.add_handler(CallbackQueryHandler(back, pattern="^back$"))
    application.add_handler(CallbackQueryHandler(shear, pattern="^shear$"))
    port = int(os.environ.get("PORT", 8000))
    threading.Thread(target=lambda: app.run(host='0.0.0.0', port=port), daemon=True).start()
    application.run_polling()

if __name__ == "__main__":
    main()
