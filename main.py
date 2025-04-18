import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor
from datetime import datetime, timedelta
import os

# Инициализация бота
API_TOKEN = os.getenv('BOT_TOKEN')  # Получаем токен из переменной окружения
if not API_TOKEN:
    raise ValueError("BOT_TOKEN не найден в переменных окружения!")

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# Подключение к базе данных
conn = sqlite3.connect('withlilybot.db', check_same_thread=False)
cursor = conn.cursor()

# Создание таблиц в базе данных
cursor.execute('''
CREATE TABLE IF NOT EXISTS fit_tracker (
    user_id INTEGER,
    date TEXT,
    steps INTEGER,
    calories INTEGER,
    weight REAL
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS plans (
    user_id INTEGER,
    date TEXT,
    plan TEXT,
    time TEXT
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS wishlist (
    user_id INTEGER,
    link TEXT,
    name TEXT,
    category TEXT
)
''')

conn.commit()

# Главное меню (ReplyKeyboardMarkup)
main_menu_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
main_menu_keyboard.add(
    KeyboardButton("Fit трекер"),
    KeyboardButton("Мои планы"),
    KeyboardButton("Мои хотелки")
)

# Fit трекер меню (InlineKeyboardMarkup)
fit_menu = InlineKeyboardMarkup(row_width=1)
fit_menu.add(
    InlineKeyboardButton("Записать шаги за сегодня", callback_data="record_steps"),
    InlineKeyboardButton("Записать калории за сегодня", callback_data="record_calories"),
    InlineKeyboardButton("Записать вес", callback_data="record_weight"),
    InlineKeyboardButton("Статистика за неделю", callback_data="weekly_stats"),
    InlineKeyboardButton("Статистика за месяц", callback_data="monthly_stats")
)

# Мои планы меню (InlineKeyboardMarkup)
plans_menu = InlineKeyboardMarkup(row_width=1)
plans_menu.add(
    InlineKeyboardButton("Добавить план", callback_data="add_plan"),
    InlineKeyboardButton("Планы на неделю", callback_data="week_plans"),
    InlineKeyboardButton("Планы на месяц", callback_data="month_plans")
)

# Мои хотелки меню (InlineKeyboardMarkup)
wishlist_menu = InlineKeyboardMarkup(row_width=1)
wishlist_menu.add(
    InlineKeyboardButton("Добавить хотелку", callback_data="add_wishlist"),
    InlineKeyboardButton("Список хотелок", callback_data="wishlist_list"),
    InlineKeyboardButton("По категориям", callback_data="wishlist_categories")
)

# Команда /start
@dp.message_handler(commands=['start'])
async def send_welcome(message: types.Message):
    await message.answer(
        "Привет! Это withLilyBot. Выберите раздел:",
        reply_markup=main_menu_keyboard
    )

# Обработка текстовых команд из главного меню
@dp.message_handler(lambda message: message.text in ["Fit трекер", "Мои планы", "Мои хотелки"])
async def process_main_menu_text(message: types.Message):
    if message.text == "Fit трекер":
        await message.answer("Выберите действие в Fit трекере:", reply_markup=fit_menu)
    elif message.text == "Мои планы":
        await message.answer("Выберите действие в Моих планах:", reply_markup=plans_menu)
    elif message.text == "Мои хотелки":
        await message.answer("Выберите действие в Моих хотелках:", reply_markup=wishlist_menu)

# Обработка инлайн-кнопок
@dp.callback_query_handler(lambda c: c.data in ["fit_tracker", "my_plans", "wishlist"])
async def process_main_menu_inline(callback_query: types.CallbackQuery):
    if callback_query.data == "fit_tracker":
        await bot.send_message(callback_query.from_user.id, "Выберите действие в Fit трекере:", reply_markup=fit_menu)
    elif callback_query.data == "my_plans":
        await bot.send_message(callback_query.from_user.id, "Выберите действие в Моих планах:", reply_markup=plans_menu)
    elif callback_query.data == "wishlist":
        await bot.send_message(callback_query.from_user.id, "Выберите действие в Моих хотелках:", reply_markup=wishlist_menu)

# Реализация Fit трекера
@dp.callback_query_handler(lambda c: c.data in ["record_steps", "record_calories", "record_weight"])
async def record_fit_data(callback_query: types.CallbackQuery):
    action = callback_query.data.split("_")[1]
    await bot.send_message(callback_query.from_user.id, f"Введите количество {action}:")
    dp.register_message_handler(lambda m: save_fit_data(m, action), state="*")

def save_fit_data(message: types.Message, action):
    user_id = message.from_user.id
    value = int(message.text)
    today = datetime.now().strftime("%Y-%m-%d")
    cursor.execute(f'INSERT INTO fit_tracker (user_id, date, {action}) VALUES (?, ?, ?)', (user_id, today, value))
    conn.commit()
    return bot.send_message(user_id, f"{action.capitalize()} записаны!")

# Реализация статистики
@dp.callback_query_handler(lambda c: c.data in ["weekly_stats", "monthly_stats"])
async def show_stats(callback_query: types.CallbackQuery):
    user_id = callback_query.from_user.id
    period = callback_query.data.split("_")[0]
    today = datetime.now()
    if period == "weekly":
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    else:
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    
    stats = cursor.execute('''
    SELECT date, steps, calories, weight FROM fit_tracker 
    WHERE user_id = ? AND date BETWEEN ? AND ?
    ''', (user_id, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d"))).fetchall()

    # Формирование статистики
    response = f"СТАТИСТИКА ЗА {period.upper()}:\n"
    total_steps = sum([s[1] for s in stats if s[1]])
    total_calories = sum([s[2] for s in stats if s[2]])
    last_weight = [s[3] for s in stats if s[3]][-1] if any(s[3] for s in stats) else "не указан"
    response += f"Вес: {last_weight}\n"
    response += f"Средние шаги: {total_steps // len(stats)}\n"
    response += f"Средние калории: {total_calories // len(stats)}\n"

    await bot.send_message(user_id, response)

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
