import telebot
import json
import random
import os
import re
import time
from telebot import types
from datetime import datetime, timedelta, timezone

# Ініціалізація бота
TOKEN = os.getenv('7991439480:AAGR8KyC3RnBEVlYpP8-39ExcI-SSAhmPC0')
bot = telebot.TeleBot(TOKEN)

# Константи
ADMIN_ID = int(os.getenv('ADMIN_ID', '6974875043'))
CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'CodeMovie1')
MOVIES_FILE = 'movies.json'
USERS_FILE = 'users.json'
ADMINS_FILE = 'admins.json'

# Глобальні змінні для зберігання стану
user_states = {}
temp_data = {}
genre_search_data = {}
user_movie_history = {}
genre_movie_history = {}

# Допоміжні функції
def ensure_file_exists(filename, default):
    """Перевіряє існування файлу, створює якщо не існує"""
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)

def load_movies():
    """Завантажує список фільмів з файлу"""
    ensure_file_exists(MOVIES_FILE, [])
    with open(MOVIES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_movies(movies):
    """Зберігає список фільмів у файл"""
    with open(MOVIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)

def log_user(user_id):
    """Логує активність користувача"""
    now = datetime.now(timezone.utc).isoformat()
    ensure_file_exists(USERS_FILE, {})
    
    with open(USERS_FILE, 'r+', encoding='utf-8') as f:
        users = json.load(f)
        users[str(user_id)] = now
        f.seek(0)
        json.dump(users, f, ensure_ascii=False, indent=2)

def check_subscription(user_id):
    """Перевіряє чи підписаний користувач на канал"""
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "creator", "administrator"]
    except Exception as e:
        print(f"Помилка перевірки підписки: {e}")
        return False

def normalize_genre(text):
    """Нормалізує назву жанру"""
    return re.sub(r'[^a-zA-Zа-яА-ЯіїєґІЇЄҐ0-9\s]', '', text.lower().strip())

def format_movie(movie):
    """Форматує інформацію про фільм"""
    return (f"🎬 {movie.get('title', 'Невідомо')}\n"
            f"⭐ IMDb: {movie.get('rating', 'Невідомо')}\n"
            f"⏱ Тривалість: {movie.get('duration', 'Невідомо')}\n"
            f"📅 Рік: {movie.get('year', 'Невідомо')}\n"
            f"🔞 Вік: {movie.get('age_category', 'Не вказано')}\n"
            f"🌍 Країна: {movie.get('country', 'Невідомо')}\n"
            f"🎭 Жанр: {movie.get('genre', 'Невідомо')}\n"
            f"#Код: {movie.get('code', 'Невідомо')}")

# Меню та інтерфейс
def send_main_menu(chat_id):
    """Надсилає головне меню"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🔍 Пошук фільму за кодом')
    markup.row('🎲 Випадковий фільм', '🎬 Пошук за жанром')
    if str(chat_id) == str(ADMIN_ID):
        markup.row('Адмін панель')
    markup.row('ℹ️ Інформація про бота')
    bot.send_message(chat_id, 'Оберіть опцію з меню:', reply_markup=markup)

def send_admin_panel(user_id):
    """Надсилає адмін панель"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('➕ Додати фільм', '➖ Видалити фільм')
    markup.row('📊 Статистика', '◀️ Назад')
    bot.send_message(user_id, 'Адмін панель:', reply_markup=markup)

# Обробники команд
@bot.message_handler(commands=['start'])
def start(message):
    """Обробник команди /start"""
    user_id = message.from_user.id
    if not check_subscription(user_id):
        markup = types.InlineKeyboardMarkup()
        btn = types.InlineKeyboardButton('Підписатися', url=f'https://t.me/{CHANNEL_USERNAME}')
        markup.add(btn)
        bot.send_message(message.chat.id, 'Щоб користуватися ботом, підпишіться на канал:', reply_markup=markup)
        return
    log_user(user_id)
    send_main_menu(message.chat.id)

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Головний обробник повідомлень"""
    user_id = message.from_user.id
    text = message.text.strip()

    if not check_subscription(user_id):
        bot.send_message(user_id, 'Будь ласка, підпишіться на канал для продовження.')
        return

    if text == '🔍 Пошук фільму за кодом':
        bot.send_message(user_id, 'Введіть код фільму:')
        user_states[user_id] = 'awaiting_code'

    elif text == '🎲 Випадковий фільм':
        movies = load_movies()
        if movies:
            movie = random.choice(movies)
            bot.send_message(user_id, format_movie(movie))
        else:
            bot.send_message(user_id, 'База фільмів порожня.')

    elif text == 'ℹ️ Інформація про бота':
        bot.send_message(user_id, 
                        "Цей бот допомагає знаходити фільми за кодом.\n"
                        "Доступні команди:\n"
                        "- Пошук за кодом\n"
                        "- Випадковий фільм\n"
                        "- Пошук за жанром")

    elif text == 'Адмін панель' and user_id == ADMIN_ID:
        send_admin_panel(user_id)

    elif text == '📊 Статистика' and user_id == ADMIN_ID:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            users = json.load(f)
        bot.send_message(user_id, f'Кількість унікальних користувачів: {len(users)}')

    elif text == '◀️ Назад':
        send_main_menu(user_id)

# Запуск бота
if __name__ == '__main__':
    print("Бот запускається...")
    ensure_file_exists(MOVIES_FILE, [])
    ensure_file_exists(USERS_FILE, {})
    ensure_file_exists(ADMINS_FILE, [ADMIN_ID])
    
    try:
        bot.polling(none_stop=True)
    except Exception as e:
        print(f"Помилка: {e}")
        time.sleep(15)
