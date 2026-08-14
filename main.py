import asyncio
import os
from datetime import datetime
from threading import Thread
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== ТВОЙ ТОКЕН =====
BOT_TOKEN = "8887613640:AAEm7r9e0bZyCR0KjCQegWqESYpGayTSC7Q"
# ======================

flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is running!"

def run_flask():
    port = int(os.getenv('PORT', 10000))
    flask_app.run(host='0.0.0.0', port=port)

# Хранилище данных игроков
players = {}

class Player:
    def __init__(self, user_id):
        self.user_id = user_id
        self.nickname = "Разведчик"
        self.gems = 0
        self.in_round = False
        self.day = 1
        self.night = 0
        self.hunger = 10
        self.fire = 100
        self.wood = 0
        self.meat = 0
        self.metal = 0
        self.is_gathering = False
        self.gather_start = None
        self.gather_type = None
        self.is_dead = False
        self.death_start = None
        self.game_start = datetime.now()
        self.last_update = datetime.now()
        self.gather_duration = 180
    
    def reset_for_new_round(self):
        self.hunger = 10
        self.fire = 100
        self.wood = 0
        self.meat = 0
        self.metal = 0
        self.is_gathering = False
        self.gather_start = None
        self.gather_type = None
        self.is_dead = False
        self.death_start = None
        self.game_start = datetime.now()
        self.day = 1
        self.night = 0
        self.in_round = True
    
    def get_time_of_day(self):
        elapsed = (datetime.now() - self.game_start).total_seconds()
        cycle_time = elapsed % 270
        if cycle_time < 180:
            return "day", cycle_time
        else:
            return "night", cycle_time - 180
    
    def get_day_night_text(self):
        time_type, elapsed = self.get_time_of_day()
        if time_type == "day":
            return f"🌞 День {self.day}"
        else:
            return f"🌙 Ночь {self.night}"
    
    def check_timers(self):
        now = datetime.now()
        if self.last_update:
            seconds_passed = (now - self.last_update).total_seconds()
            if seconds_passed >= 60:
                minutes_passed = int(seconds_passed // 60)
                self.fire = max(0, self.fire - (minutes_passed * 10))
                self.hunger = max(0, self.hunger - minutes_passed)
                self.last_update = now
                
                if self.hunger == 0 or self.fire == 0:
                    self.is_dead = True
                    self.death_start = now
                    return True
        return False
    
    def get_profile_text(self):
        self.check_timers()
        
        if self.is_dead:
            if self.death_start:
                elapsed = (datetime.now() - self.death_start).total_seconds()
                remaining = max(0, 30 - elapsed)
                if remaining > 0:
                    return f"💀 Ты погиб! \n⏳ Осталось: {int(remaining)} сек", None
                else:
                    self.is_dead = False
                    self.death_start = None
                    self.in_round = False
                    return self.get_main_menu()
        
        if self.is_gathering and self.gather_start:
            elapsed = (datetime.now() - self.gather_start).total_seconds()
            if elapsed >= self.gather_duration:
                self.is_gathering = False
                if self.gather_type == "resources":
                    self.metal += 3
                    self.meat += 3
                    loot_text = "🌳 Поиск окончен! 🔩 +3 металла, 🍗 +3 мяса"
                elif self.gather_type == "wood":
                    self.wood += 5
                    loot_text = "🌳 Рубка окончена! 🪵 +5 брёвен"
                self.gather_type = None
                self.gather_start = None
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🍃 Перейти в раунд", callback_data="back_to_round")]
                ])
                return loot_text, keyboard
            else:
                remaining = self.gather_duration - elapsed
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                if self.gather_type == "resources":
                    return f"🌳 Гуляем и добываем ресурсы.\n⏳ Вернёмся через: {minutes} мин. {seconds} сек", None
                else:
                    return f"🪵 Рубим деревья.\n⏳ Вернёмся через: {minutes} мин. {seconds} сек", None
        
        if self.in_round:
            text = f"{self.get_day_night_text()}\n🌿 Сытость: {self.hunger}\n🔥 Огонь: {self.fire}%"
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("🌳 Отправиться в лес", callback_data="go_to_forest")],
                [InlineKeyboardButton("🍗 Съесть", callback_data="eat"), 
                 InlineKeyboardButton("🪵 Огонь", callback_data="fire")]
            ])
            return text, keyboard
        
        text = f"👤 {self.nickname} | {self.gems}\n💎 Самоцветы: {self.gems}\n⏳ Находится в раунде"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Создать раунд", callback_data="create_round")],
            [InlineKeyboardButton("💰 Покупка класса", callback_data="buy_class")]
        ])
        return text, keyboard
    
    def get_main_menu(self):
        text = f"{self.get_day_night_text()}\n🌿 Сытость: {self.hunger}\n🔥 Огонь: {self.fire}%"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🌳 Отправиться в лес", callback_data="go_to_forest")],
            [InlineKeyboardButton("🍗 Съесть", callback_data="eat"), 
             InlineKeyboardButton("🪵 Огонь", callback_data="fire")]
        ])
        return text, keyboard

# Обработчики команд
async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in players:
        players[user_id] = Player(user_id)
    
    player = players[user_id]
    text, keyboard = player.get_profile_text()
    if keyboard:
        await update.message.reply_text(text, reply_markup=keyboard)
    else:
        await update.message.reply_text(text)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = query.from_user.id
    if user_id not in players:
        players[user_id] = Player(user_id)
    
    player = players[user_id]
    data = query.data
    
    if data == "create_round":
        player.reset_for_new_round()
        text = "🌳 Собрать отряд\nВыбери количество игроков:"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1️⃣ Один", callback_data="players_1"),
                InlineKeyboardButton("2️⃣ Два", callback_data="players_2")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_profile"),
                InlineKeyboardButton("➡️ Далее", callback_data="next_players_2")
            ]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "players_1":
        player.in_round = True
        text, keyboard = player.get_main_menu()
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data in ["players_2", "players_3", "players_4", "players_5"]:
        await query.answer("⏳ Функция в разработке!", show_alert=True)
    
    elif data == "next_players_2":
        text = "🌳 Собрать отряд\nВыбери количество игроков:"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("3️⃣ Три", callback_data="players_3"),
                InlineKeyboardButton("4️⃣ Четыре", callback_data="players_4")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="back_players_1"),
                InlineKeyboardButton("➡️ Далее", callback_data="next_players_3")
            ]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "next_players_3":
        text = "🌳 Собрать отряд\nВыбери количество игроков:"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("5️⃣ Пять", callback_data="players_5")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="back_players_2")
            ]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "back_players_1":
        text = "🌳 Собрать отряд\nВыбери количество игроков:"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("1️⃣ Один", callback_data="players_1"),
                InlineKeyboardButton("2️⃣ Два", callback_data="players_2")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="back_to_profile"),
                InlineKeyboardButton("➡️ Далее", callback_data="next_players_2")
            ]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "back_players_2":
        text = "🌳 Собрать отряд\nВыбери количество игроков:"
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("3️⃣ Три", callback_data="players_3"),
                InlineKeyboardButton("4️⃣ Четыре", callback_data="players_4")
            ],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="back_players_1"),
                InlineKeyboardButton("➡️ Далее", callback_data="next_players_3")
            ]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "back_to_profile":
        player.in_round = False
        text = "👤 Разведчик | 0\n💎 Самоцветы: 0\n⏳ Находится в раунде"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🎲 Создать раунд", callback_data="create_round")],
            [InlineKeyboardButton("💰 Покупка класса", callback_data="buy_class")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "go_to_forest":
        text = "🌳 Чем займёмся в лесу?\nВыбери действие:"
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🍃 За ресурсами", callback_data="gather_resources")],
            [InlineKeyboardButton("🪵 Рубка дерева", callback_data="chop_wood")],
            [InlineKeyboardButton("⬅️ Назад", callback_data="back_to_round")]
        ])
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "gather_resources":
        player.is_gathering = True
        player.gather_start = datetime.now()
        player.gather_type = "resources"
        text = "🌳 Гуляем и добываем ресурсы.\n⏳ Вернёмся через: 2 мин. 59 сек"
        await query.edit_message_text(text)
    
    elif data == "chop_wood":
        player.is_gathering = True
        player.gather_start = datetime.now()
        player.gather_type = "wood"
        text = "🪵 Рубим деревья.\n⏳ Вернёмся через: 2 мин. 59 сек"
        await query.edit_message_text(text)
    
    elif data == "back_to_round":
        player.in_round = True
        text, keyboard = player.get_main_menu()
        await query.edit_message_text(text, reply_markup=keyboard)
    
    elif data == "eat":
        if player.hunger >= 10:
            await query.answer("🌿 Сытость максимальная! Текущий уровень: 10", show_alert=True)
        elif player.meat <= 0:
            await query.answer("🍗 Недостаточно еды!", show_alert=True)
        else:
            player.meat -= 1
            player.hunger = min(10, player.hunger + 2)
            await query.answer("🍗 Съедена 1 порция!", show_alert=True)
    
    elif data == "fire":
        if player.fire >= 100:
            await query.answer(f"🪵 Огонь максимальный! 🔥 Текущий уровень: 100%", show_alert=True)
        elif player.wood <= 0:
            await query.answer(f"🪵 У тебя нет дров! 🔥 Текущий уровень: {player.fire}%", show_alert=True)
        else:
            player.wood -= 1
            player.fire = min(100, player.fire + 10)
            await query.answer(f"🪵 Огонь поддержан! 🔥 Текущий уровень: {player.fire}%", show_alert=True)
    
    elif data == "buy_class":
        await query.answer("💰 Покупка классов в разработке!", show_alert=True)

def main():
    print("Бот запущен!")
    
    # Создаем приложение
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Добавляем обработчики
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    # Запускаем бота
    application.run_polling()

if __name__ == "__main__":
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    main()
