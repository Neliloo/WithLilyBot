import telebot
from telebot import types
import json
import datetime
import os
import schedule
import time
import threading

TOKEN = os.getenv("TOKEN")
bot = telebot.TeleBot(TOKEN)

FIT_FILE = "fit_data.json"
PLANS_FILE = "plans_data.json"
WANTS_FILE = "wants_data.json"

def load_data(filename):
    if not os.path.exists(filename):
        return {}
    with open(filename, "r") as f:
        return json.load(f)

def save_data(data, filename):
    with open(filename, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def get_today():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def get_week_dates():
    today = datetime.date.today()
    start = today - datetime.timedelta(days=today.weekday())
    return [(start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]

def get_month_dates():
    today = datetime.date.today()
    return [f"{today.year}-{today.month:02}-{i:02}" for i in range(1, 32)]

user_states = {}
temp_plans = {}
temp_wants = {}

@bot.message_handler(commands=['start'])
def start_message(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("📊 Fit трекер", "📅 Мои планы", "🎁 Хотелки")
    bot.send_message(message.chat.id, "Привет! Я бот WithLilyBot 💜\nВыбери раздел:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📊 Fit трекер")
def fit_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("➕ Вес", "➕ Шаги", "➕ Калории",
               "📈 Статистика недели", "📆 Статистика месяца", "⬅️ Назад")
    bot.send_message(message.chat.id, "Выбери, что хочешь записать или посмотреть:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "📅 Мои планы")
def plans_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Записать план", "📋 Планы на неделю", "📅 Планы на месяц", "⬅️ Назад")
    bot.send_message(message.chat.id, "Раздел 'Мои планы'. Что делаем?", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "🎁 Хотелки")
def wants_menu(message):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add("➕ Добавить хотелку", "📂 Список по категории", "⬅️ Назад")
    bot.send_message(message.chat.id, "Раздел 'Хотелки'. Выбери действие:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "➕ Добавить хотелку")
def add_want_step1(message):
    user_states[message.chat.id] = "want_link"
    bot.send_message(message.chat.id, "Вставь ссылку на хотелку 🌐")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == "want_link")
def add_want_link(message):
    temp_wants[message.chat.id] = {"link": message.text}
    user_states[message.chat.id] = "want_title"
    bot.send_message(message.chat.id, "Как назвать эту хотелку?")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == "want_title")
def add_want_title(message):
    temp_wants[message.chat.id]["title"] = message.text
    user_states[message.chat.id] = "want_category"
    bot.send_message(message.chat.id, "Укажи категорию (например: одежда, техника, книги...)")

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == "want_category")
def add_want_category(message):
    entry = temp_wants.pop(message.chat.id)
    entry["category"] = message.text
    user_states.pop(message.chat.id)

    data = load_data(WANTS_FILE)
    user_id = str(message.chat.id)
    if user_id not in data:
        data[user_id] = []
    data[user_id].append(entry)
    save_data(data, WANTS_FILE)

    bot.send_message(message.chat.id, "Хотелка сохранена! 💖")

@bot.message_handler(func=lambda m: m.text == "📂 Список по категории")
def show_wants(message):
    data = load_data(WANTS_FILE).get(str(message.chat.id), [])
    if not data:
        bot.send_message(message.chat.id, "Ты пока не добавляла хотелок ✨")
        return

    cats = list(set([w['category'] for w in data]))
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    for c in cats:
        markup.add(c)
    markup.add("⬅️ Назад")
    bot.send_message(message.chat.id, "Выбери категорию:", reply_markup=markup)
    user_states[message.chat.id] = "want_category_view"

@bot.message_handler(func=lambda m: user_states.get(m.chat.id) == "want_category_view")
def show_category_list(message):
    category = message.text
    data = load_data(WANTS_FILE).get(str(message.chat.id), [])
    wants = [w for w in data if w['category'].lower() == category.lower()]

    if wants:
        text = f"🎁 Хотелки в категории '{category}':\n\n"
        for w in wants:
            text += f"• <a href='{w['link']}'>{w['title']}</a>\n"
        bot.send_message(message.chat.id, text, parse_mode='HTML', disable_web_page_preview=True)
    else:
        bot.send_message(message.chat.id, f"В категории '{category}' ничего нет ✨")

    user_states.pop(message.chat.id, None)

@bot.message_handler(func=lambda m: m.text == "⬅️ Назад")
def back_to_main(message):
    start_message(message)

@bot.message_handler(func=lambda message: True)
def fallback(message):
    bot.send_message(message.chat.id, "Я тебя не поняла 🙈 Нажми /start или выбери пункт из меню.")

def morning_reminder():
    data = load_data(PLANS_FILE)
    today = get_today()
    for user_id, plans in data.items():
        todays = [p for p in plans if p['date'] == today]
        if todays:
            msg = "📌 Твои планы на сегодня:\n"
            for p in todays:
                t = f"[{p['time']}] " if p['time'] != "-" else ""
                msg += f"— {t}{p['text']}\n"
            try:
                bot.send_message(user_id, msg)
            except:
                continue

def schedule_jobs():
    def run_schedule():
        while True:
            schedule.run_pending()
            time.sleep(60)
    schedule.every().day.at("08:00").do(morning_reminder)
    threading.Thread(target=run_schedule, daemon=True).start()

schedule_jobs()
bot.infinity_polling()
