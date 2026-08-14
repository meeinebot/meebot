import asyncio
import time
import random
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import F
import os

# Токен бота из переменных окружения Render
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Инициализация бота и диспетчера
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Хранилище данных игроков (в реальном проекте - БД)
players = {}

# Класс игрока
class Player:
    def __init__(self, user_id):
        self.user_id = user_id
        self.nickname = "Разведчик"
        self.gems = 0
        self.in_round = False
        self.day = 1
        self.night = 0
        self.is_night = False
        self.hunger = 10  # Сытость (макс 10)
        self.fire = 100   # Огонь (%)
        self.wood = 0     # Брёвна
        self.meat = 0     # Мясо
        self.metal = 0    # Металл
        self.is_gathering = False
        self.gather_start = None
        self.gather_type = None  # "resources" или "wood"
        self.is_dead = False
        self.death_start = None
        self.game_start = datetime.now()
        self.last_update = datetime.now()
        self.gather_duration = 180  # 3 минуты (было 5)
    
    def reset_for_new_round(self):
        """Сброс ресурсов для нового раунда"""
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
        self.is_night = False
        self.in_round = True
    
    def get_time_of_day(self):
        elapsed = (datetime.now() - self.game_start).total_seconds()
        cycle_time = elapsed % 270  # 3 мин день + 1.5 мин ночь = 270 сек
        if cycle_time < 180:  # 3 минуты день
            return "day", cycle_time
        else:  # ночь
            return "night", cycle_time - 180
    
    def get_day_night_text(self):
        time_type, elapsed = self.get_time_of_day()
        if time_type == "day":
            return f"🌞 День {self.day}"
        else:
            return f"🌙 Ночь {self.night}"
    
    def check_timers(self):
        """Проверка таймеров (огонь, сытость, смерть)"""
        now = datetime.now()
        if self.last_update:
            seconds_passed = (now - self.last_update).total_seconds()
            if seconds_passed >= 60:
                minutes_passed = int(seconds_passed // 60)
                # Уменьшаем огонь
                self.fire = max(0, self.fire - (minutes_passed * 10))
                # Уменьшаем сытость
                self.hunger = max(0, self.hunger - minutes_passed)
                self.last_update = now
                
                # Проверка на смерть
                if self.hunger == 0 or self.fire == 0:
                    self.is_dead = True
                    self.death_start = now
                    return True
        return False
    
    def get_profile_text(self):
        # Проверяем таймеры
        self.check_timers()
        
        # Проверка на смерть
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
        
        # Проверка на сбор ресурсов
        if self.is_gathering and self.gather_start:
            elapsed = (datetime.now() - self.gather_start).total_seconds()
            if elapsed >= self.gather_duration:  # 3 минуты прошло
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
                keyboard = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="🍃 Перейти в раунд", callback_data="back_to_round")]
                    ]
                )
                return loot_text, keyboard
            else:
                remaining = self.gather_duration - elapsed
                minutes = int(remaining // 60)
                seconds = int(remaining % 60)
                if self.gather_type == "resources":
                    return f"🌳 Гуляем и добываем ресурсы.\n⏳ Вернёмся через: {minutes} мин. {seconds} сек", None
                else:
                    return f"🪵 Рубим деревья.\n⏳ Вернёмся через: {minutes} мин. {seconds} сек", None
        
        # Если в раунде - показываем игровой экран
        if self.in_round:
            text = f"{self.get_day_night_text()}\n🌿 Сытость: {self.hunger}"
            keyboard = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="🌳 Отправиться в лес", callback_data="go_to_forest")],
                    [InlineKeyboardButton(text="🍗 Съесть", callback_data="eat"), 
                     InlineKeyboardButton(text="🪵 Огонь", callback_data="fire")]
                ]
            )
            return text, keyboard
        
        # Стандартный профиль (не в раунде)
        text = f"👤 {self.nickname} | {self.gems}\n💎 Самоцветы: {self.gems}\n⏳ Находится в раунде"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🎲 Создать раунд", callback_data="create_round")],
                [InlineKeyboardButton(text="💰 Покупка класса", callback_data="buy_class")]
            ]
        )
        return text, keyboard
    
    def get_main_menu(self):
        text = f"{self.get_day_night_text()}\n🌿 Сытость: {self.hunger}"
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text="🌳 Отправиться в лес", callback_data="go_to_forest")],
                [InlineKeyboardButton(text="🍗 Съесть", callback_data="eat"), 
                 InlineKeyboardButton(text="🪵 Огонь", callback_data="fire")]
            ]
        )
        return text, keyboard

# Обработчики команд
@dp.message(Command("profile"))
async def profile_command(message: types.Message):
    user_id = message.from_user.id
    if user_id not in players:
        players[user_id] = Player(user_id)
    
    player = players[user_id]
    text, keyboard = player.get_profile_text()
    if keyboard:
        await message.answer(text, reply_markup=keyboard)
    else:
        await message.answer(text)

# Обработчик "Создать раунд"
@dp.callback_query(F.data == "create_round")
async def create_round_menu(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id not in players:
        players[user_id] = Player(user_id)
    
    player = players[user_id]
    player.reset_for_new_round()  # Сброс ресурсов для нового раунда
    
    text = "🌳 Собрать отряд\nВыбери количество игроков:"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Один", callback_data="players_1"),
                InlineKeyboardButton(text="2️⃣ Два", callback_data="players_2")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile"),
                InlineKeyboardButton(text="➡️ Далее", callback_data="next_players_2")
            ]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Обработчики выбора игроков
@dp.callback_query(F.data == "players_1")
async def players_1(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players[user_id]
    player.in_round = True
    
    text, keyboard = player.get_main_menu()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "players_2")
async def players_2(callback: types.CallbackQuery):
    await callback.answer("⏳ Функция в разработке!", show_alert=True)

@dp.callback_query(F.data == "players_3")
async def players_3(callback: types.CallbackQuery):
    await callback.answer("⏳ Функция в разработке!", show_alert=True)

@dp.callback_query(F.data == "players_4")
async def players_4(callback: types.CallbackQuery):
    await callback.answer("⏳ Функция в разработке!", show_alert=True)

@dp.callback_query(F.data == "players_5")
async def players_5(callback: types.CallbackQuery):
    await callback.answer("⏳ Функция в разработке!", show_alert=True)

# Навигация по страницам выбора игроков
@dp.callback_query(F.data == "next_players_2")
async def next_players_2(callback: types.CallbackQuery):
    text = "🌳 Собрать отряд\nВыбери количество игроков:"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3️⃣ Три", callback_data="players_3"),
                InlineKeyboardButton(text="4️⃣ Четыре", callback_data="players_4")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_players_1"),
                InlineKeyboardButton(text="➡️ Далее", callback_data="next_players_3")
            ]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "next_players_3")
async def next_players_3(callback: types.CallbackQuery):
    text = "🌳 Собрать отряд\nВыбери количество игроков:"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="5️⃣ Пять", callback_data="players_5")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_players_2")
            ]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Кнопки назад
@dp.callback_query(F.data == "back_players_1")
async def back_players_1(callback: types.CallbackQuery):
    text = "🌳 Собрать отряд\nВыбери количество игроков:"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="1️⃣ Один", callback_data="players_1"),
                InlineKeyboardButton(text="2️⃣ Два", callback_data="players_2")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_profile"),
                InlineKeyboardButton(text="➡️ Далее", callback_data="next_players_2")
            ]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "back_players_2")
async def back_players_2(callback: types.CallbackQuery):
    text = "🌳 Собрать отряд\nВыбери количество игроков:"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="3️⃣ Три", callback_data="players_3"),
                InlineKeyboardButton(text="4️⃣ Четыре", callback_data="players_4")
            ],
            [
                InlineKeyboardButton(text="⬅️ Назад", callback_data="back_players_1"),
                InlineKeyboardButton(text="➡️ Далее", callback_data="next_players_3")
            ]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

@dp.callback_query(F.data == "back_to_profile")
async def back_to_profile(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in players:
        player = players[user_id]
        player.in_round = False
    
    profile_text = "👤 Разведчик | 0\n💎 Самоцветы: 0\n⏳ Находится в раунде"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🎲 Создать раунд", callback_data="create_round")],
            [InlineKeyboardButton(text="💰 Покупка класса", callback_data="buy_class")]
        ]
    )
    await callback.message.edit_text(profile_text, reply_markup=keyboard)
    await callback.answer()

# Обработчик "Отправиться в лес"
@dp.callback_query(F.data == "go_to_forest")
async def go_to_forest(callback: types.CallbackQuery):
    text = "🌳 Чем займёмся в лесу?\nВыбери действие:"
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🍃 За ресурсами", callback_data="gather_resources")],
            [InlineKeyboardButton(text="🪵 Рубка дерева", callback_data="chop_wood")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="back_to_round")]
        ]
    )
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Обработчик сбора ресурсов
@dp.callback_query(F.data == "gather_resources")
async def gather_resources(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players[user_id]
    player.is_gathering = True
    player.gather_start = datetime.now()
    player.gather_type = "resources"
    
    text = "🌳 Гуляем и добываем ресурсы.\n⏳ Вернёмся через: 2 мин. 59 сек"
    await callback.message.edit_text(text)
    await callback.answer()

# Обработчик рубки дерева
@dp.callback_query(F.data == "chop_wood")
async def chop_wood(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players[user_id]
    player.is_gathering = True
    player.gather_start = datetime.now()
    player.gather_type = "wood"
    
    text = "🪵 Рубим деревья.\n⏳ Вернёмся через: 2 мин. 59 сек"
    await callback.message.edit_text(text)
    await callback.answer()

# Обработчик "Перейти в раунд"
@dp.callback_query(F.data == "back_to_round")
async def back_to_round(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players[user_id]
    player.in_round = True
    text, keyboard = player.get_main_menu()
    await callback.message.edit_text(text, reply_markup=keyboard)
    await callback.answer()

# Обработчик "Съесть"
@dp.callback_query(F.data == "eat")
async def eat(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players[user_id]
    
    if player.hunger >= 10:
        await callback.answer("🌿 Сытость максимальная! Текущий уровень: 10", show_alert=True)
        return
    
    if player.meat <= 0:
        await callback.answer("🍗 Недостаточно еды!", show_alert=True)
        return
    
    player.meat -= 1
    player.hunger = min(10, player.hunger + 2)
    await callback.answer("🍗 Съедена 1 порция!", show_alert=True)

# Обработчик "Огонь"
@dp.callback_query(F.data == "fire")
async def fire(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    player = players[user_id]
    
    if player.fire >= 100:
        await callback.answer(f"🪵 Огонь максимальный! 🔥 Текущий уровень: 100%", show_alert=True)
        return
    
    if player.wood <= 0:
        await callback.answer(f"🪵 У тебя нет дров! 🔥 Текущий уровень: {player.fire}%", show_alert=True)
        return
    
    player.wood -= 1
    player.fire = min(100, player.fire + 10)
    await callback.answer(f"🪵 Огонь поддержан! 🔥 Текущий уровень: {player.fire}%", show_alert=True)

# Обработчик покупки класса (заглушка)
@dp.callback_query(F.data == "buy_class")
async def buy_class(callback: types.CallbackQuery):
    await callback.answer("💰 Покупка классов в разработке!", show_alert=True)

# Запуск бота
async def main():
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
