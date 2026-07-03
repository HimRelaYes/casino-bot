import telebot
from telebot import types
import sqlite3
import random
import time
from datetime import datetime, timedelta
import os
import sys
from flask import Flask
import threading
import json
import base64
import requests

TOKEN = '8217975863:AAEScN82IIMAq2hi7YtI_K_TfXqBd0NXlMk'  # ВСТАВЬ СВОЙ ТОКЕН!
bot = telebot.TeleBot(TOKEN)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ FOLDBOT РАБОТАЕТ!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask, daemon=True).start()

# --- НАСТРОЙКИ GITHUB БЭКАПА ---
GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')  # Теперь из переменных окружения!
REPO_NAME = 'HimRelaYes/casino-bot'  # Замени на свой!
FILE_PATH = 'casino.db'
DB_PATH = 'casino.db'

# --- СОХРАНЕНИЕ В GITHUB ---
def backup_to_github():
    try:
        if not os.path.exists(DB_PATH):
            return
        with open(DB_PATH, 'rb') as f:
            content = base64.b64encode(f.read()).decode()
        url = f'https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}'
        headers = {'Authorization': f'token {GITHUB_TOKEN}', 'Accept': 'application/vnd.github.v3+json'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            sha = response.json()['sha']
            data = {'message': f'Автобэкап БД {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}', 'content': content, 'sha': sha}
        else:
            data = {'message': 'Создание БД при первом запуске', 'content': content}
        requests.put(url, headers=headers, json=data)
        print('✅ БД сохранена в GitHub')
    except Exception as e:
        print(f'❌ Ошибка бэкапа: {e}')

def restore_from_github():
    try:
        url = f'https://api.github.com/repos/{REPO_NAME}/contents/{FILE_PATH}'
        headers = {'Authorization': f'token {GITHUB_TOKEN}'}
        response = requests.get(url, headers=headers)
        if response.status_code == 200:
            content = base64.b64decode(response.json()['content'])
            with open(DB_PATH, 'wb') as f:
                f.write(content)
            print('✅ БД восстановлена из GitHub')
            return True
    except Exception as e:
        print(f'⚠️ Ошибка восстановления: {e}')
        return False

def auto_backup():
    while True:
        time.sleep(300)
        backup_to_github()

# --- БАЗА ДАННЫХ ---
restore_from_github()
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# --- ДОБАВЛЯЕМ КОЛОНКИ ДЛЯ УРОВНЕЙ ---
cursor.execute('''
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    name TEXT,
    balance INTEGER DEFAULT 1000,
    work TEXT DEFAULT NULL,
    family TEXT DEFAULT NULL,
    daily_bonus TEXT DEFAULT NULL,
    penalty_until TEXT DEFAULT NULL,
    ban_until TEXT DEFAULT NULL,
    total_earned INTEGER DEFAULT 0,
    last_work TEXT DEFAULT NULL,
    subscribed INTEGER DEFAULT 0,
    sub_check_time TEXT DEFAULT NULL,
    xp INTEGER DEFAULT 0,
    level INTEGER DEFAULT 1
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS families (
    name TEXT PRIMARY KEY,
    owner_id INTEGER,
    balance INTEGER DEFAULT 0
)
''')

cursor.execute('''
CREATE TABLE IF NOT EXISTS family_members (
    user_id INTEGER,
    family_name TEXT,
    FOREIGN KEY(user_id) REFERENCES users(user_id),
    FOREIGN KEY(family_name) REFERENCES families(name)
)
''')
conn.commit()

threading.Thread(target=auto_backup, daemon=True).start()

# --- СИСТЕМА УРОВНЕЙ ---
LEVELS = {
    1: 0,
    2: 100,
    3: 250,
    4: 500,
    5: 1000,
    6: 2000,
    7: 3500,
    8: 5500,
    9: 8000,
    10: 12000,
    11: 17000,
    12: 23000,
    13: 30000,
    14: 40000,
    15: 50000,
    16: 65000,
    17: 80000,
    18: 100000,
    19: 125000,
    20: 150000,
}

LEVEL_NAMES = {
    1: '🟤 Новичок',
    2: '⚪ Странник',
    3: '🟢 Игрок',
    4: '🔵 Опытный',
    5: '🟣 Профи',
    6: '🟡 Мастер',
    7: '🟠 Ветеран',
    8: '🔴 Легенда',
    9: '💎 Элита',
    10: '👑 Император',
}

def get_level(xp):
    level = 1
    for lvl, xp_needed in LEVELS.items():
        if xp >= xp_needed:
            level = lvl
    return level

def get_level_name(level):
    return LEVEL_NAMES.get(level, f'⭐ Уровень {level}')

def add_xp(user_id, amount):
    cursor.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if not res:
        return
    xp, current_level = res
    new_xp = xp + amount
    new_level = get_level(new_xp)
    
    cursor.execute('UPDATE users SET xp = ?, level = ? WHERE user_id = ?', (new_xp, new_level, user_id))
    conn.commit()
    backup_to_github()
    
    if new_level > current_level:
        return new_level
    return None

def get_level_info(user_id):
    cursor.execute('SELECT xp, level FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if not res:
        return None
    xp, level = res
    next_xp = LEVELS.get(level + 1, None)
    return {
        'xp': xp,
        'level': level,
        'next_xp': next_xp,
        'progress': round((xp - LEVELS[level]) / (next_xp - LEVELS[level]) * 100) if next_xp else 100
    }

# --- ФУНКЦИИ ДЛЯ НАГРАДЫ ЗА УРОВНИ ---
def level_reward(level):
    rewards = {
        2: 100,
        3: 200,
        4: 300,
        5: 500,
        6: 700,
        7: 1000,
        8: 1500,
        9: 2000,
        10: 3000,
    }
    return rewards.get(level, level * 100)

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def register_user(user_id, name):
    cursor.execute('INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()
    backup_to_github()

def get_balance(user_id):
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    return res[0] if res else 0

def update_balance(user_id, amount):
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()
    # Добавляем опыт за заработанные деньги (кроме проигрышей)
    if amount > 0:
        xp_gain = amount // 10  # 1 XP за каждые 10 монет
        new_level = add_xp(user_id, xp_gain)
        if new_level:
            bonus = level_reward(new_level)
            update_balance(user_id, bonus)
            bot.send_message(user_id, f'🎉 *ПОВЫШЕНИЕ УРОВНЯ!*\nТы достиг {new_level} уровня!\n💰 Бонус: +{bonus}₽', parse_mode='Markdown')
    backup_to_github()

def add_penalty(user_id, days):
    until = datetime.now() + timedelta(days=days)
    cursor.execute('UPDATE users SET penalty_until = ? WHERE user_id = ?', (until.strftime('%Y-%m-%d %H:%M:%S'), user_id))
    conn.commit()
    backup_to_github()

def is_penalized(user_id):
    cursor.execute('SELECT penalty_until FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0]:
        until = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
        return datetime.now() < until
    return False

def can_work(user_id, cooldown_hours):
    cursor.execute('SELECT last_work FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0]:
        last = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
        return datetime.now() - last >= timedelta(hours=cooldown_hours)
    return True

def set_last_work(user_id):
    cursor.execute('UPDATE users SET last_work = ? WHERE user_id = ?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
    conn.commit()
    backup_to_github()

def can_bonus(user_id):
    cursor.execute('SELECT daily_bonus FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    if res and res[0]:
        last = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
        return datetime.now() - last >= timedelta(days=1)
    return True

def set_bonus(user_id):
    cursor.execute('UPDATE users SET daily_bonus = ? WHERE user_id = ?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
    conn.commit()
    backup_to_github()

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start', 'старт'])
def start(message):
    user_id = message.from_user.id
    register_user(user_id, message.from_user.first_name)
    bot.send_message(message.chat.id, 
        "🎰 *Добро пожаловать в FoldBot!*\n\n"
        "👋 Я бот-казино с семьями, работой и дуэлями!\n"
        "📋 Введи /help или /помощь чтобы увидеть все команды.\n\n"
        "🔥 *КВЕСТ:* Подпишись на https://t.me/rengadeup и получи 1000₽!\n"
        "Используй /подписка после подписки.",
        parse_mode='Markdown')

@bot.message_handler(commands=['help', 'помощь'])
def help_command(message):
    help_text = """
🎰 *FOLDBOT — ПОМОЩЬ*

━━━━━━━━━━━━━━━━━━━━

👤 *ПРОФИЛЬ И ДЕНЬГИ*
├ /profile или /профиль — твой профиль
├ /profile [ID] или /профиль [ID] — профиль игрока
├ /balance или /баланс — узнать баланс
├ /pay [сумма] или /платёж [сумма] — перевести (ответь на сообщение)
└ /top или /топ — топ 10 игроков по деньгам

📈 *УРОВНИ И ОПЫТ*
├ /level или /уровень — твой уровень и прогресс
└ /top — топ игроков

💼 *РАБОТА*
├ /developer или /разработчик — 💻 Разработчик (100-200₽, КД 30 мин)
├ /courier или /курьер — 📦 Курьер (150-300₽, КД 1 час)
├ /seller или /продавец — 🛒 Продавец (200-400₽, КД 2 часа)
└ /welder или /сварщик — 👨‍🏭 Сварщик (300-500₽, КД 4 часа)

🎰 *КАЗИНО*
├ /slots [ставка] или /слоты [ставка] — 🎰 Слоты
├ /dice [ставка] или /кубики [ставка] — 🎲 Кубики
├ /wheel [ставка] или /колесо [ставка] — 🎡 Колесо фортуны
└ /roulette [ставка] или /рулетка [ставка] — 🔴 Рулетка

🏠 *СЕМЬЯ*
├ /семьясоздать [название] — создать семью
├ /семьявступить [название] — вступить в семью
├ /семьявыйти — выйти из семьи
├ /семьясписок — список всех семей
└ /семьябаланс — баланс семьи

⚔️ *ДУЭЛИ*
└ /duel [сумма] или /дуэль [сумма] — вызвать на дуэль (ответь на сообщение)

🎁 *БОНУСЫ И КВЕСТЫ*
├ /bonus или /бонус — ежедневный бонус (100-500₽)
└ /подписка — проверить подписку на канал (награда 1000₽)

ℹ️ *ИНФО*
└ /help или /помощь — это меню

━━━━━━━━━━━━━━━━━━━━
💡 *Совет:* Работай, копи деньги и становись миллионером! 🚀
"""
    bot.send_message(message.chat.id, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['profile', 'профиль'])
def profile(message):
    args = message.text.split()
    user_id = message.from_user.id
    if len(args) > 1:
        try:
            target_id = int(args[1])
        except:
            bot.send_message(message.chat.id, '❌ Используй: `/profile [ID]` или `/профиль [ID]`', parse_mode='Markdown')
            return
    else:
        target_id = user_id
    user = get_user(target_id)
    if not user:
        bot.send_message(message.chat.id, '❌ Пользователь не найден!')
        return
    balance = user[2]
    family = user[4] if user[4] else 'Нет'
    penalty = '⚠️ Да' if is_penalized(target_id) else '✅ Нет'
    subscribed = '✅ Да' if user[11] == 1 else '❌ Нет'
    level_info = get_level_info(target_id)
    level_name = get_level_name(level_info['level'])
    
    text = f"""
👤 *Профиль игрока*

━━━━━━━━━━━━━━━━━━━━
💰 *Баланс:* {balance}₽
📈 *Уровень:* {level_name} ({level_info['level']})
📊 *Опыт:* {level_info['xp']}
🏠 *Семья:* {family}
⚠️ *Штраф:* {penalty}
📢 *Подписка:* {subscribed}
━━━━━━━━━━━━━━━━━━━━
"""
    if level_info['next_xp']:
        bar = '▓' * (level_info['progress'] // 10) + '░' * (10 - level_info['progress'] // 10)
        text += f"\n📊 *Прогресс:* [{bar}] {level_info['progress']}%"
        text += f"\n🎯 До следующего уровня: {level_info['next_xp'] - level_info['xp']} XP"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['level', 'уровень'])
def level_command(message):
    user_id = message.from_user.id
    level_info = get_level_info(user_id)
    if not level_info:
        bot.send_message(message.chat.id, '❌ Ты не зарегистрирован! Напиши /start')
        return
    level_name = get_level_name(level_info['level'])
    text = f"""
📈 *Твой уровень*

━━━━━━━━━━━━━━━━━━━━
🏅 *Уровень:* {level_name} ({level_info['level']})
⭐ *Опыт:* {level_info['xp']}
"""
    if level_info['next_xp']:
        bar = '▓' * (level_info['progress'] // 10) + '░' * (10 - level_info['progress'] // 10)
        text += f"\n📊 *Прогресс:* [{bar}] {level_info['progress']}%"
        text += f"\n🎯 До следующего уровня: {level_info['next_xp'] - level_info['xp']} XP"
    else:
        text += "\n👑 *МАКСИМАЛЬНЫЙ УРОВЕНЬ!*"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['balance', 'баланс'])
def balance(message):
    bal = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f'💰 Твой баланс: *{bal}₽*', parse_mode='Markdown')

@bot.message_handler(commands=['top', 'топ'])
def top_players(message):
    # Топ по деньгам
    cursor.execute('SELECT user_id, name, balance, level FROM users ORDER BY balance DESC LIMIT 10')
    tops = cursor.fetchall()
    if not tops:
        bot.send_message(message.chat.id, '📭 Пока нет игроков!')
        return
    
    text = "🏆 *ТОП 10 ПО ДЕНЬГАМ*\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, (user_id, name, balance, level) in enumerate(tops, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} *{name}* — {balance}₽ (Ур. {level})\n"
    
    # Топ по уровню
    cursor.execute('SELECT user_id, name, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 5')
    tops_level = cursor.fetchall()
    if tops_level:
        text += "\n📈 *ТОП 5 ПО УРОВНЮ*\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, (user_id, name, level, xp) in enumerate(tops_level, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} *{name}* — Ур. {level} ({xp} XP)\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

def work_command(message, job_name, min_pay, max_pay, cooldown_hours):
    user_id = message.from_user.id
    if is_penalized(user_id):
        bonus = random.randint(5, 15)
        bot.send_message(message.chat.id, f'⚠️ Ты под штрафом! Зарплата уменьшена на {bonus}%')
        min_pay = int(min_pay * (1 - bonus/100))
        max_pay = int(max_pay * (1 - bonus/100))
    if not can_work(user_id, cooldown_hours):
        cursor.execute('SELECT last_work FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        if res and res[0]:
            last = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            remaining = int((timedelta(hours=cooldown_hours) - (datetime.now() - last)).seconds // 60)
            bot.send_message(message.chat.id, f'⏳ Отдыхай! Следующая работа через {remaining} мин.')
        return
    salary = random.randint(min_pay, max_pay)
    update_balance(user_id, salary)
    set_last_work(user_id)
    bot.send_message(message.chat.id, f'💼 *{job_name}*\n✅ Ты заработал *{salary}₽*!\n⏳ Следующая работа через {cooldown_hours} ч.', parse_mode='Markdown')

@bot.message_handler(commands=['developer', 'разработчик'])
def developer(message):
    work_command(message, '💻 Разработчик', 100, 200, 0.5)

@bot.message_handler(commands=['courier', 'курьер'])
def courier(message):
    work_command(message, '📦 Курьер', 150, 300, 1)

@bot.message_handler(commands=['seller', 'продавец'])
def seller(message):
    work_command(message, '🛒 Продавец', 200, 400, 2)

@bot.message_handler(commands=['welder', 'сварщик'])
def welder(message):
    work_command(message, '👨‍🏭 Сварщик', 300, 500, 4)

@bot.message_handler(commands=['bonus', 'бонус'])
def bonus(message):
    user_id = message.from_user.id
    if not can_bonus(user_id):
        cursor.execute('SELECT daily_bonus FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        if res and res[0]:
            last = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            remaining = int((timedelta(days=1) - (datetime.now() - last)).seconds // 3600)
            bot.send_message(message.chat.id, f'⏳ Бонус уже получен! Следующий через {remaining} ч.')
        return
    amount = random.randint(100, 500)
    update_balance(user_id, amount)
    set_bonus(user_id)
    bot.send_message(message.chat.id, f'🎁 Ты получил ежедневный бонус: *{amount}₽*', parse_mode='Markdown')

@bot.message_handler(commands=['подписка'])
def check_subscription(message):
    user_id = message.from_user.id
    CHANNEL_ID = '@rengadeup'
    try:
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        if member.status in ['member', 'creator', 'administrator']:
            cursor.execute('SELECT subscribed FROM users WHERE user_id = ?', (user_id,))
            res = cursor.fetchone()
            if res and res[0] == 1:
                bot.send_message(message.chat.id, '❌ Ты уже получил награду за подписку!')
            else:
                update_balance(user_id, 1000)
                cursor.execute('UPDATE users SET subscribed = 1 WHERE user_id = ?', (user_id,))
                cursor.execute('UPDATE users SET sub_check_time = ? WHERE user_id = ?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
                conn.commit()
                backup_to_github()
                bot.send_message(message.chat.id, '✅ Ты подписан на канал!\n🎁 Получил 1000₽ в подарок!')
        else:
            cursor.execute('SELECT subscribed FROM users WHERE user_id = ?', (user_id,))
            res = cursor.fetchone()
            if res and res[0] == 1:
                update_balance(user_id, -3000)
                cursor.execute('UPDATE users SET subscribed = 0 WHERE user_id = ?', (user_id,))
                conn.commit()
                backup_to_github()
                bot.send_message(message.chat.id, '❌ Ты отписался от канала!\n💰 Штраф: -3000₽')
            else:
                bot.send_message(message.chat.id, '❌ Ты не подписан на канал!\n📢 Подпишись: https://t.me/rengadeup')
    except Exception as e:
        bot.send_message(message.chat.id, f'❌ Ошибка проверки подписки. Убедись, что канал существует.\n📢 Ссылка: https://t.me/rengadeup')

# --- КАЗИНО ---
@bot.message_handler(commands=['slots', 'слоты'])
def slots(message):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/slots [ставка]` или `/слоты [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.send_message(message.chat.id, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.send_message(message.chat.id, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.send_message(message.chat.id, '❌ Недостаточно средств!')
        return
    emojis = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    s1, s2, s3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
    result = f'{s1} | {s2} | {s3}'
    if s1 == s2 == s3:
        win = bet * 5
        update_balance(user_id, win)
        bot.send_message(message.chat.id, f'🎰 {result}\n🎉 ДЖЕКПОТ! +{win}₽')
    elif s1 == s2 or s2 == s3 or s1 == s3:
        win = bet * 2
        update_balance(user_id, win)
        bot.send_message(message.chat.id, f'🎰 {result}\n✅ Выигрыш! +{win}₽')
    else:
        update_balance(user_id, -bet)
        bot.send_message(message.chat.id, f'🎰 {result}\n❌ Проигрыш -{bet}₽')

@bot.message_handler(commands=['dice', 'кубики'])
def dice(message):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/dice [ставка]` или `/кубики [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.send_message(message.chat.id, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.send_message(message.chat.id, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.send_message(message.chat.id, '❌ Недостаточно средств!')
        return
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    if user_roll > bot_roll:
        update_balance(user_id, bet)
        bot.send_message(message.chat.id, f'🎲 Ты: {user_roll} | Бот: {bot_roll}\n✅ Ты выиграл {bet}₽!')
    elif user_roll < bot_roll:
        update_balance(user_id, -bet)
        bot.send_message(message.chat.id, f'🎲 Ты: {user_roll} | Бот: {bot_roll}\n❌ Ты проиграл {bet}₽!')
    else:
        bot.send_message(message.chat.id, f'🎲 Ты: {user_roll} | Бот: {bot_roll}\n🤝 Ничья!')

@bot.message_handler(commands=['wheel', 'колесо'])
def wheel(message):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/wheel [ставка]` или `/колесо [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.send_message(message.chat.id, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.send_message(message.chat.id, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.send_message(message.chat.id, '❌ Недостаточно средств!')
        return
    sectors = ['🍒 x2', '🍋 x3', '🍊 x1', '💎 x5', '❌ 0']
    win_sector = random.choice(sectors)
    if 'x' in win_sector:
        multiplier = int(win_sector.split('x')[1])
        win = bet * multiplier
        update_balance(user_id, win)
        bot.send_message(message.chat.id, f'🎡 Колесо показало: {win_sector}\n✅ Выигрыш: +{win}₽')
    else:
        update_balance(user_id, -bet)
        bot.send_message(message.chat.id, f'🎡 Колесо показало: {win_sector}\n❌ Проигрыш: -{bet}₽')

@bot.message_handler(commands=['roulette', 'рулетка'])
def roulette(message):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/roulette [ставка]` или `/рулетка [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.send_message(message.chat.id, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.send_message(message.chat.id, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.send_message(message.chat.id, '❌ Недостаточно средств!')
        return
    number = random.randint(0, 36)
    if number != 0 and number % 2 == 0:
        win = bet * 2
        update_balance(user_id, win)
        bot.send_message(message.chat.id, f'🔴 Выпало *{number}* (КРАСНОЕ)!\n✅ Ты выиграл *{win}₽*!', parse_mode='Markdown')
    elif number != 0 and number % 2 != 0:
        update_balance(user_id, -bet)
        bot.send_message(message.chat.id, f'⚫ Выпало *{number}* (ЧЁРНОЕ)!\n❌ Ты проиграл *{bet}₽*!', parse_mode='Markdown')
    else:
        update_balance(user_id, -bet)
        bot.send_message(message.chat.id, f'🟢 Выпал *0* (ЗЕЛЁНЫЙ)!\n❌ Ты проиграл *{bet}₽*!', parse_mode='Markdown')

# --- ОСТАЛЬНЫЕ КОМАНДЫ (pay, duel, семья) ---
# [ВСТАВЬ ИХ СЮДА ИЗ ПРЕДЫДУЩЕГО КОДА - ОНИ НЕ ИЗМЕНИЛИСЬ]

# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    while True:
        try:
            print('✅ FOLDBOT ЗАПУЩЕН НА RENDER!')
            print('📋 Бот работает в чатах!')
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f'❌ Ошибка: {e}')
            print('🔄 Перезапуск через 5 секунд...')
            time.sleep(5)
        finally:
            backup_to_github()
