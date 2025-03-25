import asyncio
import asyncpg
import os
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
DATABASE_URL = os.getenv("DATABASE_URL")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Подключение к базе данных PostgreSQL
async def create_db_pool():
    return await asyncpg.create_pool(DATABASE_URL)

db_pool = None

async def get_db():
    global db_pool
    if db_pool is None:
        db_pool = await create_db_pool()
    return db_pool

# Создание таблиц
async def setup_db():
    db = await get_db()
    async with db.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                tg_id BIGINT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                points INTEGER DEFAULT 0
            );
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                home_team TEXT NOT NULL,
                away_team TEXT NOT NULL,
                match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(tg_id),
                match_id INTEGER REFERENCES matches(id),
                predicted_score TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS results (
                id SERIAL PRIMARY KEY,
                match_id INTEGER REFERENCES matches(id),
                final_score TEXT NOT NULL
            );
        """)

# Клавиатура для пользователя
user_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мой профиль")],
        [KeyboardButton(text="Сделать прогноз")],
        [KeyboardButton(text="Таблица лидеров")],
        [KeyboardButton(text="Посмотреть мой прогноз")]
    ], resize_keyboard=True
)

# Клавиатура для администратора
admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Внести результаты")],
        [KeyboardButton(text="Внести новые матчи")]
    ], resize_keyboard=True
)

# Обработчик команды /start
@dp.message(Command("start"))
async def start(message: Message):
    db = await get_db()
    user_id = message.from_user.id

    async with db.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE tg_id=$1", user_id)
        if not user:
            await message.answer("Введите ваше имя:")
        else:
            await message.answer("Добро пожаловать!", reply_markup=user_keyboard)

# Внесение имени пользователя
@dp.message()
async def set_name(message: Message):
    db = await get_db()
    user_id = message.from_user.id
    user_name = message.text

    async with db.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE tg_id=$1", user_id)
        if not user:
            await conn.execute("INSERT INTO users (tg_id, name) VALUES ($1, $2)", user_id, user_name)
            await message.answer("Имя сохранено!", reply_markup=user_keyboard)

# Показать профиль пользователя
@dp.message(lambda message: message.text == "Мой профиль")
async def show_profile(message: Message):
    db = await get_db()
    user_id = message.from_user.id

    async with db.acquire() as conn:
        user = await conn.fetchrow("SELECT * FROM users WHERE tg_id=$1", user_id)
        if user:
            await message.answer(f"👤 Имя: {user['name']}\n🏆 Очки: {user['points']}")
        else:
            await message.answer("Вы не зарегистрированы!")

# Внести прогноз
@dp.message(lambda message: message.text == "Сделать прогноз")
async def make_prediction(message: Message):
    db = await get_db()
    user_id = message.from_user.id

    now = datetime.utcnow()
    friday_deadline = now.replace(hour=20, minute=0, second=0, microsecond=0) + timedelta((4 - now.weekday()) % 7)

    if now > friday_deadline:
        await message.answer("⏳ Прием прогнозов остановлен.")
        return

    async with db.acquire() as conn:
        matches = await conn.fetch("SELECT * FROM matches WHERE id NOT IN (SELECT match_id FROM predictions WHERE user_id=$1)", user_id)
        if not matches:
            await message.answer("Вы уже сделали прогноз на эту неделю.")
            return

        for match in matches:
            await message.answer(f"{match['home_team']} - {match['away_team']}\nВведите счет в формате 2-1:")

# Таблица лидеров
@dp.message(lambda message: message.text == "Таблица лидеров")
async def show_leaderboard(message: Message):
    db = await get_db()

    async with db.acquire() as conn:
        top_users = await conn.fetch("SELECT name, points FROM users ORDER BY points DESC LIMIT 10")
        leaderboard = "\n".join([f"{idx+1}. {user['name']} - {user['points']} очков" for idx, user in enumerate(top_users)])
        await message.answer(f"🏆 Таблица лидеров:\n\n{leaderboard}")

# Внесение результатов (для админа)
@dp.message(lambda message: message.text == "Внести результаты" and message.from_user.id == ADMIN_ID)
async def enter_results(message: Message):
    await message.answer("Функция внесения результатов пока не реализована.")

# Внесение новых матчей (для админа)
@dp.message(lambda message: message.text == "Внести новые матчи" and message.from_user.id == ADMIN_ID)
async def enter_new_matches(message: Message):
    await message.answer("Функция внесения новых матчей пока не реализована.")

# Запуск бота
async def main():
    await setup_db()
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
