import telebot
import json
import random
import os
import re
import time
import sys
from telebot import types
from datetime import datetime, timedelta, timezone

# Конфігурація бота через змінні середовища
TOKEN = os.getenv('7991439480:AAGR8KyC3RnBEVlYpP8-39ExcI-SSAhmPC0')
if not TOKEN:
    print("Помилка: Не вказано TELEGRAM_BOT_TOKEN")
    sys.exit(1)

bot = telebot.TeleBot(TOKEN)

# Шляхи до файлів
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MOVIES_FILE = os.path.join(BASE_DIR, 'movies.json')
USERS_FILE = os.path.join(BASE_DIR, 'users.json')
ADMINS_FILE = os.path.join(BASE_DIR, 'admins.json')

# Конфігурація змінних середовища
try:
    ADMIN_ID = int(os.getenv('ADMIN_ID', '6974875043'))
except ValueError:
    print("Помилка: ADMIN_ID має бути числом")
    sys.exit(1)

CHANNEL_USERNAME = os.getenv('CHANNEL_USERNAME', 'CodeMovie1')

# Глобальні змінні
user_states = {}
temp_data = {}
genre_search_data = {}
user_movie_history = {}
genre_movie_history = {}

# Функції для роботи з файлами
def ensure_file_exists(filename, default):
    """Створює файл, якщо він не існує"""
    try:
        if not os.path.exists(filename):
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(default, f, ensure_ascii=False, indent=2)
            os.chmod(filename, 0o666)
        return True
    except Exception as e:
        print(f"Помилка створення файлу {filename}: {e}")
        return False

def load_movies():
    """Завантажує список фільмів"""
    ensure_file_exists(MOVIES_FILE, [])
    try:
        with open(MOVIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Помилка завантаження фільмів: {e}")
        return []

def save_movies(movies):
    """Зберігає список фільмів"""
    try:
        with open(MOVIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(movies, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Помилка збереження фільмів: {e}")

def load_users():
    """Завантажує список користувачів"""
    ensure_file_exists(USERS_FILE, {})
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                new_data = {str(user_id): datetime.now(timezone.utc).isoformat() for user_id in data}
                save_users(new_data)
                return new_data
            return data
    except Exception as e:
        print(f"Помилка завантаження користувачів: {e}")
        return {}

def save_users(users):
    """Зберігає список користувачів"""
    try:
        with open(USERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Помилка збереження користувачів: {e}")

def load_admins():
    """Завантажує список адмінів"""
    ensure_file_exists(ADMINS_FILE, [ADMIN_ID])
    try:
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            admins = json.load(f)
            return [int(admin) for admin in admins]
    except Exception as e:
        print(f"Помилка завантаження адмінів: {e}")
        return [ADMIN_ID]

def save_admins(admins):
    """Зберігає список адмінів"""
    try:
        with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
            json.dump(admins, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Помилка збереження адмінів: {e}")

# Допоміжні функції
def normalize_genre(text):
    """Нормалізує назву жанру"""
    return re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9\s]', '', text.lower().strip())

def split_genres(genre_text):
    """Розділяє рядок з жанрами"""
    parts = re.split(r'[/,;]+', genre_text)
    return [normalize_genre(p) for p in parts if p.strip() != '']

def log_user(user_id):
    """Логує активність користувача"""
    users = load_users()
    users[str(user_id)] = datetime.now(timezone.utc).isoformat()
    save_users(users)

def get_weekly_user_count():
    """Повертає кількість активних користувачів"""
    users = load_users()
    count = 0
    for timestamp in users.values():
        try:
            if datetime.fromisoformat(timestamp) >= datetime.now(timezone.utc) - timedelta(days=7):
                count += 1
        except:
            continue
    return count

def check_subscription(user_id):
    """Перевіряє підписку на канал"""
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "creator", "administrator"]
    except Exception as e:
        print(f"Помилка перевірки підписки: {e}")
        return False

def format_movie(movie):
    """Форматує інформацію про фільм"""
    if not isinstance(movie, dict):
        return "Невірний формат фільму"

    caption = (f"🎬 {movie.get('title', 'Невідомо')}\n"
               f"⭐ IMDb: {movie.get('rating', 'Невідомо')}\n"
               f"⏱ Тривалість: {movie.get('duration', 'Невідомо')}\n"
               f"📅 Рік: {movie.get('year', 'Невідомо')}\n"
               f"🔞 Вік: {movie.get('age_category', 'Не вказано')}\n"
               f"🌍 Країна: {movie.get('country', 'Невідомо')}\n"
               f"🎭 Жанр: {movie.get('genre', 'Невідомо')}\n"
               f"#Код: {movie.get('code', 'Невідомо')}")

    if 'megogo_link' in movie:
        caption += f"\n\n🔗 Дивитися на Megogo: {movie['megogo_link']}"

    return caption

# Меню та кнопки
def send_main_menu(chat_id):
    """Надсилає головне меню"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🔍 Пошук фільму за кодом')
    markup.row('🎲 Випадковий фільм', '🎬 Пошук за жанром')
    if str(chat_id) in [str(admin) for admin in load_admins()]:
        markup.row('Адмін панель')
    markup.row('ℹ️ Інформація про бота')
    bot.send_message(chat_id, 'Оберіть опцію з меню:', reply_markup=markup)

def send_admin_panel(user_id):
    """Надсилає адмін панель"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('➕ Додати фільм', '➖ Видалити фільм')
    markup.row('➕ Додати адміна', '➖ Видалити адміна')
    markup.row('👑 Список адміністраторів')
    markup.row('📊 Статистика')
    markup.row('◀️ Назад')
    bot.send_message(user_id, 'Адмін панель:', reply_markup=markup)

def show_more_genre_movies(user_id, genre_input):
    """Показує фільми за жанром"""
    if genre_input not in genre_movie_history:
        genre_movie_history[genre_input] = []

    movies = load_movies()
    found_movies = []

    for m in movies:
        if isinstance(m, dict):
            movie_genres = m.get('genre', '')
            genres_list = split_genres(movie_genres)
            if genre_input in genres_list:
                found_movies.append(m)

    if not found_movies:
        bot.send_message(user_id, 'Фільми цього жанру не знайдені.')
        send_main_menu(user_id)
        return

    random.shuffle(found_movies)
    available_movies = [m for m in found_movies if m['code'] not in genre_movie_history[genre_input]]

    if len(available_movies) < 3:
        shown_in_history = [m for m in found_movies if m['code'] in genre_movie_history[genre_input]]
        if shown_in_history:
            num_needed = min(3 - len(available_movies), len(shown_in_history))
            additional_movies = random.sample(shown_in_history, num_needed)
            available_movies.extend(additional_movies)

    movies_to_show = available_movies[:3]

    for movie in movies_to_show:
        try:
            if 'poster' in movie and movie['poster']:
                bot.send_photo(user_id, movie['poster'], caption=format_movie(movie), parse_mode='Markdown')
            else:
                bot.send_message(user_id, format_movie(movie), parse_mode='Markdown')
            time.sleep(1)

            if movie['code'] not in genre_movie_history[genre_input]:
                genre_movie_history[genre_input].append(movie['code'])
        except Exception as e:
            print(f"Помилка при відправці фільму: {e}")
            continue

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🎬 Показати ще фільми цього жанру')
    markup.row('🎭 Обрати інший жанр')
    markup.row('◀️ Назад до головного меню')
    bot.send_message(user_id, 'Оберіть інший жанр або цей самий:', reply_markup=markup)

# Обробники команд
@bot.message_handler(commands=['start'])
def start(message):
    """Обробник команди /start"""
    try:
        user_id = message.from_user.id
        if not check_subscription(user_id):
            markup = types.InlineKeyboardMarkup()
            btn = types.InlineKeyboardButton('Підписатися', url=f'https://t.me/{CHANNEL_USERNAME}')
            markup.add(btn)
            bot.send_message(message.chat.id, 'Щоб користуватися ботом, підпишіться на канал:', reply_markup=markup)
            return
        
        log_user(user_id)
        send_main_menu(message.chat.id)
    except Exception as e:
        print(f"Помилка в /start: {e}")
        bot.send_message(message.chat.id, "⚠️ Сталася помилка. Спробуйте ще раз.")

def handle_state(message):
    """Обробляє повідомлення в залежності від стану"""
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    state = user_states.get(user_id)

    if state == 'awaiting_code':
        movies = load_movies()
        found = next((m for m in movies if isinstance(m, dict) and m['code'] == text), None)
        if found:
            try:
                if 'poster' in found and found['poster']:
                    bot.send_photo(user_id, found['poster'], caption=format_movie(found), parse_mode='Markdown')
                else:
                    bot.send_message(user_id, format_movie(found), parse_mode='Markdown')
            except Exception as e:
                print(f"Помилка при відправці фільму: {e}")
                bot.send_message(user_id, 'Сталася помилка при відправці фільму.')
        else:
            bot.send_message(user_id, 'Фільм не знайдено.')
        user_states.pop(user_id, None)
        send_main_menu(user_id)

    elif state == 'awaiting_genre':
        genre_input = normalize_genre(text)
        genre_search_data[user_id] = genre_input
        show_more_genre_movies(user_id, genre_input)
        user_states.pop(user_id, None)

    elif state == 'add_code':
        temp_data[user_id] = {'code': text}
        user_states[user_id] = 'add_title'
        bot.send_message(user_id, 'Введіть назву фільму:')

    elif state == 'add_title':
        temp_data[user_id]['title'] = text
        user_states[user_id] = 'add_rating'
        bot.send_message(user_id, 'Введіть рейтинг IMDb:')

    elif state == 'add_rating':
        temp_data[user_id]['rating'] = text
        user_states[user_id] = 'add_duration'
        bot.send_message(user_id, 'Введіть тривалість:')

    elif state == 'add_duration':
        temp_data[user_id]['duration'] = text
        user_states[user_id] = 'add_year'
        bot.send_message(user_id, 'Введіть рік:')

    elif state == 'add_year':
        temp_data[user_id]['year'] = text
        user_states[user_id] = 'add_age_category'
        bot.send_message(user_id, 'Введіть вікову категорію (наприклад, 16+):')

    elif state == 'add_age_category':
        temp_data[user_id]['age_category'] = text
        user_states[user_id] = 'add_country'
        bot.send_message(user_id, 'Введіть країну:')

    elif state == 'add_country':
        temp_data[user_id]['country'] = text
        user_states[user_id] = 'add_genre'
        bot.send_message(user_id, 'Введіть жанр (наприклад, Екшн/Пригоди):')

    elif state == 'add_genre':
        temp_data[user_id]['genre'] = text
        user_states[user_id] = 'add_megogo_link'
        bot.send_message(user_id, 'Введіть партнерське посилання на Megogo (або крапку "." щоб пропустити):')

    elif state == 'add_megogo_link':
        if text != '.':
            temp_data[user_id]['megogo_link'] = text
        user_states[user_id] = 'add_poster'
        bot.send_message(user_id, 'Надішліть постер фільму як фото:')

    elif state == 'add_poster' and message.photo:
        file_id = message.photo[-1].file_id
        temp_data[user_id]['poster'] = file_id
        movie = temp_data.pop(user_id)
        movies = load_movies()
        movies.append(movie)
        save_movies(movies)
        bot.send_message(user_id, 'Фільм додано!')
        user_states.pop(user_id)

    elif state == 'delete_code':
        code = text
        movies = load_movies()
        movies = [m for m in movies if isinstance(m, dict) and m['code'] != code]
        save_movies(movies)
        bot.send_message(user_id, 'Фільм видалено (якщо існував).')
        user_states.pop(user_id)

    elif state == 'add_admin':
        try:
            new_admin_id = int(text)
            admins = load_admins()
            if new_admin_id not in admins:
                admins.append(new_admin_id)
                save_admins(admins)
                bot.send_message(user_id, f'Користувач {new_admin_id} доданий як адміністратор.')
            else:
                bot.send_message(user_id, 'Цей користувач вже є адміністратором.')
        except:
            bot.send_message(user_id, 'Некоректний ID.')
        user_states.pop(user_id)

    elif state == 'remove_admin':
        try:
            rem_admin_id = int(text)
            admins = load_admins()
            if rem_admin_id in admins:
                admins.remove(rem_admin_id)
                save_admins(admins)
                bot.send_message(user_id, f'Користувач {rem_admin_id} видалений з адміністраторів.')
            else:
                bot.send_message(user_id, 'Цього користувача немає серед адміністраторів.')
        except:
            bot.send_message(user_id, 'Некоректний ID.')
        user_states.pop(user_id)

@bot.message_handler(func=lambda message: True, content_types=['text', 'photo'])
def handle_message(message):
    """Головний обробник повідомлень"""
    try:
        user_id = message.from_user.id
        text = message.text.strip() if message.text else ""

        if not check_subscription(user_id):
            bot.send_message(user_id, 'Спочатку підпишіться на канал.')
            return

        if user_id in user_states:
            handle_state(message)
            return

        if text == '🔍 Пошук фільму за кодом':
            bot.send_message(user_id, 'Введіть код фільму:')
            user_states[user_id] = 'awaiting_code'

        elif text == '🎲 Випадковий фільм':
            movies = load_movies()
            if not movies:
                bot.send_message(user_id, 'База фільмів порожня.')
                return

            if user_id not in user_movie_history:
                user_movie_history[user_id] = []

            available_movies = [m for m in movies if isinstance(m, dict) and m['code'] not in user_movie_history[user_id]]

            if not available_movies:
                available_movies = movies
                user_movie_history[user_id] = []

            if available_movies:
                movie = random.choice(available_movies)
                user_movie_history[user_id].append(movie['code'])

                try:
                    if 'poster' in movie and movie['poster']:
                        bot.send_photo(user_id, movie['poster'], caption=format_movie(movie), parse_mode='Markdown')
                    else:
                        bot.send_message(user_id, format_movie(movie), parse_mode='Markdown')
                except Exception as e:
                    print(f"Помилка при відправці фільму: {e}")
                    bot.send_message(user_id, 'Сталася помилка при відправці фільму.')
            else:
                bot.send_message(user_id, 'Не вдалося знайти фільм.')

        elif text == '🎬 Пошук за жанром':
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            genres = ['"🎭"Драма', '"😂"Комедія', '"🔫"Бойовик', '"🔥"Екшн', '"🕵️‍♂️"Трилер', '"👻"Жахи', '"🛸"Пригоди',
                     '"🤖"Фантастика']
            for i in range(0, len(genres), 3):
                markup.row(*genres[i:i + 3])
            markup.row('◀️ Назад')
            bot.send_message(user_id, 'Оберіть жанр:', reply_markup=markup)
            user_states[user_id] = 'awaiting_genre'

        elif text == '◀️ Назад':
            send_main_menu(user_id)
            user_states.pop(user_id, None)
            if user_id in genre_search_data:
                del genre_search_data[user_id]

        elif text == 'Адмін панель' and user_id in [admin for admin in load_admins()]:
            send_admin_panel(user_id)

        elif text == '📊 Статистика' and user_id in [admin for admin in load_admins()]:
            count = get_weekly_user_count()
            bot.send_message(user_id, f'Користувачів за останні 7 днів: {count}')

        elif text == '➕ Додати фільм' and user_id in [admin for admin in load_admins()]:
            temp_data[user_id] = {}
            user_states[user_id] = 'add_code'
            bot.send_message(user_id, 'Введіть код фільму:')

        elif text == '➖ Видалити фільм' and user_id in [admin for admin in load_admins()]:
            user_states[user_id] = 'delete_code'
            bot.send_message(user_id, 'Введіть код фільму для видалення:')

        elif text == '➕ Додати адміна' and user_id == ADMIN_ID:
            user_states[user_id] = 'add_admin'
            bot.send_message(user_id, 'Введіть ID користувача, якого хочете додати адміністратором:')

        elif text == '➖ Видалити адміна' and user_id == ADMIN_ID:
            user_states[user_id] = 'remove_admin'
            bot.send_message(user_id, 'Введіть ID користувача, якого хочете видалити з адміністраторів:')

        elif text == '👑 Список адміністраторів' and user_id in [admin for admin in load_admins()]:
            admins = load_admins()
            if admins:
                admin_list = '\n'.join(str(a) for a in admins)
                bot.send_message(user_id, f'Список адміністраторів:\n{admin_list}')
            else:
                bot.send_message(user_id, 'Список адміністраторів порожній.')

        elif text == 'ℹ️ Інформація про бота':
            info = (
                "ℹ️ Про бота\n\n"
                "🔍 Пошук фільму за кодом — введи код із TikTok, щоб дізнатися назву фільму.\n"
                "🎲 Випадковий фільм — бот випадково надішле тобі фільм із бази.\n"
                "🎬 Пошук за жанром — обери жанр, щоб переглянути добірку фільмів."
            )
            bot.send_message(user_id, info, parse_mode='Markdown')

        elif text == '🎬 Показати ще фільми цього жанру':
            if user_id in genre_search_data:
                show_more_genre_movies(user_id, genre_search_data[user_id])
            else:
                bot.send_message(user_id, 'Жанр не вибрано. Оберіть жанр знову.')
                send_main_menu(user_id)

        elif text == '🎭 Обрати інший жанр':
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            genres = ['"🎭"Драма', '"😂"Комедія', '"🔫"Бойовик', '"🔥"Екшн', '"🕵️‍♂️"Трилер', '"👻"Жахи', '"🛸"Пригоди',
                     '"🤖"Фантастика']
            for i in range(0, len(genres), 3):
                markup.row(*genres[i:i + 3])
            markup.row('◀️ Назад')
            bot.send_message(user_id, 'Оберіть жанр:', reply_markup=markup)
            user_states[user_id] = 'awaiting_genre'

        elif text == '◀️ Назад до головного меню':
            send_main_menu(user_id)
            user_states.pop(user_id, None)
            if user_id in genre_search_data:
                del genre_search_data[user_id]

        else:
            bot.send_message(user_id, 'Невідома команда. Оберіть дію з меню.')
    except Exception as e:
        print(f"Помилка в обробнику повідомлень: {e}")
        bot.send_message(message.chat.id, "⚠️ Сталася помилка. Спробуйте ще раз.")

# Запуск бота
if __name__ == '__main__':
    print("🤖 Бот запускається...")
    print(f"🛠 Версія Python: {sys.version}")
    print(f"🔑 Адміністратор
