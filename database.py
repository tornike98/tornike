import asyncpg
import os
from dotenv import load_dotenv

load_dotenv()
DB_DSN = os.getenv("DB_DSN")

# Подключение к базе данных
async def connect_db():
    return await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=10)

# Создание таблиц
async def create_tables(pool):
    async with pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                points INT DEFAULT 0
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS matches (
                id SERIAL PRIMARY KEY,
                team1 TEXT,
                team2 TEXT,
                score TEXT NULL
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS predictions (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(user_id),
                match_id INT REFERENCES matches(id),
                predicted_score TEXT,
                UNIQUE(user_id, match_id)
            )
        ''')

# Получение таблицы лидеров
async def get_leaderboard(pool):
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT username, points FROM users ORDER BY points DESC LIMIT 10"
        )
        return rows

# Добавление пользователя
async def add_user(pool, user_id, username, full_name):
    async with pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO users (user_id, username, full_name) 
            VALUES ($1, $2, $3) ON CONFLICT (user_id) DO NOTHING
        ''', user_id, username, full_name)

# Проверка, делал ли пользователь прогноз
async def has_made_prediction(pool, user_id):
    async with pool.acquire() as conn:
        result = await conn.fetchval('''
            SELECT COUNT(*) FROM predictions WHERE user_id = $1
        ''', user_id)
        return result > 0
