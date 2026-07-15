import asyncio
import logging
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import aiosqlite
from dotenv import load_dotenv
import os

load_dotenv()
bot = Bot(token=os.getenv("BOT_TOKEN"))
dp = Dispatcher()

DB_NAME = "cleaning.db"

async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS cleanings (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                username TEXT,
                date TEXT,
                approved INTEGER DEFAULT 0,
                photo_file_id TEXT
            )
        """)
        await db.commit()

@dp.message(Command("start"))
async def start(message: types.Message):
    await message.answer(
        "Привет! 👋\n"
        "Отправь фото уборки с текстом 'уборка', 'clean' или 'убра' в подписи.\n"
        "/stats — статистика\n"
        "/leaderboard — топ"
    )

@dp.message(F.photo)
async def handle_photo(message: types.Message):
    caption = (message.caption or "").lower()
    if any(word in caption for word in ["уборка", "clean", "убра"]):
        file_id = message.photo[-1].file_id
        
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute(
                "INSERT INTO cleanings (user_id, username, date, photo_file_id) VALUES (?, ?, ?, ?)",
                (message.from_user.id, message.from_user.username or message.from_user.full_name, 
                 datetime.now().isoformat(), file_id)
            )
            await db.commit()
        
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{message.from_user.id}")],
            [InlineKeyboardButton(text="❌ Оспорить", callback_data=f"challenge_{message.from_user.id}")]
        ])
        
        await message.answer(
            f"📸 {message.from_user.full_name} заявляет уборку!\nПодтверждаете?",
            reply_markup=keyboard
        )
    else:
        await message.answer("Добавь в подпись слово 'уборка' или 'clean'")

@dp.callback_query()
async def callback_handler(callback: types.CallbackQuery):
    action, user_id_str = callback.data.split("_")
    user_id = int(user_id_str)
    
    if action == "approve":
        async with aiosqlite.connect(DB_NAME) as db:
            await db.execute("UPDATE cleanings SET approved = 1 WHERE user_id = ? AND approved = 0", (user_id,))
            await db.commit()
        await callback.message.edit_text("✅ Уборка подтверждена!")
    elif action == "challenge":
        await callback.message.edit_text("❌ Уборка оспорена.")

@dp.message(Command("stats"))
@dp.message(Command("leaderboard"))
async def stats(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("""
            SELECT username, COUNT(*) as points 
            FROM cleanings 
            WHERE approved = 1 
            GROUP BY user_id, username 
            ORDER BY points DESC
        """) as cursor:
            rows = await cursor.fetchall()
        
        text = "🏆 Рейтинг уборок:\n\n"
        for i, (username, points) in enumerate(rows, 1):
            text += f"{i}. {username} — {points} баллов\n"
        await message.answer(text or "Пока никто не убирался 😢")

async def main():
    await init_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())