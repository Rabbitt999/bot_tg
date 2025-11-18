import telebot
import json
import random
import os
import re
import time
import requests
from telebot import types
from datetime import datetime, timedelta, timezone
from collections import defaultdict

# Конфігурація бота
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '7991439480:AAGR8KyC3RnBEVlYpP8-39ExcI-SSAhmPC0')
bot = telebot.TeleBot(TOKEN)

ADMIN_ID = 6974875043
CHANNEL_USERNAME = 'CodeMovie1'
MOVIES_FILE = 'movies.json'
USERS_FILE = 'users.json'
ADMINS_FILE = 'admins.json'
SAVED_MOVIES_FILE = 'saved_movies.json'

# TMDB API конфігурація
TMDB_API_KEY = os.getenv('TMDB_API_KEY',
                         '4819d57a475cf1ba39646b846f3d9d17')
TMDB_BASE_URL = 'https://api.themoviedb.org/3'
TMDB_IMAGE_BASE_URL = 'https://image.tmdb.org/t/p/w500'

# Глобальні змінні для зберігання стану
user_states = {}
temp_data = {}
genre_search_data = {}
user_movie_history = {}
genre_movie_history = {}
edit_movie_data = {}

# Система лімітів повідомлень
user_message_count = defaultdict(list)
LIMIT_CONFIG = {
    'random': {'limit': 10, 'seconds': 30, 'message': '🎲 Ви досягли ліміту випадкових фільмів: 10 за 30 секунд. Зачекайте ⏳'},
    'genre': {'limit': 3, 'seconds': 30, 'message': '🎬 Ви досягли ліміту пошуку за жанром: 3 рази за 30 секунд. Зачекайте ⏳'},
    'default': {'limit': 10, 'seconds': 30, 'message': '⚡ Ви досягли загального ліміту повідомлень: 10 за 30 секунд. Зачекайте ⏳'}
}

# Словник для перекладу країн з англійської на українську
COUNTRY_TRANSLATIONS = {
    'United States of America': 'США',
    'United States': 'США',
    'USA': 'США',
    'UK': 'Велика Британія',
    'United Kingdom': 'Велика Британія',
    'Canada': 'Канада',
    'Australia': 'Австралія',
    'Germany': 'Німеччина',
    'France': 'Франція',
    'Italy': 'Італія',
    'Spain': 'Іспанія',
    'Japan': 'Японія',
    'China': 'Китай',
    'South Korea': 'Південна Корея',
    'India': 'Індія',
    'Russia': 'Росія',
    'Ukraine': 'Україна',
    'Poland': 'Польща',
    'Czech Republic': 'Чехія',
    'Sweden': 'Швеція',
    'Norway': 'Норвегія',
    'Denmark': 'Данія',
    'Finland': 'Фінляндія',
    'Netherlands': 'Нідерланди',
    'Belgium': 'Бельгія',
    'Switzerland': 'Швейцарія',
    'Austria': 'Австрія',
    'Hungary': 'Угорщина',
    'Romania': 'Румунія',
    'Bulgaria': 'Болгарія',
    'Greece': 'Греція',
    'Turkey': 'Туреччина',
    'Brazil': 'Бразилія',
    'Mexico': 'Мексика',
    'Argentina': 'Аргентина',
    'Ireland': 'Ірландія',
    'Portugal': 'Португалія',
    'Israel': 'Ізраїль',
    'Egypt': 'Єгипет',
    'South Africa': 'ПАР',
    'New Zealand': 'Нова Зеландія',
    'Thailand': 'Таїланд',
    'Vietnam': "В'єтнам",
    'Philippines': 'Філіппіни',
    'Indonesia': 'Індонезія',
    'Malaysia': 'Малайзія',
    'Singapore': 'Сінгапур',
    'Hong Kong': 'Гонконг',
    'Taiwan': 'Тайвань'
}


def check_rate_limit(user_id, action_type='default'):
    """
    Перевіряє ліміт повідомлень для користувача
    Повертає True якщо ліміт не перевищено, False якщо перевищено
    """
    if user_id in load_admins():  # Адміни не мають обмежень
        return True
        
    now = time.time()
    config = LIMIT_CONFIG[action_type]
    
    # Очищаємо старі запити
    user_message_count[user_id] = [
        timestamp for timestamp in user_message_count[user_id] 
        if now - timestamp <= config['seconds']
    ]
    
    # Перевіряємо ліміт
    if len(user_message_count[user_id]) >= config['limit']:
        return False
    
    # Додаємо новий запит
    user_message_count[user_id].append(now)
    return True


def send_rate_limit_alert(chat_id, action_type='default'):
    """Надсилає alert-повідомлення про перевищення ліміту"""
    config = LIMIT_CONFIG[action_type]
    bot.send_message(chat_id, f"⚠️ {config['message']}")


def translate_country(country_name):
    """Перекладає назву країни з англійської на українську"""
    if not country_name:
        return "Невідомо"

    country_name = str(country_name).strip()

    # Перевіряємо чи є переклад у словнику
    if country_name in COUNTRY_TRANSLATIONS:
        return COUNTRY_TRANSLATIONS[country_name]

    # Якщо це список країн через кому, перекладаємо кожну
    if ',' in country_name:
        countries = [c.strip() for c in country_name.split(',')]
        translated_countries = []
        for country in countries:
            if country in COUNTRY_TRANSLATIONS:
                translated_countries.append(COUNTRY_TRANSLATIONS[country])
            else:
                translated_countries.append(country)
        return ', '.join(translated_countries)

    return country_name


def convert_age_rating(age_rating):
    """Конвертує американську вікову систему в числову"""
    if not age_rating:
        return "Не вказано"

    age_rating = str(age_rating).strip().upper()

    # Конвертація американської системи
    age_mapping = {
        'G': '0+',
        'PG': '6+',
        'PG-13': '12+',
        'R': '16+',
        'NC-17': '18+',
        'NR': 'Не вказано',
        'UNRATED': 'Не вказано'
    }

    # Перевірка чи це американський рейтинг
    if age_rating in age_mapping:
        return age_mapping[age_rating]

    # Обробка подвійних плюсів (16++, 13++ тощо)
    if re.match(r'^\d+\+{2,}$', age_rating):
        base_age = re.search(r'^\d+', age_rating).group()
        return f"{base_age}+"

    # Обробка звичайних числових рейтингів
    if re.match(r'^\d+\+$', age_rating):
        return age_rating

    # Якщо це інший формат, повертаємо оригінал
    return age_rating


def ensure_file_exists(filename, default):
    """Перевіряє існування файлу, створює якщо не існує"""
    if not os.path.exists(filename):
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(default, f, ensure_ascii=False, indent=2)


def load_movies():
    """Завантажує список фільмів з файлу"""
    ensure_file_exists(MOVIES_FILE, [])
    try:
        with open(MOVIES_FILE, 'r', encoding='utf-8') as f:
            movies = json.load(f)
            # Конвертуємо вікові рейтинги та країни при завантаженні
            for movie in movies:
                if isinstance(movie, dict):
                    if 'age_category' in movie:
                        movie['age_category'] = convert_age_rating(movie['age_category'])
                    if 'country' in movie:
                        movie['country'] = translate_country(movie['country'])
            return movies
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def save_movies(movies):
    """Зберігає список фільмів у файл"""
    with open(MOVIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(movies, f, ensure_ascii=False, indent=2)


def load_users():
    """Завантажує список користувачів у правильному форматі"""
    ensure_file_exists(USERS_FILE, {})
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                new_data = {str(user_id): datetime.now(timezone.utc).isoformat() for user_id in data}
                save_users(new_data)
                return new_data
            return data
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_users(users):
    """Зберігає список користувачів"""
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def load_saved_movies():
    """Завантажує збережені фільми користувачів"""
    ensure_file_exists(SAVED_MOVIES_FILE, {})
    try:
        with open(SAVED_MOVIES_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return {}


def save_saved_movies(saved_movies):
    """Зберігає збережені фільми користувачів"""
    with open(SAVED_MOVIES_FILE, 'w', encoding='utf-8') as f:
        json.dump(saved_movies, f, ensure_ascii=False, indent=2)


def get_user_saved_movies(user_id):
    """Отримує збережені фільми користувача"""
    saved_movies = load_saved_movies()
    user_id_str = str(user_id)
    if user_id_str not in saved_movies:
        saved_movies[user_id_str] = []
    return saved_movies[user_id_str]


def save_movie_for_user(user_id, movie_code):
    """Зберігає фільм для користувача"""
    saved_movies = load_saved_movies()
    user_id_str = str(user_id)

    if user_id_str not in saved_movies:
        saved_movies[user_id_str] = []

    # Перевіряємо, чи не перевищуємо ліміт у 6 фільмів
    if len(saved_movies[user_id_str]) >= 6:
        return False, "Досягнуто ліміт у 6 збережених фільмів. Видаліть деякі фільми, щоб додати нові."

    # Перевіряємо, чи фільм вже збережений
    if movie_code not in saved_movies[user_id_str]:
        saved_movies[user_id_str].append(movie_code)
        save_saved_movies(saved_movies)
        return True, "Фільм успішно збережено!"
    else:
        return False, "Цей фільм вже збережено."


def remove_movie_from_user(user_id, movie_code):
    """Видаляє фільм зі збережених для користувача"""
    saved_movies = load_saved_movies()
    user_id_str = str(user_id)

    if user_id_str in saved_movies and movie_code in saved_movies[user_id_str]:
        saved_movies[user_id_str].remove(movie_code)
        save_saved_movies(saved_movies)
        return True, "Фільм успішно видалено зі збережених!"
    else:
        return False, "Цей фільм не знайдено у ваших збережених."


def is_movie_saved_by_user(user_id, movie_code):
    """Перевіряє, чи збережений фільм користувачем"""
    saved_movies = load_saved_movies()
    user_id_str = str(user_id)
    return user_id_str in saved_movies and movie_code in saved_movies[user_id_str]


def log_user(user_id):
    """Логує активність користувача"""
    users = load_users()
    users[str(user_id)] = datetime.now(timezone.utc).isoformat()
    save_users(users)


def get_weekly_user_count():
    """Повертає кількість унікальних користувачів за останні 7 днів"""
    users = load_users()
    count = 0
    for timestamp in users.values():
        try:
            if datetime.fromisoformat(timestamp) >= datetime.now(timezone.utc) - timedelta(days=7):
                count += 1
        except Exception:
            continue
    return count


def check_subscription(user_id):
    """Перевіряє чи підписаний користувач на канал"""
    try:
        member = bot.get_chat_member(f"@{CHANNEL_USERNAME}", user_id)
        return member.status in ["member", "creator", "administrator"]
    except Exception as e:
        print(f"Помилка перевірки підписки: {e}")
        return False


def normalize_genre(text):
    """Нормалізує назву жанру для порівняння"""
    return re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9\s]', '', text.lower().strip())


def split_genres(genre_text):
    """Розділяє рядок з жанрами на список"""
    parts = re.split(r'[/,;]+', genre_text)
    return [normalize_genre(p) for p in parts if p.strip() != '']


def send_main_menu(chat_id):
    """Надсилає головне меню"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('🔍 Пошук фільму за кодом')
    markup.row('🎲 Випадковий фільм', '🎬 Пошук за жанром')
    markup.row('💾 Мої збережені фільми')
    if str(chat_id) == str(ADMIN_ID):
        markup.row('Адмін панель')
    markup.row('ℹ️ Інформація про бота')
    bot.send_message(chat_id, 'Оберіть опцію з меню:', reply_markup=markup)


def send_admin_panel(user_id):
    """Надсилає адмін панель"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('➕ Додати фільм 🎬', '➖ Видалити фільм 🎬')
    markup.row('🔍 Завантажити фільм за назвою')
    markup.row('📋 Список фільмів')
    markup.row('🗑️ Видалити всі фільми', '📊 Статистика')
    markup.row('✏️ Редагування фільмів')
    markup.row('➕ Додати адміна 👤', '➖ Видалити адміна 👤')
    markup.row('👑 Список адміністраторів')
    markup.row('◀️ Назад')
    bot.send_message(user_id, 'Адмін панель:', reply_markup=markup)


def send_edit_movie_panel(user_id, movie):
    """Надсилає панель редагування фільму"""
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('✏️ Назва', '⭐ Рейтинг')
    markup.row('⏱ Тривалість', '📅 Рік')
    markup.row('🚫 Вік', '🌍 Країна')
    markup.row('🎭 Жанр', '🖼 Постер')
    markup.row('🔢 Код фільму')
    markup.row('◀️ Назад до адмін панелі')
    
    caption = (f"🎬 **Редагування фільму:**\n\n"
               f"📝 Назва: {movie.get('title', 'Невідомо')}\n"
               f"⭐ Рейтинг: {movie.get('rating', 'Невідомо')}\n"
               f"⏱ Тривалість: {movie.get('duration', 'Невідомо')}\n"
               f"📅 Рік: {movie.get('year', 'Невідомо')}\n"
               f"🚫 Вік: {movie.get('age_category', 'Невідомо')}\n"
               f"🌍 Країна: {movie.get('country', 'Невідомо')}\n"
               f"🎭 Жанр: {movie.get('genre', 'Невідомо')}\n"
               f"🔢 Код: {movie.get('code', 'Невідомо')}")
    
    if 'poster' in movie and movie['poster']:
        try:
            bot.send_photo(user_id, movie['poster'], caption=caption, parse_mode='Markdown', reply_markup=markup)
        except:
            bot.send_message(user_id, caption + f"\n\n🖼 Постер: [є]", parse_mode='Markdown', reply_markup=markup)
    else:
        bot.send_message(user_id, caption + f"\n\n🖼 Постер: [відсутній]", parse_mode='Markdown', reply_markup=markup)


def format_movie(movie, show_save_button=True, user_id=None):
    """Форматує інформацію про фільм для відправки"""
    if not isinstance(movie, dict):
        return "Невірний формат фільму", None

    # Конвертуємо віковий рейтинг та країну перед відображенням
    age_rating = convert_age_rating(movie.get('age_category', 'Не вказано'))
    country = translate_country(movie.get('country', 'Невідомо'))

    caption = (f"🎬 {movie.get('title', 'Невідомо')}\n"
               f"⭐ IMDb: {movie.get('rating', 'Невідомо')}\n"
               f"⏱ Тривалість: {movie.get('duration', 'Невідомо')}\n"
               f"📅 Рік: {movie.get('year', 'Невідомо')}\n"
               f"🚫 Вік: {age_rating}\n"
               f"🌍 Країна: {country}\n"
               f"🎭 Жанр: {movie.get('genre', 'Невідомо')}\n"
               f"#Код: {movie.get('code', 'Невідомо')}")

    if 'megogo_link' in movie:
        caption += f"\n\n🔗 Дивитися на Megogo: {movie['megogo_link']}"

    # Створюємо кнопку збереження/видалення
    markup = None
    if show_save_button and user_id is not None:
        markup = types.InlineKeyboardMarkup()
        movie_code = movie.get('code', '')

        if is_movie_saved_by_user(user_id, movie_code):
            # Якщо фільм вже збережений, показуємо кнопку "Видалити"
            btn = types.InlineKeyboardButton('🗑️ Видалити зі збережених', callback_data=f'remove_{movie_code}')
            markup.add(btn)
        else:
            # Якщо фільм не збережений, показуємо кнопку "Зберегти"
            btn = types.InlineKeyboardButton('💾 Зберегти фільм', callback_data=f'save_{movie_code}')
            markup.add(btn)

    return caption, markup


def load_admins():
    """Завантажує список адміністраторів"""
    ensure_file_exists(ADMINS_FILE, [ADMIN_ID])
    try:
        with open(ADMINS_FILE, 'r', encoding='utf-8') as f:
            admins = json.load(f)
            return [int(admin) for admin in admins]
    except (json.JSONDecodeError, FileNotFoundError):
        return [ADMIN_ID]


def save_admins(admins):
    """Зберігає список адміністраторів"""
    with open(ADMINS_FILE, 'w', encoding='utf-8') as f:
        json.dump(admins, f, ensure_ascii=False, indent=2)


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
            caption, markup = format_movie(movie, show_save_button=True, user_id=user_id)
            if 'poster' in movie and movie['poster']:
                bot.send_photo(user_id, movie['poster'], caption=caption, parse_mode='Markdown', reply_markup=markup)
            else:
                bot.send_message(user_id, caption, parse_mode='Markdown', reply_markup=markup)
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


def get_existing_codes():
    """Отримує всі існуючі коди фільмів"""
    movies = load_movies()
    return {movie['code'] for movie in movies if isinstance(movie, dict) and 'code' in movie}


def get_existing_titles():
    """Отримує всі існуючі назви фільмів (нормалізовані)"""
    movies = load_movies()
    titles = set()
    for movie in movies:
        if isinstance(movie, dict) and 'title' in movie:
            normalized_title = re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9]', '', movie['title'].lower().strip())
            titles.add(normalized_title)
    return titles


def generate_unique_code():
    """Генерує унікальний 4-значний код"""
    existing_codes = get_existing_codes()

    while True:
        code = str(random.randint(1000, 9999))
        if code not in existing_codes:
            return code


def is_movie_exists(movie_title):
    """Перевіряє чи існує фільм з такою назвою"""
    existing_titles = get_existing_titles()
    normalized_title = re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9]', '', movie_title.lower().strip())
    return normalized_title in existing_titles


def delete_all_movies():
    """Видаляє всі фільми з бази"""
    save_movies([])
    global user_movie_history, genre_movie_history
    user_movie_history = {}
    genre_movie_history = {}


def search_tmdb_movies(query, year=None):
    """Пошук фільмів на TMDB"""
    try:
        url = f"{TMDB_BASE_URL}/search/movie"
        params = {
            'api_key': TMDB_API_KEY,
            'query': query,
            'language': 'uk-UA',
            'page': 1
        }
        if year:
            params['year'] = year

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json().get('results', [])
        else:
            print(f"TMDB API помилка: {response.status_code}")
            return []
    except Exception as e:
        print(f"Помилка пошуку на TMDB: {e}")
        return []


def get_tmdb_movie_details(movie_id):
    """Отримання детальної інформації про фільм з TMDB"""
    try:
        url = f"{TMDB_BASE_URL}/movie/{movie_id}"
        params = {
            'api_key': TMDB_API_KEY,
            'language': 'uk-UA',
            'append_to_response': 'credits'
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"TMDB API помилка деталей: {response.status_code}")
            return None
    except Exception as e:
        print(f"Помилка отримання деталей фільму: {e}")
        return None


def convert_runtime(minutes):
    """Конвертує хвилини у формат години:хвилины"""
    if not minutes:
        return "Невідомо"
    hours = minutes // 60
    mins = minutes % 60
    return f"{hours} год {mins} хв" if hours > 0 else f"{mins} хв"


def get_age_rating(movie_details):
    """Отримує віковий рейтинг фільму та конвертує його"""
    try:
        release_dates_url = f"{TMDB_BASE_URL}/movie/{movie_details['id']}/release_dates"
        params = {'api_key': TMDB_API_KEY}

        response = requests.get(release_dates_url, params=params, timeout=10)
        if response.status_code == 200:
            data = response.json()
            for country in data.get('results', []):
                if country['iso_3166_1'] in ['UA', 'US']:
                    for release in country.get('release_dates', []):
                        if release.get('certification'):
                            american_rating = release['certification']
                            # Конвертуємо американський рейтинг
                            return convert_age_rating(american_rating)
        return "16+"
    except Exception as e:
        print(f"Помилка отримання вікового рейтингу: {e}")
        return "16+"


def auto_add_movie_from_tmdb(movie_title, user_id, year=None):
    """Автоматично додає фільм з TMDB"""
    try:
        if is_movie_exists(movie_title):
            return False, f"Фільм '{movie_title}' вже існує в базі"

        search_results = search_tmdb_movies(movie_title, year)
        if not search_results:
            return False, "Фільм не знайдено на TMDB"

        movie_data = search_results[0]
        movie_details = get_tmdb_movie_details(movie_data['id'])

        if not movie_details:
            return False, "Не вдалося отримати деталі фільму"

        final_title = movie_details['title']
        if is_movie_exists(final_title):
            return False, f"Фільм '{final_title}' вже існує в базі"

        code = generate_unique_code()

        genres = [genre['name'] for genre in movie_details.get('genres', [])]
        genre_str = '/'.join(genres[:3])

        countries = [country['name'] for country in movie_details.get('production_countries', [])]
        # Перекладаємо назви країн на українську
        translated_countries = [translate_country(country) for country in countries]
        country_str = ', '.join(translated_countries[:2])

        rating = round(movie_details.get('vote_average', 0), 1)

        release_year = movie_details['release_date'][:4] if movie_details.get('release_date') else 'Невідомо'

        movie = {
            'code': code,
            'title': final_title,
            'rating': str(rating),
            'duration': convert_runtime(movie_details.get('runtime')),
            'year': release_year,
            'age_category': get_age_rating(movie_details),
            'country': country_str,
            'genre': genre_str,
            'poster': f"{TMDB_IMAGE_BASE_URL}{movie_details['poster_path']}" if movie_details.get(
                'poster_path') else '',
            'description': movie_details.get('overview', ''),
            'source': 'tmdb_auto'
        }

        existing_movies = load_movies()
        existing_movies.append(movie)
        save_movies(existing_movies)

        return True, movie

    except Exception as e:
        print(f"Помилка автоматичного додавання фільму: {e}")
        return False, f"Помилка: {str(e)}"


def process_multiple_movies(user_id, movie_titles_text):
    """Обробляє декілька назв фільмів одночасно"""
    # Розділяємо текст на окремі назви фільмів
    movie_titles = [title.strip() for title in movie_titles_text.split('\n') if title.strip()]

    if not movie_titles:
        bot.send_message(user_id, "❌ Не знайдено жодної назви фільму.")
        return

    total_movies = len(movie_titles)
    successful_movies = []
    failed_movies = []

    # Надсилаємо повідомлення про початок обробки
    progress_msg = bot.send_message(user_id, f"🔄 Починаю обробку {total_movies} фільмів...\n\n0/{total_movies} завершено")

    for index, movie_title in enumerate(movie_titles, 1):
        try:
            # Оновлюємо прогрес
            bot.edit_message_text(
                chat_id=user_id,
                message_id=progress_msg.message_id,
                text=f"🔄 Обробляю фільми...\n\n{index}/{total_movies} завершено\n\n⚙️ Зараз: {movie_title}"
            )

            # Додаємо фільм
            success, result = auto_add_movie_from_tmdb(movie_title, user_id)

            if success:
                if isinstance(result, dict):
                    successful_movies.append(result['title'])
                else:
                    successful_movies.append(movie_title)
            else:
                failed_movies.append(f"{movie_title} - {result}")

            # Невелика затримка між запитами до API
            time.sleep(1)

        except Exception as e:
            failed_movies.append(f"{movie_title} - Помилка: {str(e)}")
            continue

    # Формуємо фінальний звіт
    report = f"📊 **ЗВІТ ПРО ДОДАВАННЯ ФІЛЬМІВ**\n\n"
    report += f"✅ Успішно додано: {len(successful_movies)}\n"
    report += f"❌ Не вдалося додати: {len(failed_movies)}\n"
    report += f"📋 Всього оброблено: {total_movies}\n\n"

    if successful_movies:
        report += "**Успішно додані фільми:**\n"
        for i, title in enumerate(successful_movies[:10], 1):  # Показуємо перші 10
            report += f"{i}. {title}\n"
        if len(successful_movies) > 10:
            report += f"... та ще {len(successful_movies) - 10} фільмів\n"

    if failed_movies:
        report += "\n**Помилки при додаванні:**\n"
        for i, error in enumerate(failed_movies[:5], 1):  # Показуємо перші 5 помилок
            report += f"{i}. {error}\n"
        if len(failed_movies) > 5:
            report += f"... та ще {len(failed_movies) - 5} помилок\n"

    # Видаляємо повідомлення про прогрес і надсилаємо звіт
    bot.delete_message(user_id, progress_msg.message_id)
    bot.send_message(user_id, report, parse_mode='Markdown')

    # Показуємо кілька останніх успішно доданих фільмів
    if successful_movies:
        bot.send_message(user_id, "🎬 **Останні додані фільми:**")
        recent_movies = successful_movies[-3:]  # Останні 3 фільми
        for title in recent_movies:
            # Знаходимо фільм у базі для відображення інформації
            movies = load_movies()
            movie_info = next((m for m in movies if m.get('title') == title), None)
            if movie_info:
                try:
                    caption, markup = format_movie(movie_info, show_save_button=True, user_id=user_id)
                    if movie_info.get('poster'):
                        bot.send_photo(user_id, movie_info['poster'], caption=caption, parse_mode='Markdown', reply_markup=markup)
                    else:
                        bot.send_message(user_id, caption, parse_mode='Markdown', reply_markup=markup)
                    time.sleep(0.5)
                except Exception as e:
                    print(f"Помилка при відправці фільму: {e}")
                    bot.send_message(user_id, f"🎬 {title} (помилка відображення)")


def send_movies_list(user_id):
    """Надсилає список всіх фільмів з кодами"""
    movies = load_movies()

    if not movies:
        bot.send_message(user_id, "📭 База фільмів порожня.")
        return

    movies.sort(key=lambda x: x.get('title', '').lower())

    chunk_size = 50
    chunks = [movies[i:i + chunk_size] for i in range(0, len(movies), chunk_size)]

    for chunk_index, chunk in enumerate(chunks, 1):
        movie_list = "📋 **СПИСОК ФІЛЬМІВ**\n\n"

        for i, movie in enumerate(chunk, 1):
            title = movie.get('title', 'Невідома назва')
            code = movie.get('code', 'Невідомий код')
            year = movie.get('year', 'Невідомо')

            movie_list += f"{i + (chunk_index - 1) * chunk_size}. **{title}** ({year}) - `{code}`\n"

        if len(chunks) > 1:
            movie_list += f"\n*Частина {chunk_index} з {len(chunks)}*"

        try:
            bot.send_message(user_id, movie_list, parse_mode='Markdown')
            time.sleep(0.5)
        except Exception as e:
            print(f"Помилка при відправці списку фільмів: {e}")
            if "Message is too long" in str(e):
                smaller_chunks = [chunk[i:i + 20] for i in range(0, len(chunk), 20)]
                for small_chunk in smaller_chunks:
                    small_list = "📋 **СПИСОК ФІЛЬМІВ**\n\n"
                    for j, m in enumerate(small_chunk, 1):
                        title = m.get('title', 'Невідома назва')
                        code = m.get('code', 'Невідомий код')
                        year = m.get('year', 'Невідомо')
                        small_list += f"{j}. **{title}** ({year}) - `{code}`\n"
                    bot.send_message(user_id, small_list, parse_mode='Markdown')
                    time.sleep(0.3)

    total_movies = len(movies)
    unique_titles = len(get_existing_titles())
    bot.send_message(user_id, f"📊 **Всього фільмів у базі:** {total_movies}\n**Унікальних назв:** {unique_titles}")


def send_delete_confirmation(user_id):
    """Надсилає підтвердження видалення всіх фільмів"""
    movies_count = len(load_movies())

    if movies_count == 0:
        bot.send_message(user_id, "📭 База фільмів вже порожня.")
        return

    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row('✅ ТАК, видалити всі фільми')
    markup.row('❌ НІ, скасувати')

    message = (
        f"⚠️ **УВАГА! ВИДАЛЕННЯ ВСІХ ФІЛЬМІВ**\n\n"
        f"Ви збираєтесь видалити **всі {movies_count} фільмів** з бази даних!\n\n"
        f"🔴 **Ця дія незворотна!**\n"
        f"🔴 **Всі дані будуть втрачені!**\n\n"
        f"Підтвердіть видалення:"
    )

    bot.send_message(user_id, message, reply_markup=markup, parse_mode='Markdown')


def show_saved_movies(user_id):
    """Показує збережені фільми користувача"""
    saved_movie_codes = get_user_saved_movies(user_id)

    if not saved_movie_codes:
        bot.send_message(user_id, "📭 У вас немає збережених фільмів.")
        return

    movies = load_movies()
    saved_movies = [movie for movie in movies if movie.get('code') in saved_movie_codes]

    if not saved_movies:
        bot.send_message(user_id, "❌ Не вдалося знайти ваші збережені фільми. Можливо, вони були видалені з бази.")
        return

    bot.send_message(user_id, f"💾 Ваші збережені фільми ({len(saved_movies)}/6):")

    # Створюємо клавіатуру з назвами фільмів
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)

    for movie in saved_movies:
        title = movie.get('title', 'Невідома назва')
        code = movie.get('code', '')
        btn_text = f"🎬 {title} ({code})"
        markup.add(btn_text)

    markup.row('◀️ Назад до головного меню')
    bot.send_message(user_id, "Оберіть фільм для перегляду:", reply_markup=markup)


def handle_saved_movie_selection(user_id, message_text):
    """Обробляє вибір збереженого фільму"""
    # Виділяємо код фільму з тексту повідомлення
    match = re.search(r'\((\d{4})\)', message_text)
    if match:
        movie_code = match.group(1)
        movies = load_movies()
        movie = next((m for m in movies if m.get('code') == movie_code), None)

        if movie:
            caption, markup = format_movie(movie, show_save_button=True, user_id=user_id)
            try:
                if 'poster' in movie and movie['poster']:
                    bot.send_photo(user_id, movie['poster'], caption=caption, parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.send_message(user_id, caption, parse_mode='Markdown', reply_markup=markup)
            except Exception as e:
                print(f"Помилка при відправці фільму: {e}")
                bot.send_message(user_id, "❌ Помилка при відправці фільму.")
        else:
            bot.send_message(user_id, "❌ Фільм не знайдено в базі.")
    else:
        bot.send_message(user_id, "❌ Не вдалося розпізнати фільм.")


def find_movie_by_code_or_title(search_term):
    """Знаходить фільм за кодом або назвою"""
    movies = load_movies()
    
    # Пошук за кодом
    movie_by_code = next((m for m in movies if m.get('code') == search_term), None)
    if movie_by_code:
        return movie_by_code
    
    # Пошук за назвою (точне співпадіння)
    normalized_search = re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9]', '', search_term.lower().strip())
    for movie in movies:
        if isinstance(movie, dict) and 'title' in movie:
            normalized_title = re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9]', '', movie['title'].lower().strip())
            if normalized_title == normalized_search:
                return movie
    
    # Пошук за частиною назви
    for movie in movies:
        if isinstance(movie, dict) and 'title' in movie:
            normalized_title = re.sub(r'[^a-zA-Zа-яА-ЯіїІЇєЄґҐ0-9]', '', movie['title'].lower().strip())
            if normalized_search in normalized_title:
                return movie
    
    return None


def update_movie_in_database(updated_movie):
    """Оновлює фільм у базі даних"""
    movies = load_movies()
    for i, movie in enumerate(movies):
        if movie.get('code') == updated_movie.get('code'):
            movies[i] = updated_movie
            save_movies(movies)
            return True
    return False


@bot.callback_query_handler(func=lambda call: True)
def handle_callback_query(call):
    """Обробляє inline кнопки"""
    try:
        user_id = call.from_user.id
        data = call.data

        if data.startswith('save_'):
            movie_code = data.replace('save_', '')
            success, message = save_movie_for_user(user_id, movie_code)

            if success:
                # Оновлюємо повідомлення з кнопкою "Видалити"
                movies = load_movies()
                movie = next((m for m in movies if m.get('code') == movie_code), None)
                if movie:
                    caption, markup = format_movie(movie, show_save_button=True, user_id=user_id)
                    try:
                        if call.message.content_type == 'photo':
                            bot.edit_message_caption(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                caption=caption,
                                parse_mode='Markdown',
                                reply_markup=markup
                            )
                        else:
                            bot.edit_message_text(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=caption,
                                parse_mode='Markdown',
                                reply_markup=markup
                            )
                    except Exception as e:
                        print(f"Помилка оновлення повідомлення: {e}")

                bot.answer_callback_query(call.id, message)
            else:
                bot.answer_callback_query(call.id, message)

        elif data.startswith('remove_'):
            movie_code = data.replace('remove_', '')
            success, message = remove_movie_from_user(user_id, movie_code)

            if success:
                # Оновлюємо повідомлення з кнопкою "Зберегти"
                movies = load_movies()
                movie = next((m for m in movies if m.get('code') == movie_code), None)
                if movie:
                    caption, markup = format_movie(movie, show_save_button=True, user_id=user_id)
                    try:
                        if call.message.content_type == 'photo':
                            bot.edit_message_caption(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                caption=caption,
                                parse_mode='Markdown',
                                reply_markup=markup
                            )
                        else:
                            bot.edit_message_text(
                                chat_id=call.message.chat.id,
                                message_id=call.message.message_id,
                                text=caption,
                                parse_mode='Markdown',
                                reply_markup=markup
                            )
                    except Exception as e:
                        print(f"Помилка оновлення повідомлення: {e}")

                bot.answer_callback_query(call.id, message)
            else:
                bot.answer_callback_query(call.id, message)

    except Exception as e:
        print(f"Помилка в обробнику callback: {e}")
        bot.answer_callback_query(call.id, "❌ Сталася помилка")


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
        print(f"Помилка в команді /start: {e}")
        bot.send_message(message.chat.id, "Сталася помилка. Спробуйте ще раз.")


def handle_state(message):
    """Обробляє повідомлення в залежності від стану користувача"""
    user_id = message.from_user.id
    text = message.text.strip() if message.text else ""
    state = user_states.get(user_id)

    if state == 'awaiting_code':
        movies = load_movies()
        found = next((m for m in movies if isinstance(m, dict) and m['code'] == text), None)
        if found:
            try:
                caption, markup = format_movie(found, show_save_button=True, user_id=user_id)
                if 'poster' in found and found['poster']:
                    bot.send_photo(user_id, found['poster'], caption=caption, parse_mode='Markdown', reply_markup=markup)
                else:
                    bot.send_message(user_id, caption, parse_mode='Markdown', reply_markup=markup)
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
        if not text.isdigit() or len(text) != 4:
            bot.send_message(user_id, 'Код має бути 4-значним числом (наприклад: 1234). Спробуйте ще раз:')
            return

        existing_codes = get_existing_codes()
        if text in existing_codes:
            bot.send_message(user_id, 'Цей код вже використовується. Введіть інший 4-значний код:')
            return

        temp_data[user_id]['code'] = text
        user_states[user_id] = 'add_title'
        bot.send_message(user_id, 'Введіть назву фільму:')

    elif state == 'add_title':
        if is_movie_exists(text):
            bot.send_message(user_id, f'Фільм з назвою "{text}" вже існує. Введіть іншу назву:')
            return

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
        # Конвертуємо віковий рейтинг при додаванні
        converted_age = convert_age_rating(text)
        temp_data[user_id]['age_category'] = converted_age
        user_states[user_id] = 'add_country'
        bot.send_message(user_id, 'Введіть країну:')

    elif state == 'add_country':
        # Перекладаємо країну при додаванні
        translated_country = translate_country(text)
        temp_data[user_id]['country'] = translated_country
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
        bot.send_message(user_id, 'Надішліть постер фільму як фото (або крапку "." щоб пропустити):')

    elif state == 'add_poster':
        if message.photo:
            file_id = message.photo[-1].file_id
            temp_data[user_id]['poster'] = file_id
        elif text == '.':
            pass
        else:
            bot.send_message(user_id, 'Будь ласка, надішліть фото або крапку "." щоб пропустити.')
            return

        movie = temp_data.pop(user_id)
        movies = load_movies()
        movies.append(movie)
        save_movies(movies)
        bot.send_message(user_id, f'Фільм додано з кодом: {movie["code"]}!')
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
        except Exception:
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
        except Exception:
            bot.send_message(user_id, 'Некоректний ID.')
        user_states.pop(user_id)

    elif state == 'auto_load_by_title':
        # Обробляємо декілька фільмів одночасно
        process_multiple_movies(user_id, text)
        user_states.pop(user_id, None)
        send_admin_panel(user_id)

    elif state == 'confirm_delete_all':
        if text == '✅ ТАК, видалити всі фільми':
            movies_count = len(load_movies())
            delete_all_movies()
            bot.send_message(user_id, f"✅ Всі {movies_count} фільмів успішно видалено! База даних очищена.",
                             reply_markup=types.ReplyKeyboardRemove())
            send_admin_panel(user_id)
        elif text == '❌ НІ, скасувати':
            bot.send_message(user_id, "❌ Видалення скасовано.", reply_markup=types.ReplyKeyboardRemove())
            send_admin_panel(user_id)
        else:
            bot.send_message(user_id, "Будь ласка, оберіть один з варіантів:")
            return
        user_states.pop(user_id, None)

    # Стани для редагування фільмів
    elif state == 'edit_movie_search':
        movie = find_movie_by_code_or_title(text)
        if movie:
            edit_movie_data[user_id] = movie
            send_edit_movie_panel(user_id, movie)
            user_states[user_id] = 'edit_movie_select_field'
        else:
            bot.send_message(user_id, '❌ Фільм не знайдено. Спробуйте ще раз ввести код або назву:')
            return

    elif state == 'edit_movie_select_field':
        if text == '◀️ Назад до адмін панелі':
            user_states.pop(user_id, None)
            edit_movie_data.pop(user_id, None)
            send_admin_panel(user_id)
            return

        movie = edit_movie_data.get(user_id)
        if not movie:
            bot.send_message(user_id, '❌ Помилка: дані фільму не знайдені.')
            user_states.pop(user_id, None)
            send_admin_panel(user_id)
            return

        field_mapping = {
            '✏️ Назва': 'title',
            '⭐ Рейтинг': 'rating',
            '⏱ Тривалість': 'duration',
            '📅 Рік': 'year',
            '🚫 Вік': 'age_category',
            '🌍 Країна': 'country',
            '🎭 Жанр': 'genre',
            '🔢 Код фільму': 'code'
        }

        if text in field_mapping:
            field = field_mapping[text]
            user_states[user_id] = f'edit_movie_{field}'
            
            if field == 'code':
                bot.send_message(user_id, f'Введіть новий код фільму (поточний: {movie.get("code", "Невідомо")}):')
            else:
                current_value = movie.get(field, 'Не вказано')
                bot.send_message(user_id, f'Введіть нове значення для "{text}" (поточне: {current_value}):')
        
        elif text == '🖼 Постер':
            user_states[user_id] = 'edit_movie_poster'
            bot.send_message(user_id, 'Надішліть новий постер як фото (або крапку "." щоб видалити постер):')

    elif state.startswith('edit_movie_'):
        movie = edit_movie_data.get(user_id)
        if not movie:
            bot.send_message(user_id, '❌ Помилка: дані фільму не знайдені.')
            user_states.pop(user_id, None)
            send_admin_panel(user_id)
            return

        field = state.replace('edit_movie_', '')
        
        if field == 'poster':
            if message.photo:
                file_id = message.photo[-1].file_id
                movie['poster'] = file_id
                bot.send_message(user_id, '✅ Постер оновлено!')
            elif text == '.':
                movie['poster'] = ''
                bot.send_message(user_id, '✅ Постер видалено!')
            else:
                bot.send_message(user_id, 'Будь ласка, надішліть фото або крапку "." щоб видалити постер.')
                return
        elif field == 'code':
            if not text.isdigit() or len(text) != 4:
                bot.send_message(user_id, '❌ Код має бути 4-значним числом. Спробуйте ще раз:')
                return
            
            existing_codes = get_existing_codes()
            old_code = movie.get('code')
            if text != old_code and text in existing_codes:
                bot.send_message(user_id, '❌ Цей код вже використовується іншим фільмом. Спробуйте інший код:')
                return
            
            movie['code'] = text
            bot.send_message(user_id, '✅ Код фільму оновлено!')
        elif field == 'age_category':
            # Конвертуємо віковий рейтинг
            converted_age = convert_age_rating(text)
            movie[field] = converted_age
            bot.send_message(user_id, '✅ Вікову категорію оновлено!')
        elif field == 'country':
            # Перекладаємо країну
            translated_country = translate_country(text)
            movie[field] = translated_country
            bot.send_message(user_id, '✅ Країну оновлено!')
        else:
            movie[field] = text
            bot.send_message(user_id, f'✅ {field.capitalize()} оновлено!')

        # Оновлюємо фільм у базі даних
        if update_movie_in_database(movie):
            edit_movie_data[user_id] = movie  # Оновлюємо локальну копію
            send_edit_movie_panel(user_id, movie)
            user_states[user_id] = 'edit_movie_select_field'
        else:
            bot.send_message(user_id, '❌ Помилка при оновленні фільму в базі даних.')
            user_states.pop(user_id, None)
            send_admin_panel(user_id)


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
            if not check_rate_limit(user_id, 'default'):
                send_rate_limit_alert(user_id, 'default')
                return
            bot.send_message(user_id, 'Введіть 4-значний код фільму:')
            user_states[user_id] = 'awaiting_code'

        elif text == '🎲 Випадковий фільм':
            if not check_rate_limit(user_id, 'random'):
                send_rate_limit_alert(user_id, 'random')
                return
            movies = load_movies()
            if not movies:
                bot.send_message(user_id, 'База фільмів порожня.')
                return

            if user_id not in user_movie_history:
                user_movie_history[user_id] = []

            available_movies = [m for m in movies if
                                isinstance(m, dict) and m['code'] not in user_movie_history[user_id]]

            if not available_movies:
                available_movies = movies
                user_movie_history[user_id] = []

            if available_movies:
                movie = random.choice(available_movies)
                user_movie_history[user_id].append(movie['code'])

                try:
                    caption, markup = format_movie(movie, show_save_button=True, user_id=user_id)
                    if 'poster' in movie and movie['poster']:
                        bot.send_photo(user_id, movie['poster'], caption=caption, parse_mode='Markdown', reply_markup=markup)
                    else:
                        bot.send_message(user_id, caption, parse_mode='Markdown', reply_markup=markup)
                except Exception as e:
                    print(f"Помилка при відправці фільму: {e}")
                    bot.send_message(user_id, 'Сталася помилка при відправці фільму.')
            else:
                bot.send_message(user_id, 'Не вдалося знайти фільм.')

        elif text == '🎬 Пошук за жанром':
            if not check_rate_limit(user_id, 'genre'):
                send_rate_limit_alert(user_id, 'genre')
                return
            markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
            genres = ['"🎭"Драма', '"😂"Комедія', '"🔫"Бойовик', '"🔥"Екшн', '"🕵️‍♂️"Трилер', '"👻"Жахи', '"🛸"Пригоди',
                      '"🤖"Фантастика']
            for i in range(0, len(genres), 3):
                markup.row(*genres[i:i + 3])
            markup.row('◀️ Назад')
            bot.send_message(user_id, 'Оберіть жанр:', reply_markup=markup)
            user_states[user_id] = 'awaiting_genre'

        elif text == '💾 Мої збережені фільми':
            if not check_rate_limit(user_id, 'default'):
                send_rate_limit_alert(user_id, 'default')
                return
            show_saved_movies(user_id)

        elif text == '◀️ Назад':
            send_main_menu(user_id)
            user_states.pop(user_id, None)
            if user_id in genre_search_data:
                del genre_search_data[user_id]

        elif text == 'Адмін панель' and user_id in load_admins():
            send_admin_panel(user_id)

        elif text == '📊 Статистика' and user_id in load_admins():
            count = get_weekly_user_count()
            movies_count = len(load_movies())
            existing_codes = get_existing_codes()
            unique_titles = len(get_existing_titles())
            all_movies = load_movies()
            high_rated_count = sum(1 for m in all_movies if float(m.get('rating', 0)) >= 7.0)
            very_high_rated_count = sum(1 for m in all_movies if float(m.get('rating', 0)) >= 8.0)

            # Статистика збережених фільмів
            saved_movies_data = load_saved_movies()
            total_saved_movies = sum(len(movies) for movies in saved_movies_data.values())
            users_with_saved_movies = sum(1 for movies in saved_movies_data.values() if movies)

            bot.send_message(user_id,
                             f'📊 Статистика:\n\n'
                             f'Користувачів за останні 7 днів: {count}\n'
                             f'Фільмів у базі: {movies_count}\n'
                             f'Унікальних назв: {unique_titles}\n'
                             f'Використано кодів: {len(existing_codes)}\n\n'
                             f'⭐ Фільмів з рейтингом 7.0+: {high_rated_count}\n'
                             f'⭐ Фільмів з рейтингом 8.0+: {very_high_rated_count}\n\n'
                             f'💾 Збережених фільмів: {total_saved_movies}\n'
                             f'Користувачів зі збереженими: {users_with_saved_movies}')

        elif text == '📋 Список фільмів' and user_id in load_admins():
            send_movies_list(user_id)

        elif text == '➕ Додати фільм 🎬' and user_id in load_admins():
            temp_data[user_id] = {}
            user_states[user_id] = 'add_code'
            bot.send_message(user_id, 'Введіть 4-значний код фільму (наприклад: 1234):')

        elif text == '➖ Видалити фільм 🎬' and user_id in load_admins():
            user_states[user_id] = 'delete_code'
            bot.send_message(user_id, 'Введіть 4-значний код фільму для видалення:')

        elif text == '🔍 Завантажити фільм за назвою' and user_id in load_admins():
            user_states[user_id] = 'auto_load_by_title'
            instruction = (
                "🎬 **ДОДАВАННЯ ДЕКІЛЬКОХ ФІЛЬМІВ**\n\n"
                "Введіть назви фільмів, кожну з нового рядка:\n\n"
                "**Приклад:**\n"
                "Інтерстеллар\n"
                "Втеча з Шоушенка\n"
                "1+1\n"
                "Хрещений батько\n"
                "Початок\n\n"
                "Бот почне обробку всіх фільмів по черзі та надішле звіт."
            )
            bot.send_message(user_id, instruction, parse_mode='Markdown')

        elif text == '🗑️ Видалити всі фільми' and user_id in load_admins():
            user_states[user_id] = 'confirm_delete_all'
            send_delete_confirmation(user_id)

        elif text == '✏️ Редагування фільмів' and user_id in load_admins():
            user_states[user_id] = 'edit_movie_search'
            bot.send_message(user_id, 'Введіть код або назву фільму для редагування:')

        elif text == '➕ Додати адміна 👤' and user_id == ADMIN_ID:
            user_states[user_id] = 'add_admin'
            bot.send_message(user_id, 'Введіть ID користувача, якого хочете додати адміністратором:')

        elif text == '➖ Видалити адміна 👤' и user_id == ADMIN_ID:
            user_states[user_id] = 'remove_admin'
            bot.send_message(user_id, 'Введіть ID користувача, якого хочете видалити з адміністраторів:')

        elif text == '👑 Список адміністраторів' and user_id in load_admins():
            admins = load_admins()
            if admins:
                admin_list = '\n'.join(str(a) for a in admins)
                bot.send_message(user_id, f'Список адміністраторів:\n{admin_list}')
            else:
                bot.send_message(user_id, 'Список адміністраторів порожній.')

        elif text == 'ℹ️ Інформація про бота':
            if not check_rate_limit(user_id, 'default'):
                send_rate_limit_alert(user_id, 'default')
                return
            info = (
                "ℹ️ Про бота\n\n"
                "🔍 Пошук фільму за кодом — введи 4-значний код, щоб дізнатися назву фільму.\n"
                "🎲 Випадковий фільм — бот випадково надішле тобі фільм із бази.\n"
                "🎬 Пошук за жанром — обери жанр, щоб переглянути добірку фільмів.\n"
                "💾 Мої збережені фільми — переглядай фільми, які ти зберіг (до 6 фільмів).\n"
                "🎯 Коди фільмів: 4-значні числа (наприклад: 1234, 5678, 9999)\n\n"
                "💡 Під кожним фільмом є кнопка для збереження/видалення зі збережених."
            )
            bot.send_message(user_id, info, parse_mode='Markdown')

        elif text == '🎬 Показати ще фільми цього жанру':
            if not check_rate_limit(user_id, 'genre'):
                send_rate_limit_alert(user_id, 'genre')
                return
            if user_id in genre_search_data:
                show_more_genre_movies(user_id, genre_search_data[user_id])
            else:
                bot.send_message(user_id, 'Жанр не вибрано. Оберіть жанр знову.')
                send_main_menu(user_id)

        elif text == '🎭 Обрати інший жанр':
            if not check_rate_limit(user_id, 'genre'):
                send_rate_limit_alert(user_id, 'genre')
                return
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

        elif text == '◀️ Назад до адмін панелі' and user_id in load_admins():
            send_admin_panel(user_id)

        elif text.startswith('🎬 '):
            # Обробка вибору збереженого фільму
            if not check_rate_limit(user_id, 'default'):
                send_rate_limit_alert(user_id, 'default')
                return
            handle_saved_movie_selection(user_id, text)

        else:
            if not check_rate_limit(user_id, 'default'):
                send_rate_limit_alert(user_id, 'default')
                return
            bot.send_message(user_id, 'Невідома команда. Оберіть дію з меню.')
    except Exception as e:
        print(f"Помилка в обробнику повідомлень: {e}")
        bot.send_message(message.chat.id, "Сталася помилка. Спробуйте ще раз.")


if __name__ == '__main__':
    print("Бот запущений...")
    if TMDB_API_KEY == 'ваш_tmdb_api_ключ':
        print("⚠️  УВАГА: Встановіть свій TMDB API ключ у змінну середовища TMDB_API_KEY")
    else:
        print("✅ TMDB API ключ налаштовано")

    while True:
        try:
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Помилка: {e}")
            time.sleep(15)
