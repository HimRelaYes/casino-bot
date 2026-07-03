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

TOKEN = '8217975863:AAEScN82IIMAq2hi7YtI_K_TfXqBd0NXlMk'  # ВСТАВЬ СВОЙ ТОКЕН!
bot = telebot.TeleBot(TOKEN)

# --- ВЕБ-СЕРВЕР ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def home():
    return "✅ БОТ РАБОТАЕТ!"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

threading.Thread(target=run_flask, daemon=True).start()

# --- БАЗА ДАННЫХ ---
DB_PATH = '/tmp/casino.db'

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
    sub_check_time TEXT DEFAULT NULL
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

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def get_user(user_id):
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    return cursor.fetchone()

def register_user(user_id, name):
    cursor.execute('INSERT OR IGNORE INTO users (user_id, name) VALUES (?, ?)', (user_id, name))
    conn.commit()

def get_balance(user_id):
    cursor.execute('SELECT balance FROM users WHERE user_id = ?', (user_id,))
    res = cursor.fetchone()
    return res[0] if res else 0

def update_balance(user_id, amount):
    cursor.execute('UPDATE users SET balance = balance + ? WHERE user_id = ?', (amount, user_id))
    conn.commit()

def add_penalty(user_id, days):
    until = datetime.now() + timedelta(days=days)
    cursor.execute('UPDATE users SET penalty_until = ? WHERE user_id = ?', (until.strftime('%Y-%m-%d %H:%M:%S'), user_id))
    conn.commit()

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

# --- КОМАНДЫ ---
@bot.message_handler(commands=['start', 'старт'])
def start(message):
    user_id = message.from_user.id
    register_user(user_id, message.from_user.first_name)
    bot.send_message(message.chat.id, 
        "🎰 *Добро пожаловать в Casino Empire!*\n\n"
        "👋 Я бот-казино с семьями, работой и дуэлями!\n"
        "📋 Введи /help или /помощь чтобы увидеть все команды.\n\n"
        "🔥 *КВЕСТ:* Подпишись на https://t.me/rengadeup и получи 1000₽!\n"
        "Используй /подписка после подписки.",
        parse_mode='Markdown')

@bot.message_handler(commands=['help', 'помощь'])
def help_command(message):
    help_text = """
🎰 *CASINO EMPIRE — ПОМОЩЬ*

━━━━━━━━━━━━━━━━━━━━

👤 *ПРОФИЛЬ И ДЕНЬГИ*
├ /profile или /профиль — твой профиль
├ /profile [ID] или /профиль [ID] — профиль игрока
├ /balance или /баланс — узнать баланс
├ /pay [сумма] или /платёж [сумма] — перевести (ответь на сообщение)
└ /top или /топ — топ 10 игроков по деньгам

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
    
    # Если указан ID другого игрока
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
    work = user[3] if user[3] else 'Нет'
    family = user[4] if user[4] else 'Нет'
    penalty = '⚠️ Да' if is_penalized(target_id) else '✅ Нет'
    subscribed = '✅ Да' if user[9] == 1 else '❌ Нет'
    
    text = f"""
👤 *Профиль игрока*

━━━━━━━━━━━━━━━━━━━━
💰 *Баланс:* {balance}₽
💼 *Работа:* {work}
🏠 *Семья:* {family}
⚠️ *Штраф:* {penalty}
📢 *Подписка:* {subscribed}
━━━━━━━━━━━━━━━━━━━━
"""
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['balance', 'баланс'])
def balance(message):
    bal = get_balance(message.from_user.id)
    bot.send_message(message.chat.id, f'💰 Твой баланс: *{bal}₽*', parse_mode='Markdown')

@bot.message_handler(commands=['top', 'топ'])
def top_players(message):
    cursor.execute('SELECT user_id, name, balance FROM users ORDER BY balance DESC LIMIT 10')
    tops = cursor.fetchall()
    
    if not tops:
        bot.send_message(message.chat.id, '📭 Пока нет игроков!')
        return
    
    text = "🏆 *ТОП 10 ИГРОКОВ ПО ДЕНЬГАМ*\n━━━━━━━━━━━━━━━━━━━━\n"
    for i, (user_id, name, balance) in enumerate(tops, 1):
        medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else f"{i}."
        text += f"{medal} *{name}* — {balance}₽\n"
    
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

# --- РАБОТЫ ---
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

# --- /bonus ---
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

# --- КВЕСТ: ПОДПИСКА ---
@bot.message_handler(commands=['подписка'])
def check_subscription(message):
    user_id = message.from_user.id
    CHANNEL_ID = '@rengadeup'  # или ID канала (например -1001234567890)
    
    try:
        # Проверяем подписку
        member = bot.get_chat_member(CHANNEL_ID, user_id)
        
        if member.status in ['member', 'creator', 'administrator']:
            # Проверяем, не получал ли уже награду
            cursor.execute('SELECT subscribed FROM users WHERE user_id = ?', (user_id,))
            res = cursor.fetchone()
            
            if res and res[0] == 1:
                bot.send_message(message.chat.id, '❌ Ты уже получил награду за подписку!')
            else:
                # Даём награду
                update_balance(user_id, 1000)
                cursor.execute('UPDATE users SET subscribed = 1 WHERE user_id = ?', (user_id,))
                cursor.execute('UPDATE users SET sub_check_time = ? WHERE user_id = ?', (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), user_id))
                conn.commit()
                bot.send_message(message.chat.id, '✅ Ты подписан на канал!\n🎁 Получил 1000₽ в подарок!')
        else:
            # Если отписался, но награда была получена
            cursor.execute('SELECT subscribed FROM users WHERE user_id = ?', (user_id,))
            res = cursor.fetchone()
            if res and res[0] == 1:
                # Штраф 3000
                update_balance(user_id, -3000)
                cursor.execute('UPDATE users SET subscribed = 0 WHERE user_id = ?', (user_id,))
                conn.commit()
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

# --- /pay ---
@bot.message_handler(commands=['pay', 'платёж'])
def pay(message):
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/pay [сумма]` или `/платёж [сумма]` (ответь на сообщение)', parse_mode='Markdown')
        return
    try:
        amount = int(args[1])
    except:
        bot.send_message(message.chat.id, '❌ Сумма должна быть числом!')
        return
    if amount <= 0:
        bot.send_message(message.chat.id, '❌ Сумма должна быть больше 0!')
        return
    user_id = message.from_user.id
    if get_balance(user_id) < amount:
        bot.send_message(message.chat.id, '❌ Недостаточно средств!')
        return
    if not message.reply_to_message:
        bot.send_message(message.chat.id, '❌ Ответь на сообщение пользователя!')
        return
    target_id = message.reply_to_message.from_user.id
    if target_id == user_id:
        bot.send_message(message.chat.id, '❌ Нельзя перевести самому себе!')
        return
    update_balance(user_id, -amount)
    update_balance(target_id, amount)
    bot.send_message(message.chat.id, f'✅ Переведено {amount}₽ пользователю @{message.reply_to_message.from_user.username or target_id}')
    bot.send_message(target_id, f'💰 Ты получил {amount}₽ от @{message.from_user.username or user_id}')

# --- /duel ---
@bot.message_handler(commands=['duel', 'дуэль'])
def duel(message):
    if not message.reply_to_message:
        bot.send_message(message.chat.id, '❌ Ответь на сообщение соперника!')
        return
    args = message.text.split()
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/duel [сумма]` или `/дуэль [сумма]`', parse_mode='Markdown')
        return
    try:
        amount = int(args[1])
    except:
        bot.send_message(message.chat.id, '❌ Ставка должна быть числом!')
        return
    if amount <= 0:
        bot.send_message(message.chat.id, '❌ Ставка должна быть больше 0!')
        return
    user_id = message.from_user.id
    target_id = message.reply_to_message.from_user.id
    if user_id == target_id:
        bot.send_message(message.chat.id, '❌ Нельзя вызвать себя!')
        return
    if get_balance(user_id) < amount:
        bot.send_message(message.chat.id, '❌ Недостаточно средств!')
        return
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton('✅ Принять', callback_data=f'duel_accept_{user_id}_{target_id}_{amount}'))
    markup.add(types.InlineKeyboardButton('❌ Отклонить', callback_data=f'duel_reject_{user_id}_{target_id}'))
    bot.send_message(target_id, f'⚔️ @{message.from_user.username or user_id} вызывает тебя на дуэль!\n💰 Ставка: {amount}₽', reply_markup=markup)

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
        bot.send_message(message.chat.id, '❌ Используй: `/семьясоздать [название]`', parse_mode='Markdown')
        return
    name = args[1]
    user_id = message.from_user.id
    cursor.execute('SELECT * FROM families WHERE name = ?', (name,))
    if cursor.fetchone():
        bot.send_message(message.chat.id, '❌ Семья с таким названием уже существует!')
        return
    cursor.execute('INSERT INTO families (name, owner_id) VALUES (?, ?)', (name, user_id))
    cursor.execute('INSERT INTO family_members (user_id, family_name) VALUES (?, ?)', (user_id, name))
    cursor.execute('UPDATE users SET family = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    bot.send_message(message.chat.id, f'✅ Семья "{name}" создана! Ты её глава.')

@bot.message_handler(commands=['семьявступить'])
def family_join(message):
    args = message.text.split(maxsplit=1)
    if len(args) < 2:
        bot.send_message(message.chat.id, '❌ Используй: `/семьявступить [название]`', parse_mode='Markdown')
        return
    name = args[1]
    user_id = message.from_user.id
    cursor.execute('SELECT * FROM families WHERE name = ?', (name,))
    if not cursor.fetchone():
        bot.send_message(message.chat.id, '❌ Семья не найдена!')
        return
    cursor.execute('INSERT INTO family_members (user_id, family_name) VALUES (?, ?)', (user_id, name))
    cursor.execute('UPDATE users SET family = ? WHERE user_id = ?', (name, user_id))
    conn.commit()
    bot.send_message(message.chat.id, f'✅ Ты вступил в семью "{name}"!')

@bot.message_handler(commands=['семьявыйти'])
def family_leave(message):
    user_id = message.from_user.id
    user = get_user(user_id)
    if not user or not user[4]:
        bot.send_message(message.chat.id, '❌ Ты не состоишь в семье!')
        return
    family_name = user[4]
    cursor.execute('DELETE FROM family_members WHERE user_id = ?', (user_id,))
    cursor.execute('UPDATE users SET family = NULL WHERE user_id = ?', (user_id,))
    cursor.execute('SELECT COUNT(*) FROM family_members WHERE family_name = ?', (family_name,))
    count = cursor.fetchone()[0]
    if count == 0:
        cursor.execute('DELETE FROM families WHERE name = ?', (family_name,))
        bot.send_message(message.chat.id, f'🏚️ Ты покинул семью "{family_name}". Семья распущена.')
    else:
        bot.send_message(message.chat.id, f'👋 Ты покинул семью "{family_name}".')
    conn.commit()

@bot.message_handler(commands=['семьясписок'])
def family_list(message):
    cursor.execute('SELECT name FROM families')
    families = cursor.fetchall()
    if not families:
        bot.send_message(message.chat.id, '📭 Пока нет созданных семей.')
        return
    text = '📋 *Список семей:*\n\n'
    for f in families:
        cursor.execute('SELECT COUNT(*) FROM family_members WHERE family_name = ?', (f[0],))
        count = cursor.fetchone()[0]
        text += f'🏠 *{f[0]}* — {count} участников\n'
    bot.send_message(message.chat.id, text, parse_mode='Markdown')

@bot.message_handler(commands=['семьябаланс'])
def family_balance(message):
    user = get_user(message.from_user.id)
    if not user or not user[4]:
        bot.send_message(message.chat.id, '❌ Ты не в семье!')
        return
    family_name = user[4]
    cursor.execute('SELECT user_id FROM family_members WHERE family_name = ?', (family_name,))
    members = cursor.fetchall()
    total = 0
    for m in members:
        total += get_balance(m[0])
    bot.send_message(message.chat.id, f'💰 *Общий баланс семьи "{family_name}": {total}₽*', parse_mode='Markdown')

# --- ЗАПУСК БОТА ---
if __name__ == '__main__':
    while True:
        try:
            print('✅ БОТ ЗАПУЩЕН НА RENDER!')
            print('📋 Бот работает в чатах!')
            bot.polling(none_stop=True, timeout=60)
        except Exception as e:
            print(f'❌ Ошибка: {e}')
            print('🔄 Перезапуск через 5 секунд...')
            time.sleep(5)
