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
GITHUB_TOKEN = os.environ.get('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')
REPO_NAME = 'himzyReal/casino-bot'
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
    1: 0, 2: 100, 3: 250, 4: 500, 5: 1000,
    6: 2000, 7: 3500, 8: 5500, 9: 8000, 10: 12000,
    11: 17000, 12: 23000, 13: 30000, 14: 40000, 15: 50000,
    16: 65000, 17: 80000, 18: 100000, 19: 125000, 20: 150000,
}

LEVEL_NAMES = {
    1: '🟤 Новичок', 2: '⚪ Странник', 3: '🟢 Игрок', 4: '🔵 Опытный',
    5: '🟣 Профи', 6: '🟡 Мастер', 7: '🟠 Ветеран', 8: '🔴 Легенда',
    9: '💎 Элита', 10: '👑 Император',
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

def level_reward(level):
    rewards = {2: 100, 3: 200, 4: 300, 5: 500, 6: 700, 7: 1000, 8: 1500, 9: 2000, 10: 3000}
    return rewards.get(level, level * 100)

# --- АДМИН-КОМАНДЫ ---
ADMIN_IDS = [1879227483]  # ВСТАВЬ СВОИ ID (можно несколько)

@bot.message_handler(commands=['админ_баланс'])
def admin_balance(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, '❌ У тебя нет прав!')
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, '❌ Используй: `/админ_баланс [ID] [сумма]`')
        return
    try:
        user_id = int(args[1])
        amount = int(args[2])
        update_balance(user_id, amount)
        bot.reply_to(message, f'✅ Баланс пользователя {user_id} изменён на {amount}₽')
    except:
        bot.reply_to(message, '❌ Неверный формат!')

@bot.message_handler(commands=['админ_бонус'])
def admin_bonus(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, '❌ У тебя нет прав!')
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/админ_бонус [ID]`')
        return
    try:
        user_id = int(args[1])
        amount = random.randint(500, 2000)
        update_balance(user_id, amount)
        bot.reply_to(message, f'✅ Бонус {amount}₽ выдан пользователю {user_id}')
    except:
        bot.reply_to(message, '❌ Неверный ID!')

@bot.message_handler(commands=['админ_штраф'])
def admin_penalty(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, '❌ У тебя нет прав!')
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/админ_штраф [ID] [дни]`')
        return
    try:
        user_id = int(args[1])
        days = int(args[2]) if len(args) > 2 else 2
        add_penalty(user_id, days)
        bot.reply_to(message, f'✅ Штраф на {days} дней выдан пользователю {user_id}')
    except:
        bot.reply_to(message, '❌ Неверный формат!')

@bot.message_handler(commands=['админ_очистить'])
def admin_clear(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, '❌ У тебя нет прав!')
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/админ_очистить [ID]`')
        return
    try:
        user_id = int(args[1])
        cursor.execute('DELETE FROM users WHERE user_id = ?', (user_id,))
        conn.commit()
        backup_to_github()
        bot.reply_to(message, f'✅ Пользователь {user_id} удалён из базы!')
    except:
        bot.reply_to(message, '❌ Неверный ID!')

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
    if amount > 0:
        xp_gain = amount // 10
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
    bot.reply_to(message, 
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

🎰 *КАЗИНО* (шанс на победу)
├ /slots [ставка] или /слоты [ставка] — 🎰 Слоты (шанс 40%)
├ /dice [ставка] или /кубики [ставка] — 🎲 Кубики (шанс 50%)
├ /wheel [ставка] или /колесо [ставка] — 🎡 Колесо (шанс 60%)
└ /roulette [ставка] или /рулетка [ставка] — 🔴 Рулетка (шанс 48%)

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
    bot.reply_to(message, help_text, parse_mode='Markdown')

@bot.message_handler(commands=['profile', 'профиль'])
def profile(message):
    args = message.text.split()
    user_id = message.from_user.id
    if len(args) > 1:
        try:
            target_id = int(args[1])
        except:
            bot.reply_to(message, '❌ Используй: `/profile [ID]` или `/профиль [ID]`', parse_mode='Markdown')
            return
    else:
        target_id = user_id
    user = get_user(target_id)
    if not user:
        bot.reply_to(message, '❌ Пользователь не найден!')
        return
    balance = user[2]
    family = user[4] if user[4] else 'Нет'
    penalty = '⚠️ Да' if is_penalized(target_id) else '✅ Нет'
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
━━━━━━━━━━━━━━━━━━━━
"""
    if level_info['next_xp']:
        bar = '▓' * (level_info['progress'] // 10) + '░' * (10 - level_info['progress'] // 10)
        text += f"\n📊 *Прогресс:* [{bar}] {level_info['progress']}%"
        text += f"\n🎯 До следующего уровня: {level_info['next_xp'] - level_info['xp']} XP"
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['level', 'уровень'])
def level_command(message):
    user_id = message.from_user.id
    level_info = get_level_info(user_id)
    if not level_info:
        bot.reply_to(message, '❌ Ты не зарегистрирован! Напиши /start')
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
    
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['balance', 'баланс'])
def balance(message):
    bal = get_balance(message.from_user.id)
    bot.reply_to(message, f'💰 Твой баланс: *{bal}₽*', parse_mode='Markdown')

@bot.message_handler(commands=['top', 'топ'])
def top_players(message):
    cursor.execute('SELECT user_id, name, balance, level FROM users ORDER BY balance DESC LIMIT 10')
    tops = cursor.fetchall()
    if not tops:
        bot.reply_to(message, '📭 Пока нет игроков!')
        return
    text = "🏆 *ТОП 10 ПО ДЕНЬГАМ*\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, (user_id, name, balance, level) in enumerate(tops, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} *{name}* — {balance}₽ (Ур. {level})\n"
    cursor.execute('SELECT user_id, name, level, xp FROM users ORDER BY level DESC, xp DESC LIMIT 5')
    tops_level = cursor.fetchall()
    if tops_level:
        text += "\n📈 *ТОП 5 ПО УРОВНЮ*\n━━━━━━━━━━━━━━━━━━━━\n"
        for i, (user_id, name, level, xp) in enumerate(tops_level, 1):
            medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
            text += f"{medal} *{name}* — Ур. {level} ({xp} XP)\n"
    bot.reply_to(message, text, parse_mode='Markdown')

def work_command(message, job_name, min_pay, max_pay, cooldown_hours):
    user_id = message.from_user.id
    if is_penalized(user_id):
        bonus = random.randint(5, 15)
        bot.reply_to(message, f'⚠️ Ты под штрафом! Зарплата уменьшена на {bonus}%')
        min_pay = int(min_pay * (1 - bonus/100))
        max_pay = int(max_pay * (1 - bonus/100))
    if not can_work(user_id, cooldown_hours):
        cursor.execute('SELECT last_work FROM users WHERE user_id = ?', (user_id,))
        res = cursor.fetchone()
        if res and res[0]:
            last = datetime.strptime(res[0], '%Y-%m-%d %H:%M:%S')
            remaining = int((timedelta(hours=cooldown_hours) - (datetime.now() - last)).seconds // 60)
            bot.reply_to(message, f'⏳ Отдыхай! Следующая работа через {remaining} мин.')
        return
    salary = random.randint(min_pay, max_pay)
    update_balance(user_id, salary)
    set_last_work(user_id)
    bot.reply_to(message, f'💼 *{job_name}*\n✅ Ты заработал *{salary}₽*!\n⏳ Следующая работа через {cooldown_hours} ч.', parse_mode='Markdown')

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
            bot.reply_to(message, f'⏳ Бонус уже получен! Следующий через {remaining} ч.')
        return
    amount = random.randint(100, 500)
    update_balance(user_id, amount)
    set_bonus(user_id)
    bot.reply_to(message, f'🎁 Ты получил ежедневный бонус: *{amount}₽*', parse_mode='Markdown')

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
                bot.reply_to(message, '❌ Ты уже получил награду за подписку!')
            else:
                update_balance(user_id, 1000)
                cursor.execute('UPDATE users SET subscribed = 1 WHERE user_id = ?', (user_id,))
                cursor.execute('UPDATE users SET sub_check_time = ? WHERE user_id = ?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
                conn.commit()
                backup_to_github()
                bot.reply_to(message, '✅ Ты подписан на канал!\n🎁 Получил 1000₽ в подарок!')
        else:
            cursor.execute('SELECT subscribed FROM users WHERE user_id = ?', (user_id,))
            res = cursor.fetchone()
            if res and res[0] == 1:
                update_balance(user_id, -3000)
                cursor.execute('UPDATE users SET subscribed = 0 WHERE user_id = ?', (user_id,))
                conn.commit()
                backup_to_github()
                bot.reply_to(message, '❌ Ты отписался от канала!\n💰 Штраф: -3000₽')
            else:
                bot.reply_to(message, '❌ Ты не подписан на канал!\n📢 Подпишись: https://t.me/rengadeup')
    except Exception as e:
        bot.reply_to(message, f'❌ Ошибка проверки подписки. Убедись, что канал существует.\n📢 Ссылка: https://t.me/rengadeup')

# --- КАЗИНО ---
@bot.message_handler(commands=['slots', 'слоты'])
def slots(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/slots [ставка]` или `/слоты [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.reply_to(message, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.reply_to(message, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.reply_to(message, '❌ Недостаточно средств!')
        return
    emojis = ['🍒', '🍋', '🍊', '🍇', '💎', '7️⃣']
    s1, s2, s3 = random.choice(emojis), random.choice(emojis), random.choice(emojis)
    result = f'{s1} | {s2} | {s3}'
    if random.random() < 0.4:  # 40% шанс выигрыша
        if s1 == s2 == s3:
            win = bet * 5
            update_balance(user_id, win)
            bot.reply_to(message, f'🎰 {result}\n🎉 ДЖЕКПОТ! +{win}₽ (шанс 40%)')
        elif s1 == s2 or s2 == s3 or s1 == s3:
            win = bet * 2
            update_balance(user_id, win)
            bot.reply_to(message, f'🎰 {result}\n✅ Выигрыш! +{win}₽ (шанс 40%)')
        else:
            update_balance(user_id, -bet)
            bot.reply_to(message, f'🎰 {result}\n❌ Проигрыш -{bet}₽ (шанс 40%)')
    else:
        update_balance(user_id, -bet)
        bot.reply_to(message, f'🎰 {result}\n❌ Проигрыш -{bet}₽ (шанс 40%)')

@bot.message_handler(commands=['dice', 'кубики'])
def dice(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/dice [ставка]` или `/кубики [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.reply_to(message, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.reply_to(message, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.reply_to(message, '❌ Недостаточно средств!')
        return
    user_roll = random.randint(1, 6)
    bot_roll = random.randint(1, 6)
    if user_roll > bot_roll:
        update_balance(user_id, bet)
        bot.reply_to(message, f'🎲 Ты: {user_roll} | Бот: {bot_roll}\n✅ Ты выиграл {bet}₽! (шанс 50%)')
    elif user_roll < bot_roll:
        update_balance(user_id, -bet)
        bot.reply_to(message, f'🎲 Ты: {user_roll} | Бот: {bot_roll}\n❌ Ты проиграл {bet}₽! (шанс 50%)')
    else:
        bot.reply_to(message, f'🎲 Ты: {user_roll} | Бот: {bot_roll}\n🤝 Ничья! (шанс 50%)')

@bot.message_handler(commands=['wheel', 'колесо'])
def wheel(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/wheel [ставка]` или `/колесо [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.reply_to(message, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.reply_to(message, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.reply_to(message, '❌ Недостаточно средств!')
        return
    sectors = ['🍒 x2', '🍋 x3', '🍊 x1', '💎 x5', '❌ 0']
    win_sector = random.choice(sectors)
    if 'x' in win_sector and random.random() < 0.6:  # 60% шанс выигрыша
        multiplier = int(win_sector.split('x')[1])
        win = bet * multiplier
        update_balance(user_id, win)
        bot.reply_to(message, f'🎡 Колесо показало: {win_sector}\n✅ Выигрыш: +{win}₽ (шанс 60%)')
    else:
        update_balance(user_id, -bet)
        bot.reply_to(message, f'🎡 Колесо показало: {win_sector}\n❌ Проигрыш: -{bet}₽ (шанс 60%)')

@bot.message_handler(commands=['roulette', 'рулетка'])
def roulette(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/roulette [ставка]` или `/рулетка [ставка]`', parse_mode='Markdown')
        return
    try:
        bet = int(args[1])
    except:
        bot.reply_to(message, '❌ Ставка должна быть числом!')
        return
    if bet <= 0:
        bot.reply_to(message, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < bet:
        bot.reply_to(message, '❌ Недостаточно средств!')
        return
    number = random.randint(0, 36)
    if number != 0 and number % 2 == 0:
        if random.random() < 0.48:  # 48% шанс выигрыша
            win = bet * 2
            update_balance(user_id, win)
            bot.reply_to(message, f'🔴 Выпало *{number}* (КРАСНОЕ)!\n✅ Ты выиграл *{win}₽*! (шанс 48%)', parse_mode='Markdown')
        else:
            update_balance(user_id, -bet)
            bot.reply_to(message, f'🔴 Выпало *{number}* (КРАСНОЕ)!\n❌ Ты проиграл *{bet}₽*! (шанс 48%)', parse_mode='Markdown')
    elif number != 0 and number % 2 != 0:
        if random.random() < 0.48:
            win = bet * 2
            update_balance(user_id, win)
            bot.reply_to(message, f'⚫ Выпало *{number}* (ЧЁРНОЕ)!\n✅ Ты выиграл *{win}₽*! (шанс 48%)', parse_mode='Markdown')
        else:
            update_balance(user_id, -bet)
            bot.reply_to(message, f'⚫ Выпало *{number}* (ЧЁРНОЕ)!\n❌ Ты проиграл *{bet}₽*! (шанс 48%)', parse_mode='Markdown')
    else:
        update_balance(user_id, -bet)
        bot.reply_to(message, f'🟢 Выпал *0* (ЗЕЛЁНЫЙ)!\n❌ Ты проиграл *{bet}₽*! (шанс 48%)', parse_mode='Markdown')

# --- /pay ---
@bot.message_handler(commands=['pay', 'платёж'])
def pay(message):
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/pay [сумма]` или `/платёж [сумма]` (ответь на сообщение)', parse_mode='Markdown')
        return
    try:
        amount = int(args[1])
    except:
        bot.reply_to(message, '❌ Сумма должна быть числом!')
        return
    if amount <= 0:
        bot.reply_to(message, '❌ Сумма должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < amount:
        bot.reply_to(message, '❌ Недостаточно средств!')
        return
    if not message.reply_to_message:
        bot.reply_to(message, '❌ Ответь на сообщение пользователя!')
        return
    target_id = message.reply_to_message.from_user.id
    if target_id == user_id:
        bot.reply_to(message, '❌ Нельзя перевести самому себе!')
        return
    update_balance(user_id, -amount)
    update_balance(target_id, amount)
    bot.reply_to(message, f'✅ Переведено {amount}₽ пользователю @{message.reply_to_message.from_user.username or target_id}')
    bot.send_message(target_id, f'💰 Ты получил {amount}₽ от @{message.from_user.username or user_id}')

# --- /duel ---
@bot.message_handler(commands=['duel', 'дуэль'])
def duel(message):
    if not message.reply_to_message:
        bot.reply_to(message, '❌ Ответь на сообщение соперника!')
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/duel [сумма]` или `/дуэль [сумма]`', parse_mode='Markdown')
        return
    try:
        amount = int(args[1])
    except:
        bot.reply_to(message, '❌ Ставка должна быть числом!')
        return
    if amount <= 0:
        bot.reply_to(message, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    if user_id == target_id:
        bot.reply_to(message, '❌ Нельзя вызвать себя!')
        return
    if get_balance(user_id) < amount:
        bot.reply_to(message, '❌ Недостаточно средств!')
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('✅ Принять', callback_data=f'duel_accept_{user_id}_{target_id}_{amount}'))
    markup.add(types.InlineKeyboardButton('❌ Отклонить', callback_data=f'duel_reject_{user_id}_{target_id}'))
    bot.send_message(target_id, f'⚔️ @{message.from_user.username or user_id} вызывает тебя на дуэль!\n💰 Ставка: {amount}₽', reply_markup=markup)
    bot.reply_to(message, '⚔️ Запрос на дуэль отправлен! Жди ответа.')

@bot.callback_query_handler(func=lambda call: call.data.startswith('duel_'))
def duel_callback(call):
    data = call.data.split('_')
    action = data[1]
    if action == 'reject':
        bot.answer_callback_query(call.id, 'Дуэль отклонена!')
        bot.edit_message_text('❌ Дуэль отклонена.', call.message.chat.id, call.message.message_id)
        return
    user_id = int(data[2])
    target_id = int(data[3])
    amount = int(data[4])
    if call.from_user.id != target_id:
        bot.answer_callback_query(call.id, 'Это не твоя дуэль!', show_alert=True)
        return
    if get_balance(user_id) < amount or get_balance(target_id) < amount:
        bot.answer_callback_query(call.id, 'У одного из игроков недостаточно средств!', show_alert=True)
        return
    winner = random.choice([user_id, target_id])
    loser = target_id if winner == user_id else user_id
    update_balance(winner, amount)
    update_balance(loser, -amount)
    if get_balance(loser) < -50000:
        update_balance(loser, -get_balance(loser))
        add_penalty(loser, 2)
        bot.send_message(loser, '💀 Твой счёт обнулён! Ты под штрафом 2 дня!')
    bot.edit_message_text(f'⚔️ *Дуэль завершена!*\n🥇 Победитель: @{call.from_user.username or winner}\n💰 Выигрыш: {amount}₽', call.message.chat.id, call.message.message_id, parse_mode='Markdown')
    bot.answer_callback_query(call.id, 'Дуэль окончена!')

# --- СЕМЬЯ ---
@bot.message_handler(commands=['семьясоздать'])
def family_create(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/семьясоздать [название]`', parse_mode='Markdown')
        return
    name = args[1]
    user_id = message.from_user.id
    cursor.execute('SELECT * FROM families WHERE name = ?', (name,))
    if cursor.fetchone():
        bot.reply_to(message, '❌ Семья с таким названием уже существует!')
        return
    cursor.execute('INSERT INTO families (name, owner_id) VALUES (?, ?)', (name, user_id))
    cursor.execute('INSERT INTO family_members (user_id, family_name) VALUES (?, ?)', (user_id, name))
    cursor.execute('UPDATE users SET family = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    backup_to_github()
    bot.reply_to(message, f'✅ Семья "{name}" создана! Ты её глава.')

@bot.message_handler(commands=['семьявступить'])
def family_join(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.reply_to(message, '❌ Используй: `/семьявступить [название]`', parse_mode='Markdown')
        return
    name = args[1]
    user_id = message.from_user.id
    cursor.execute('SELECT * FROM families WHERE name = ?', (name,))
    if not cursor.fetchone():
        bot.reply_to(message, '❌ Семья не найдена!')
        return
    cursor.execute('INSERT INTO family_members (user_id, family_name) VALUES (?, ?)', (user_id, name))
    cursor.execute('UPDATE users SET family = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    backup_to_github()
    bot.reply_to(message, f'✅ Ты вступил в семью "{name}"!')

@bot.message_handler(commands=['семьявыйти'])
def family_leave(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user or not user[4]:
        bot.reply_to(message, '❌ Ты не состоишь в семье!')
        return
    family_name = user[4]
    cursor.execute('DELETE FROM family_members WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE users SET family = NULL WHERE user_id = ?', (user_id,))
    cursor.execute('SELECT COUNT(*) FROM family_members WHERE family_name = ?', (family_name,))
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute('DELETE FROM families WHERE name = ?', (family_name,))
        bot.reply_to(message, f'🏚️ Ты покинул семью "{family_name}". Семья распущена.')
    else:
        bot.reply_to(message, f'👋 Ты покинул семью "{family_name}".')
    conn.commit()
    backup_to_github()

@bot.message_handler(commands=['семьясписок'])
def family_list(message):
    cursor.execute('SELECT name FROM families')
    families = cursor.fetchall()
    if not families:
        bot.reply_to(message, '📭 Пока нет созданных семей.')
        return
    text = '📋 *Список семей:*\n\n'
    for f in families:
        cursor.execute('SELECT COUNT(*) FROM family_members WHERE family_name = ?', (f[0],))
        count = cursor.fetchone()[0]
        text += f'🏠 *{f[0]}* — {count} участников\n'
    bot.reply_to(message, text, parse_mode='Markdown')

@bot.message_handler(commands=['семьябаланс'])
def family_balance(message):
    user = get_user(message.from_user.id)
    if not user or not user[4]:
        bot.reply_to(message, '❌ Ты не в семье!')
        return
    family_name = user[4]
    cursor.execute('SELECT user_id FROM family_members WHERE family_name = ?', (family_name,))
    members = cursor.fetchall()
    total = 0
    for m in members:
        total += get_balance(m[0])
    bot.reply_to(message, f'💰 *Общий баланс семьи "{family_name}": {total}₽*', parse_mode='Markdown')

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
