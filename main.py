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

RARITIES = {
    "🔵 Редкая": {"items": ["🏡 Деревенская овечка", "🏖️ Пляжная овечка", "💤 Сонная овечка"], "w": 40},
    "🟣 Эпическая": {"items": ["💥 Шизанутая овечка", "🎀 Милая овечка", "🍭 Карамельная овечка"], "w": 30},
    "🟡 Легендарная": {"items": ["🔥 Магмовая овечка", "💎 Бриллиантовая овечка", "🐚 Жемчужная овечка"], "w": 20},
    "🔴 Мифическая": {"items": ["👼 Священная овечка", "👻 Призрачная овечка", "🕯️ Ритуальная овечка"], "w": 10}
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
                inv_cabbage INTEGER DEFAULT 0,
                inv_blueberry INTEGER DEFAULT 0,
                inv_watermelon INTEGER DEFAULT 0,
                inv_mango INTEGER DEFAULT 0,
                buff_cabbage INTEGER DEFAULT 0,
                buff_blueberry INTEGER DEFAULT 0,
                buff_blueberry_expires REAL DEFAULT 0,
                buff_watermelon INTEGER DEFAULT 0,
                buff_mango INTEGER DEFAULT 0,
                buff_mango_expires REAL DEFAULT 0
            )
        """)
        cols = ["inv_cabbage", "inv_blueberry", "inv_watermelon", "inv_mango",
                "buff_cabbage", "buff_blueberry", "buff_blueberry_expires",
                "buff_watermelon", "buff_mango", "buff_mango_expires"]
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
                "inv_cabbage": 0,
                "inv_blueberry": 0,
                "inv_watermelon": 0,
                "inv_mango": 0,
                "buff_cabbage": 0,
                "buff_blueberry": 0,
                "buff_blueberry_expires": 0,
                "buff_watermelon": 0,
                "buff_mango": 0,
                "buff_mango_expires": 0
            }
            await db.execute(
                "INSERT INTO players (id, skin, balance, wool, harvest, shearing, s_finish, last_active, "
                "inv_cabbage, inv_blueberry, inv_watermelon, inv_mango, "
                "buff_cabbage, buff_blueberry, buff_blueberry_expires, buff_watermelon, buff_mango, buff_mango_expires) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (u["id"], u["skin"], u["balance"], u["wool"], u["harvest"], u["shearing"],
                 u["s_finish"], u["last_active"],
                 u["inv_cabbage"], u["inv_blueberry"], u["inv_watermelon"], u["inv_mango"],
                 u["buff_cabbage"], u["buff_blueberry"], u["buff_blueberry_expires"],
                 u["buff_watermelon"], u["buff_mango"], u["buff_mango_expires"])
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
        "inv_cabbage, inv_blueberry, inv_watermelon, inv_mango, "
        "buff_cabbage, buff_blueberry, buff_blueberry_expires, buff_watermelon, buff_mango, buff_mango_expires) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(id) DO UPDATE SET "
        "skin=excluded.skin, balance=excluded.balance, wool=excluded.wool, "
        "harvest=excluded.harvest, shearing=excluded.shearing, "
        "s_finish=excluded.s_finish, last_active=excluded.last_active, "
        "inv_cabbage=excluded.inv_cabbage, inv_blueberry=excluded.inv_blueberry, "
        "inv_watermelon=excluded.inv_watermelon, inv_mango=excluded.inv_mango, "
        "buff_cabbage=excluded.buff_cabbage, buff_blueberry=excluded.buff_blueberry, "
        "buff_blueberry_expires=excluded.buff_blueberry_expires, buff_watermelon=excluded.buff_watermelon, "
        "buff_mango=excluded.buff_mango, buff_mango_expires=excluded.buff_mango_expires",
        (u["id"], u["skin"], u["balance"], u["wool"], u["harvest"], u["shearing"],
         u["s_finish"], u["last_active"],
         u.get("inv_cabbage", 0), u.get("inv_blueberry", 0), u.get("inv_watermelon", 0), u.get("inv_mango", 0),
         u.get("buff_cabbage", 0), u.get("buff_blueberry", 0), u.get("buff_blueberry_expires", 0),
         u.get("buff_watermelon", 0), u.get("buff_mango", 0), u.get("buff_mango_expires", 0))
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
    text = (f"🎒 Инвентарь.\n🥬 {u.get('inv_cabbage',0)}   🫐 {u.get('inv_blueberry',0)}\n"
            f"🍉 {u.get('inv_watermelon',0)}   🥭 {u.get('inv_mango',0)}")
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥬", callback_data="use_cabbage"),
         InlineKeyboardButton("🫐", callback_data="use_blueberry"),
         InlineKeyboardButton("🍉", callback_data="use_watermelon"),
         InlineKeyboardButton("🥭", callback_data="use_mango")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])
    await query.edit_message_text(text, reply_markup=kb)

async def use_treat(update: Update, context: ContextTypes.DEFAULT_TYPE, treat_key: str, inv_field: str):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u.get(inv_field, 0) <= 0:
        await query.answer("❌ У тебя нет этого угощения!", show_alert=True)
        return
    u[inv_field] -= 1
    now = time.time()
    if treat_key == "cabbage":
        u["buff_cabbage"] = 1
        msg = "🥬 Ты съел капусту! ✨ Эффект активирован."
    elif treat_key == "blueberry":
        u["buff_blueberry"] = 1
        u["buff_blueberry_expires"] = now + 6 * 3600
        msg = "🫐 Ты съел чернику! ✨ Эффект активирован."
    elif treat_key == "watermelon":
        u["buff_watermelon"] = 1
        msg = "🍉 Ты съел арбуз! ✨ Эффект активирован."
    elif treat_key == "mango":
        u["buff_watermelon"] = 1
        u["buff_mango"] = 1
        u["buff_mango_expires"] = now + 12 * 3600
        msg = "🥭 Ты съел манго! ✨ Эффект активирован."
    else:
        return
    await save_u(u)
    await query.answer(msg, show_alert=True)
    await inventory(update, context)

async def use_cabbage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_treat(update, context, "cabbage", "inv_cabbage")

async def use_blueberry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_treat(update, context, "blueberry", "inv_blueberry")

async def use_watermelon(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_treat(update, context, "watermelon", "inv_watermelon")

async def use_mango(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await use_treat(update, context, "mango", "inv_mango")

async def market_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Яйца", callback_data="eggs"),
         InlineKeyboardButton("💰 Продать шерсть", callback_data="sell"),
         InlineKeyboardButton("🍬 Угощения", callback_data="treats")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
    ])
    await update.message.reply_text("🐑 Овечий рынок.\n➡️ Выбери раздел:", reply_markup=kb)

async def eggs_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🥚 Купить яйцо (200🐾)", callback_data="open_egg")],
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
        [InlineKeyboardButton("💰 Продать всю шерсть", callback_data="sell_confirm")],
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
        [InlineKeyboardButton("🍬 Купить угощение (100🐾)", callback_data="buy_treat")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="market_main")]
    ])
    await query.edit_message_text("🍬 Покупка угощений.\n💸 Курс: 1 🍬 = 100 🐾", reply_markup=kb)

TREATS = ["🥬 Капуста", "🫐 Черника", "🍉 Арбуз", "🥭 Манго"]
TREAT_WEIGHTS = [40, 30, 20, 10]

async def buy_treat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    if u['balance'] < 100:
        await query.answer("❌ Недостаточно копытц!", show_alert=True)
        return
    u['balance'] -= 100
    treat = random.choices(TREATS, weights=TREAT_WEIGHTS)[0]
    if treat == "🥬 Капуста":
        u['inv_cabbage'] = u.get('inv_cabbage', 0) + 1
    elif treat == "🫐 Черника":
        u['inv_blueberry'] = u.get('inv_blueberry', 0) + 1
    elif treat == "🍉 Арбуз":
        u['inv_watermelon'] = u.get('inv_watermelon', 0) + 1
    elif treat == "🥭 Манго":
        u['inv_mango'] = u.get('inv_mango', 0) + 1
    await save_u(u)
    await query.answer(f"🍬 Ты купил угощение!\n✨ Получено: {treat}", show_alert=True)
    await treats_menu(update, context)

async def shear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    u = await get_u(query.from_user.id)
    now = time.time()
    if u['shearing']:
        if now >= u['s_finish']:
            if u.get('buff_cabbage', 0):
                gain = random.randint(15, 25)
                u['buff_cabbage'] = 0
            else:
                gain = random.randint(5, 15)
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
        [InlineKeyboardButton("🥚 Яйца", callback_data="eggs"),
         InlineKeyboardButton("💰 Продать шерсть", callback_data="sell"),
         InlineKeyboardButton("🍬 Угощения", callback_data="treats")],
        [InlineKeyboardButton("⬅️ Назад", callback_data="back")]
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

def main():
    asyncio.get_event_loop().run_until_complete(init_db())
    application = Application.builder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start_cmd))
    application.add_handler(CommandHandler("sheep", sheep_cmd))
    application.add_handler(CommandHandler("market", market_cmd))
    application.add_handler(CallbackQueryHandler(inventory, pattern="^inventory$"))
    application.add_handler(CallbackQueryHandler(use_cabbage, pattern="^use_cabbage$"))
    application.add_handler(CallbackQueryHandler(use_blueberry, pattern="^use_blueberry$"))
    application.add_handler(CallbackQueryHandler(use_watermelon, pattern="^use_watermelon$"))
    application.add_handler(CallbackQueryHandler(use_mango, pattern="^use_mango$"))
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
