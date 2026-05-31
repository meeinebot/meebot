import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

def get_reset_time():
    now = datetime.now()
    reset = now.replace(hour=12, minute=0, second=0, microsecond=0)
    if now >= reset:
        reset += timedelta(days=1)
    return reset

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reset_time = get_reset_time()
    time_left = reset_time - datetime.now()
    hours, remainder = divmod(time_left.seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    timer_text = f"{hours:02}:{minutes:02}:{seconds:02}"

    keyboard = [
        [InlineKeyboardButton("⛏️ Копать", callback_data="dig")],
        [InlineKeyboardButton("🛠️ Верстак", callback_data="workbench")],
        [InlineKeyboardButton("🏆 Престиж", callback_data="prestige")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        f"🪨 Каменная кирка.\n"
        f"⏳ Руда будет готова к сбору через: {timer_text}",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(f"⏳ Функция '{query.data}' ещё в разработке!")

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
