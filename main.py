import asyncio
import logging
import os
import random
import time
from threading import Thread

from flask import Flask
import aiosqlite
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

# ========== FLASK ДЛЯ ПИНГА (Render / FastCron) ==========
flask_app = Flask('')

@flask_app.route('/')
def home():
    return "Bot is alive!", 200

def run_flask():
    flask_app.run(host='0.0.0.0', port=10000)

Thread(target=run_flask, daemon=True).start()
# ========================================================

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["BOT_TOKEN"]
DB_PATH = "game.db"

MINING_DURATION = 5 * 60
BROKEN_COOLDOWN = 12 * 3600

PICKAXE_NAMES = {
    "stone":   "🪨 Каменная кирка",
    "iron":    "🔩 Железная кирка",
    "diamond": "💎 Алмазная кирка",
}

PICKAXE_SHORT = {
    "stone":   "🪨 Каменная",
    "iron":    "🔩 Железная",
    "diamond": "💎 Алмазная",
}

PICKAXE_COOLDOWN = {
    "stone":   12 * 3600,
    "iron":     9 * 3600,
    "diamond":  6 * 3600,
}

PICKAXE_MAX_DURABILITY = {
    "stone":    5,
    "iron":    10,
    "diamond": 15,
}

REPAIR_COST = {
    "stone":   ("stone",   45),
    "iron":    ("iron",    75),
    "diamond": ("diamond", 105),
}

REPAIR_SUCCESS_MSG = {
    "stone":   "🪨 Каменная кирка успешно починена!",
    "iron":    "🔩 Железная кирка успешно починена!",
    "diamond": "💎 Алмазная кирка успешно починена!",
}

UPGRADE_COST = {
    "stone": {"stone": 275, "iron": 55,  "diamond": 0},
    "iron":  {"stone": 305, "iron": 105, "diamond": 35},
}

UPGRADE_RESULT = {
    "stone": "iron",
    "iron":  "diamond",
}

UPGRADE_NAMES = {
    "stone": "🔩 Железная кирка",
    "iron":  "💎 Алмазная кирка",
}

PRESTIGE_MILESTONES = [250, 500, 750, 1000]
PRESTIGE_REWARDS = {
    250:  ("stone",   75),
    500:  ("iron",    50),
    750:  ("diamond", 25),
    1000: None,
}
MILESTONE_BIT = {250: 1, 500: 2, 750: 4, 1000: 8}


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS players (
                user_id           INTEGER PRIMARY KEY,
                pickaxe           TEXT    DEFAULT 'stone',
                stone             INTEGER DEFAULT 0,
                iron              INTEGER DEFAULT 0,
                diamond           INTEGER DEFAULT 0,
                ore_ready_at      REAL    DEFAULT 0,
                mining_ends_at    REAL    DEFAULT 0,
                durability        INTEGER DEFAULT 5,
                is_broken         INTEGER DEFAULT 0,
                prestige          INTEGER DEFAULT 0,
                claimed_milestones INTEGER DEFAULT 0
            )
        """)
        for col, definition in [
            ("durability",         "INTEGER DEFAULT 5"),
            ("is_broken",          "INTEGER DEFAULT 0"),
            ("prestige",           "INTEGER DEFAULT 0"),
            ("claimed_milestones", "INTEGER DEFAULT 0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE players ADD COLUMN {col} {definition}")
            except Exception:
                pass
        await db.commit()


async def get_player(db, user_id: int) -> dict:
    async with db.execute(
        "SELECT pickaxe, stone, iron, diamond, ore_ready_at, mining_ends_at, "
        "durability, is_broken, prestige, claimed_milestones "
        "FROM players WHERE user_id = ?",
        (user_id,),
    ) as cur:
        row = await cur.fetchone()

    if row is None:
        now = time.time()
        ore_ready = now + PICKAXE_COOLDOWN["stone"]
        await db.execute(
            "INSERT INTO players (user_id, ore_ready_at, durability) VALUES (?, ?, ?)",
            (user_id, ore_ready, PICKAXE_MAX_DURABILITY["stone"]),
        )
        await db.commit()
        return {
            "pickaxe": "stone", "stone": 0, "iron": 0, "diamond": 0,
            "ore_ready_at": ore_ready, "mining_ends_at": 0,
            "durability": PICKAXE_MAX_DURABILITY["stone"], "is_broken": 0,
            "prestige": 0, "claimed_milestones": 0,
        }

    return {
        "pickaxe":           row[0],
        "stone":             row[1],
        "iron":              row[2],
        "diamond":           row[3],
        "ore_ready_at":      row[4],
        "mining_ends_at":    row[5],
        "durability":        row[6] if row[6] is not None else PICKAXE_MAX_DURABILITY[row[0]],
        "is_broken":         row[7] if row[7] is not None else 0,
        "prestige":          row[8] if row[8] is not None else 0,
        "claimed_milestones": row[9] if row[9] is not None else 0,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def fmt_hms(secs: float) -> str:
    secs = max(0, int(secs))
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def fmt_ms(secs: float) -> str:
    secs = max(0, int(secs))
    m, s = divmod(secs, 60)
    return f"{m}:{s:02d}"


def prestige_goal(prestige: int) -> int:
    for m in PRESTIGE_MILESTONES:
        if prestige < m:
            return m
    return 1000


def build_message(player: dict):
    now = time.time()
    pickaxe = PICKAXE_NAMES[player["pickaxe"]]
    is_broken = bool(player["is_broken"])
    is_mining = player["mining_ends_at"] and now < player["mining_ends_at"]

    broken_tag = " (сломана)" if is_broken else ""

    if is_mining:
        left = player["mining_ends_at"] - now
        text = (
            f"{pickaxe}{broken_tag}\n"
            f"⛏️ Выкапываем руду.\n"
            f"⏳ Процесс займет: {fmt_ms(left)}"
        )
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏱️ Обновить время", callback_data="refresh")],
            [InlineKeyboardButton("⬅️ Назад",          callback_data="refresh")],
        ])
        return text, keyboard

    ore_ready = now >= player["ore_ready_at"]

    if ore_ready:
        text = f"{pickaxe}{broken_tag}\n✅ Руда готова к сбору."
    else:
        left = player["ore_ready_at"] - now
        text = f"{pickaxe}{broken_tag}\n⏳ Руда будет готова к сбору через: {fmt_hms(left)}"

    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("⛏️", callback_data="dig"),
        InlineKeyboardButton("🛠️", callback_data="workbench"),
        InlineKeyboardButton("🏆", callback_data="prestige"),
    ]])
    return text, keyboard


def workbench_message(player: dict):
    pickaxe = player["pickaxe"]
    text = (
        f"🛠️ Верстак.\n"
        f"⛏️ Текущая кирка: {PICKAXE_SHORT[pickaxe]}."
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("⚙️ Улучшить", callback_data="upgrade")],
        [InlineKeyboardButton("🔧 Починить", callback_data="repair")],
        [InlineKeyboardButton("⬅️ Назад",    callback_data="back")],
    ])
    return text, keyboard


def prestige_message(player: dict):
    p = player["prestige"]
    goal = prestige_goal(p)
    text = f"🏆 Престиж: {p}/{goal}"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("💰 Забрать награду", callback_data="claim_reward")],
        [InlineKeyboardButton("⬅️ Назад",           callback_data="back")],
    ])
    return text, keyboard


def roll_drops(is_broken: bool):
    if is_broken:
        if random.random() < 0.75:
            return "stone", random.randint(5, 10), "🪨"
        return "iron", random.randint(3, 5), "🔩"
    roll = random.random()
    if roll < 0.10:
        return "diamond", random.randint(3, 5), "💎"
    if roll < 0.40:
        return "iron", random.randint(5, 10), "🔩"
    return "stone", random.randint(10, 15), "🪨"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    async with aiosqlite.connect(DB_PATH) as db:
        player = await get_player(db, user_id)
    text, keyboard = build_message(player)
    await update.message.reply_text(text, reply_markup=keyboard)


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    now = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        player = await get_player(db, user_id)

        if data == "dig":
            is_mining = player["mining_ends_at"] and now < player["mining_ends_at"]
            if is_mining:
                await query.answer("⏳ Уже идёт добыча!", show_alert=True)
                return

            if now < player["ore_ready_at"]:
                await query.answer("❌ Ещё не готова!", show_alert=True)
                return

            await query.answer()

            mining_ends = now + MINING_DURATION
            await db.execute(
                "UPDATE players SET mining_ends_at = ? WHERE user_id = ?",
                (mining_ends, user_id),
            )
            await db.commit()
            player["mining_ends_at"] = mining_ends

            text, keyboard = build_message(player)
            await query.edit_message_text(text, reply_markup=keyboard)

            context.job_queue.run_once(
                finish_mining_job,
                when=MINING_DURATION,
                data={
                    "user_id":    user_id,
                    "chat_id":    query.message.chat_id,
                    "message_id": query.message.message_id,
                },
                name=f"mining_{user_id}",
            )

        elif data in ("refresh", "back"):
            await query.answer()
            text, keyboard = build_message(player)
            try:
                await query.edit_message_text(text, reply_markup=keyboard)
            except Exception:
                pass

        elif data == "workbench":
            await query.answer()
            text, keyboard = workbench_message(player)
            await query.edit_message_text(text, reply_markup=keyboard)

        elif data == "upgrade":
            pickaxe = player["pickaxe"]

            if pickaxe == "diamond":
                await query.answer("❌ Уже максимальный уровень кирки!", show_alert=True)
                return

            cost = UPGRADE_COST[pickaxe]
            if (player["stone"] < cost["stone"]
                    or player["iron"] < cost["iron"]
                    or player["diamond"] < cost["diamond"]):
                await query.answer("❌ Недостаточно ресурсов!", show_alert=True)
                return

            new_pickaxe = UPGRADE_RESULT[pickaxe]
            new_dur = PICKAXE_MAX_DURABILITY[new_pickaxe]

            await db.execute(
                """UPDATE players
                   SET pickaxe    = ?,
                       stone      = stone   - ?,
                       iron       = iron    - ?,
                       diamond    = diamond - ?,
                       durability = ?,
                       is_broken  = 0
                   WHERE user_id = ?""",
                (new_pickaxe, cost["stone"], cost["iron"], cost["diamond"],
                 new_dur, user_id),
            )
            await db.commit()

            await query.answer(f"✅ {UPGRADE_NAMES[pickaxe]} успешно сделана!", show_alert=True)

            player["pickaxe"]    = new_pickaxe
            player["stone"]     -= cost["stone"]
            player["iron"]      -= cost["iron"]
            player["diamond"]   -= cost["diamond"]
            player["durability"] = new_dur
            player["is_broken"]  = 0

            text, keyboard = workbench_message(player)
            await query.edit_message_text(text, reply_markup=keyboard)

        elif data == "repair":
            pickaxe = player["pickaxe"]

            if not player["is_broken"]:
                await query.answer("❌ Кирка ещё целая!", show_alert=True)
                return

            res_key, res_cost = REPAIR_COST[pickaxe]
            if player[res_key] < res_cost:
                await query.answer("❌ Ресурсов недостаточно!", show_alert=True)
                return

            new_dur = PICKAXE_MAX_DURABILITY[pickaxe]
            await db.execute(
                f"""UPDATE players
                    SET {res_key}  = {res_key} - ?,
                        durability = ?,
                        is_broken  = 0
                    WHERE user_id = ?""",
                (res_cost, new_dur, user_id),
            )
            await db.commit()

            await query.answer(REPAIR_SUCCESS_MSG[pickaxe], show_alert=True)

            player[res_key]      -= res_cost
            player["durability"]  = new_dur
            player["is_broken"]   = 0

            text, keyboard = workbench_message(player)
            await query.edit_message_text(text, reply_markup=keyboard)

        elif data == "prestige":
            await query.answer()
            text, keyboard = prestige_message(player)
            await query.edit_message_text(text, reply_markup=keyboard)

        elif data == "claim_reward":
            p  = player["prestige"]
            cm = player["claimed_milestones"]

            to_claim = None
            for m in PRESTIGE_MILESTONES:
                if p >= m and PRESTIGE_REWARDS[m] is not None:
                    if not (cm & MILESTONE_BIT[m]):
                        to_claim = m
                        break

            if to_claim is None:
                await query.answer("❌ Нет доступных наград!", show_alert=True)
                return

            res_key, res_amount = PRESTIGE_REWARDS[to_claim]
            new_cm = cm | MILESTONE_BIT[to_claim]

            await db.execute(
                f"""UPDATE players
                    SET {res_key}           = {res_key} + ?,
                        claimed_milestones  = ?
                    WHERE user_id = ?""",
                (res_amount, new_cm, user_id),
            )
            await db.commit()

            await query.answer("✅ Награда успешно получена!", show_alert=True)

            player[res_key]             += res_amount
            player["claimed_milestones"] = new_cm

            text, keyboard = prestige_message(player)
            await query.edit_message_text(text, reply_markup=keyboard)


# ---------------------------------------------------------------------------
# Mining finish job
# ---------------------------------------------------------------------------

async def finish_mining_job(context: ContextTypes.DEFAULT_TYPE):
    job_data   = context.job.data
    user_id    = job_data["user_id"]
    chat_id    = job_data["chat_id"]
    message_id = job_data["message_id"]

    now = time.time()

    async with aiosqlite.connect(DB_PATH) as db:
        player = await get_player(db, user_id)

        was_broken = bool(player["is_broken"])
        resource, amount, emoji = roll_drops(was_broken)

        new_dur    = player["durability"]
        new_broken = was_broken
        if not was_broken:
            new_dur = max(0, player["durability"] - 1)
            if new_dur == 0:
                new_broken = True

        next_cooldown = BROKEN_COOLDOWN if new_broken else PICKAXE_COOLDOWN[player["pickaxe"]]
        new_ore_ready = now + next_cooldown

        new_prestige = min(1000, player["prestige"] + random.randint(5, 15))

        await db.execute(
            f"""UPDATE players
                SET {resource}     = {resource} + ?,
                    mining_ends_at = 0,
                    ore_ready_at   = ?,
                    durability     = ?,
                    is_broken      = ?,
                    prestige       = ?
                WHERE user_id = ?""",
            (amount, new_ore_ready, new_dur, int(new_broken), new_prestige, user_id),
        )
        await db.commit()
        player = await get_player(db, user_id)

    broken_note = "\n⚠️ Кирка сломалась!" if (new_broken and not was_broken) else ""
    try:
        await context.bot.send_message(
            chat_id=chat_id,
            text=f"✅ Руда успешно выкопана! Получено: {amount} {emoji}{broken_note}",
        )
    except Exception as e:
        logger.error("send_message error: %s", e)

    text, keyboard = build_message(player)
    try:
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=message_id,
            text=text,
            reply_markup=keyboard,
        )
    except Exception:
        try:
            await context.bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)
        except Exception as e:
            logger.error("edit fallback error: %s", e)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    asyncio.get_event_loop().run_until_complete(init_db())
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    logger.info("Bot started")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
