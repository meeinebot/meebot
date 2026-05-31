import os
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# Токен берётся из переменной окружения BOT_TOKEN на Render
TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает!")

if __name__ == "__main__":
    if not TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден в переменных окружения!")
    else:
        app = ApplicationBuilder().token(TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        print("🤖 Бот запущен и ждёт команды /start")
        app.run_polling()
