import asyncio
import json
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    BotCommand,
    ReplyKeyboardMarkup,
    KeyboardButton,
)
import aiosqlite
from dotenv import load_dotenv
import os

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

DB_NAME = "cleaning.db"

main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="📸 Уборка"),
            KeyboardButton(text="🏆 Рейтинг"),
        ],
        [
            KeyboardButton(text="📋 История"),
            KeyboardButton(text="📜 Правила"),
        ],
    ],
    resize_keyboard=True,
)


async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cleanings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    date TEXT,
    photo_file_id TEXT,
    votes TEXT DEFAULT '{}',
    closed INTEGER DEFAULT 0
)
        """)
        await db.commit()


def build_vote_card(cleaning_id: int, author_name: str, votes: dict) -> tuple[str, InlineKeyboardMarkup]:
    """Строит текст карточки и клавиатуру голосования для конкретной уборки."""
    if votes:
        values = list(votes.values())
        avg = sum(values) / len(values)
        tally = f"\n\n🗳 Голосов: {len(values)} | Средний балл: {avg:.1f}"
    else:
        tally = "\n\n🗳 Пока никто не проголосовал."

    text = (
        f"📸 {author_name} заявляет уборку!\n"
        f"Сколько баллов дать?\n"
        f"1 — мелкая уборка, 5 — обычная, 10 — генеральная."
        f"{tally}"
    )

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="1️⃣", callback_data=f"vote_{cleaning_id}_1"),
            InlineKeyboardButton(text="5️⃣", callback_data=f"vote_{cleaning_id}_5"),
            InlineKeyboardButton(text="🔟", callback_data=f"vote_{cleaning_id}_10"),
            InlineKeyboardButton(text="❌", callback_data=f"vote_{cleaning_id}_0"),
        ]
    ])
    return text, keyboard


@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! 👋\n"
        "Отправь фото уборки с текстом 'убрался', 'clean' или 'убр' в подписи.\n"
        "Дальше все (кроме автора) голосуют, сколько баллов дать.\n\n"
        "/stats — статистика\n"
        "/pending — последние уборки, можно проголосовать или переголосовать\n"
        "/leaderboard — топ"
        "/info — подробная информация\n",
        reply_markup=main_keyboard
    )


@dp.message(Command("info"))
async def info(message: types.Message):
    await message.answer(
        "📋 **Информация о боте**\n\n"
        "🧹 **Как заявить уборку:**\n"
        "Отправь фото с подписью, содержащей слова: 'уборка', 'clean', 'убр', 'убрался', 'убираю' или 'убра'\n\n"
        "🗳 **Как голосовать:**\n"
        "После отправки фото появится карточка с кнопками:\n"
        "1️⃣ — мелкая уборка\n"
        "5️⃣ — обычная уборка\n"
        "🔟 — генеральная уборка\n"
        "❌ — не засчитывать\n\n"
        "⚠️ **Правила:**\n"
        "- Нельзя голосовать за свою уборку\n"
        "- Можно переголосовать (оценка изменится)\n"
        "- Уборка закрывается после 2+ голосов\n\n"
        "📊 **Команды:**\n"
        "/start — приветствие и базовая справка\n"
        "/info — эта информация\n"
        "/pending — последние уборки для голосования\n"
        "/stats — рейтинг всех участников\n"
        "/leaderboard — топ уборщиков\n\n"
        "💡 **Совет:** Используй /pending чтобы проголосовать за пропущенные уборки!"
    )


@dp.message(F.text == "📸 Уборка")
async def btn_cleaning(message: types.Message):
    await message.answer(
        "📸 Отправь фото уборки с подписью, содержащей слова: 'уборка', 'clean', 'убр', 'убрался', 'убираю' или 'убра'"
    )


@dp.message(F.text == "🏆 Рейтинг")
async def btn_rating(message: types.Message):
    await stats(message)


@dp.message(F.text == "📋 История")
async def btn_history(message: types.Message):
    await pending(message)


@dp.message(F.text == "📜 Правила")
async def btn_rules(message: types.Message):
    await info(message)


@dp.message(F.photo)
async def handle_photo(message: types.Message):
    logging.info(f"DEBUG PHOTO: Получено сообщение от {message.from_user.full_name}")
    logging.info(f"DEBUG PHOTO: Есть фото: {bool(message.photo)}")
    logging.info(f"DEBUG PHOTO: Caption raw: '{message.caption}'")
    
    if not message.photo:
        logging.info("DEBUG PHOTO: Нет фото")
        return
    
    caption = (message.caption or "").lower()
    logging.info(f"DEBUG PHOTO: Caption lower: '{caption}'")
    
    keywords = ["уборка", "clean", "убр", "убрался", "убираю", "убра"]
    found = any(word in caption for word in keywords)
    logging.info(f"DEBUG PHOTO: Ключевое слово найдено: {found}")
    
    if not found:
        logging.info("DEBUG PHOTO: Не найдено ключевое слово — выход")
        return

    logging.info("DEBUG PHOTO: ✅ Всё ок, сохраняем уборку!")
    
    file_id = message.photo[-1].file_id
    author_name = message.from_user.username or message.from_user.full_name

    async with aiosqlite.connect(DB_NAME) as db:
        cursor = await db.execute(
            "INSERT INTO cleanings (user_id, username, date, photo_file_id, votes) VALUES (?, ?, ?, ?, ?)",
            (message.from_user.id, author_name, datetime.now().isoformat(), file_id, "{}"),
        )
        await db.commit()
        cleaning_id = cursor.lastrowid

    text, keyboard = build_vote_card(cleaning_id, author_name, {})
    await message.answer(text, reply_markup=keyboard)
    logging.info("DEBUG PHOTO: Сообщение с клавиатурой отправлено")

@dp.callback_query(F.data.startswith("vote_"))
@dp.callback_query(F.data.startswith("vote_"))
async def vote_handler(callback: types.CallbackQuery):
    _, cleaning_id_str, points_str = callback.data.split("_")

    cleaning_id = int(cleaning_id_str)
    points = int(points_str)

    async with aiosqlite.connect(DB_NAME) as db:

        async with db.execute(
            """
            SELECT user_id, username, votes, closed
            FROM cleanings
            WHERE id = ?
            """,
            (cleaning_id,)
        ) as cursor:
            row = await cursor.fetchone()


        if row is None:
            await callback.answer(
                "Уборка не найдена",
                show_alert=True
            )
            return


        author_id, author_name, votes_json, closed = row


        if closed:
            await callback.answer(
                "Уборка уже закрыта, голосовать нельзя 🚫",
                show_alert=True
            )
            return


        if callback.from_user.id == author_id:
            await callback.answer(
                "Не ахуевай, нельзя голосовать за свою уборку 🙅",
                show_alert=True
            )
            return


        votes = json.loads(votes_json or "{}")


        # если голосовал раньше — просто меняем оценку
        votes[str(callback.from_user.id)] = points


        # минимум 2 человека проголосовали
        closed = 1 if len(votes) >= 2 else 0


        await db.execute(
            """
            UPDATE cleanings
            SET votes = ?, closed = ?
            WHERE id = ?
            """,
            (
                json.dumps(votes),
                closed,
                cleaning_id
            )
        )

        await db.commit()



    text, keyboard = build_vote_card(
        cleaning_id,
        author_name,
        votes
    )


    if closed:
        avg = sum(votes.values()) / len(votes)

        text += (
            "\n\n"
            "✅ Уборка закрыта\n"
            f"Итоговая оценка: {avg:.1f}/10"
        )


    try:
        await callback.message.edit_text(
            text,
            reply_markup=keyboard
        )

    except Exception:
        await callback.message.edit_caption(
            caption=text,
            reply_markup=keyboard
        )


    await callback.answer("Голос учтён ✅")


@dp.message(Command("pending"))
async def pending(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT id, username, date FROM cleanings ORDER BY id DESC LIMIT 10"
        ) as cursor:
            rows = await cursor.fetchall()

    if not rows:
        await message.answer("Пока нет ни одной уборки.")
        return

    buttons = []
    for cleaning_id, username, date_str in rows:
        dt = datetime.fromisoformat(date_str)
        label = f"{username} — {dt.strftime('%d.%m %H:%M')}"
        buttons.append([InlineKeyboardButton(text=label, callback_data=f"show_{cleaning_id}")])

    await message.answer(
        "Последние уборки (выбери, чтобы посмотреть и проголосовать):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@dp.callback_query(F.data.startswith("show_"))
async def show_handler(callback: types.CallbackQuery):
    cleaning_id = int(callback.data.split("_")[1])

    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute(
            "SELECT username, votes, photo_file_id FROM cleanings WHERE id = ?", (cleaning_id,)
        ) as cursor:
            row = await cursor.fetchone()

    if row is None:
        await callback.answer("Не найдено.", show_alert=True)
        return

    username, votes_json, photo_file_id = row
    votes = json.loads(votes_json or "{}")
    text, keyboard = build_vote_card(cleaning_id, username, votes)
    await callback.message.answer_photo(photo_file_id, caption=text, reply_markup=keyboard)
    await callback.answer()


@dp.message(Command("stats"))
@dp.message(Command("leaderboard"))
async def stats(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id, username, votes FROM cleanings") as cursor:
            rows = await cursor.fetchall()

    totals: dict[int, dict] = {}
    for user_id, username, votes_json in rows:
        votes = json.loads(votes_json or "{}")
        if not votes:
            continue
        avg = sum(votes.values()) / len(votes)
        entry = totals.setdefault(user_id, {"username": username, "points": 0.0})
        entry["points"] += avg

    ranking = sorted(totals.values(), key=lambda x: x["points"], reverse=True)

    if not ranking:
        await message.answer("Пока никто не убирался 😢")
        return

    text = "🏆 Рейтинг уборок:\n\n"
    for i, entry in enumerate(ranking, 1):
        text += f"{i}. {entry['username']} — {entry['points']:.1f} баллов\n"
    await message.answer(text)


async def main():
    await init_db()
    await bot.set_my_commands([
        BotCommand(command="start", description="Как пользоваться ботом"),
        BotCommand(command="info", description="Подробная информация"),
        BotCommand(command="pending", description="Последние уборки / голосование"),
        BotCommand(command="stats", description="Рейтинг уборок"),
        BotCommand(command="leaderboard", description="Топ уборщиков"),
    ])
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())