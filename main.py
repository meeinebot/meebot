import os
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

TOKEN = os.environ.get("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Бот работает!")

def main():
    if not TOKEN:
        print("❌ ОШИБКА: BOT_TOKEN не найден!")
        return

    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))

    print("🤖 Бот запущен и ждёт команды /start")
    app.run_polling()

if __name__ == "__main__":
    main()
