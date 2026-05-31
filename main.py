import os
import sqlite3
import random
from datetime import datetime, timedelta
from threading import Lock
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

# --- База данных ---
DB_PATH = "mining.db"
db_lock = Lock()

def init_db():
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users
                     (user_id INTEGER PRIMARY KEY,
                      reset_time TEXT,
                      stones INTEGER DEFAULT 0,
                      iron INTEGER DEFAULT 0,
                      diamonds INTEGER DEFAULT 0)''')
        conn.commit()
        conn.close()

init_db()

def get_user(user_id):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT reset_time, stones, iron, diamonds FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        conn.close()
        if row:
            return {"reset_time": datetime.fromisoformat(row[0]) if row[0] else None,
                    "stones": row[1], "iron": row[2], "diamonds": row[3]}
        return None

def set_user(user_id, reset_time=None, stones=None, iron=None, diamonds=None):
    with db_lock:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        existing = get_user(user_id)
        if existing:
            new_reset = reset_time.isoformat() if reset_time else existing["reset_time"].isoformat() if existing["reset_time"] else None
            new_stones = stones if stones is not None else existing["stones"]
            new_iron = iron if iron is not None else existing["iron"]
            new_diamonds = diamonds if diamonds is not None else existing["diamonds"]
            c.execute("UPDATE users SET reset_time = ?, stones = ?, iron = ?, diamonds = ? WHERE user_id = ?",
                      (new_reset, new_stones, new_iron, new_diamonds, user_id))
        else:
            c.execute("INSERT INTO users (user_id, reset_time, stones, iron, diamonds) VALUES (?, ?, ?, ?, ?)",
                      (user_id, reset_time.isoformat() if reset_time else None, stones or 0, iron or 0, diamonds or 0))
        conn.commit()
        conn.close()

def get_profile_text(user_id):
    user = get_user(user_id)
    if not user:
        return "❌ Ошибка профиля"
    reset_time = user["reset_time"]
    if reset_time and datetime.now() >= reset_time:
        return (f"🪨 Каменная кирка.\n"
                f"✅ Руда готова к сбору.\n"
                f"📦 Ресурсы: 🪨 {user['stones']} | 🔩 {user['iron']} | 💎 {user['diamonds']}")
    elif reset_time:
        left = reset_time - datetime.now()
        hours, rem = divmod(left.seconds, 3600)
        mins, secs = divmod(rem, 60)
        timer_str = f"{hours:02}:{mins:02}:{secs:02}"
        return (f"🪨 Каменная кирка.\n"
                f"⏳ Руда будет готова к сбору через: {timer_str}\n"
                f"📦 Ресурсы: 🪨 {user['stones']} | 🔩 {user['iron']} | 💎 {user['diamonds']}")
    else:
        return (f"🪨 Каменная кирка.\n"
                f"✅ Руда готова к сбору.\n"
                f"📦 Ресурсы: 🪨 {user['stones']} | 🔩 {user['iron']} | 💎 {user['diamonds']}")

def get_profile_keyboard():
    # Кнопка Копать всегда показывается
    keyboard = [
        [InlineKeyboardButton("⛏️ Копать", callback_data="dig_start")],
        [InlineKeyboardButton("🛠️ Верстак", callback_data="workbench")],
        [InlineKeyboardButton("🏆 Престиж", callback_data="prestige")]
    ]
    return InlineKeyboardMarkup(keyboard)

# --- Хэндлеры ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        set_user(user_id)
    await show_profile(update, context)

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE, query=None):
    user_id = update.effective_user.id
    text = get_profile_text(user_id)
    reply_markup = get_profile_keyboard()
    if query:
        await query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data

    if data == "dig_start":
        user = get_user(user_id)
        # Проверяем, можно ли копать
        if user["reset_time"] and datetime.now() < user["reset_time"]:
            # Нельзя — показываем окно с кнопкой Ок
            await query.answer("❌ Ещё не готова!", show_alert=True)
            return
        
        # Можно копать — запускаем процесс на 5 минут
        context.user_data["mining_end"] = datetime.now() + timedelta(minutes=5)
        context.user_data["mining_user_id"] = user_id
        await query.edit_message_text(
            "⛏️ Выкапываем руду.\n⏳ Процесс займет: 5:00",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⏱️ Обновить время", callback_data="mining_refresh")],
                [InlineKeyboardButton("⬅️ Назад", callback_data="mining_back")]
            ])
        )
        # Запускаем фоновую задачу для завершения копки
        asyncio.create_task(mining_waiter(context, user_id, query.message.chat_id))

    elif data == "mining_refresh":
        end = context.user_data.get("mining_end")
        if not end:
            await query.edit_message_text("❌ Процесс копки не найден", reply_markup=None)
            return
        remaining = (end - datetime.now()).total_seconds()
        if remaining <= 0:
            await finish_mining(query, context, user_id)
        else:
            mins = int(remaining // 60)
            secs = int(remaining % 60)
            await query.edit_message_text(
                f"⛏️ Выкапываем руду.\n⏳ Процесс займет: {mins:02}:{secs:02}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("⏱️ Обновить время", callback_data="mining_refresh")],
                    [InlineKeyboardButton("⬅️ Назад", callback_data="mining_back")]
                ])
            )

    elif data == "mining_back":
        await show_profile(update, context, query)

    elif data == "workbench":
        await query.answer("🛠️ Верстак пока не сделан.", show_alert=True)
    elif data == "prestige":
        await query.answer("🏆 Престиж пока не сделан.", show_alert=True)

async def mining_waiter(context: ContextTypes.DEFAULT_TYPE, user_id, chat_id):
    end = context.user_data.get("mining_end")
    if not end:
        return
    now = datetime.now()
    if now >= end:
        # Уже пора завершать
        return
    await asyncio.sleep((end - now).total_seconds())
    # Отправляем уведомление пользователю
    try:
        await context.bot.send_message(chat_id, "✅ Руда успешно собрана! Зайдите в профиль и нажмите «Копать», чтобы получить ресурсы.")
    except Exception as e:
        print(f"Ошибка уведомления: {e}")

async def finish_mining(query, context: ContextTypes.DEFAULT_TYPE, user_id):
    # Определяем ресурсы
    r = random.random()
    if r < 0.6:
        amount = random.randint(10, 15)
        resource = "stones"
        emoji = "🪨"
    elif r < 0.9:
        amount = random.randint(5, 10)
        resource = "iron"
        emoji = "🔩"
    else:
        amount = random.randint(3, 5)
        resource = "diamonds"
        emoji = "💎"

    user = get_user(user_id)
    new_amount = user[resource] + amount
    if resource == "stones":
        set_user(user_id, stones=new_amount)
    elif resource == "iron":
        set_user(user_id, iron=new_amount)
    else:
        set_user(user_id, diamonds=new_amount)

    # Устанавливаем 12-часовой таймер до следующей копки
    new_reset = datetime.now() + timedelta(hours=12)
    set_user(user_id, reset_time=new_reset)

    await query.edit_message_text(
        f"✅ Руда успешно собрана! Получено: {amount} {emoji}\n"
        f"📦 Теперь у вас: 🪨 {get_user(user_id)['stones']} | 🔩 {get_user(user_id)['iron']} | 💎 {get_user(user_id)['diamonds']}",
        reply_markup=None
    )
    context.user_data.pop("mining_end", None)

# --- Запуск ---
import asyncio

def main():
    if not TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден!")
        return
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    print("🤖 Бот запущен и ждёт команды /start")
    app.run_polling()

if __name__ == "__main__":
    main()
