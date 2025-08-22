import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
import sqlite3
import time
import threading
from datetime import datetime

TOKEN = '8358000057:AAHRxNRay0kS4T2k10EKB13f_i0rut8E4JQ'
OWNER_ID = 7391705411

bot = telebot.TeleBot(TOKEN)
bot_username = bot.get_me().username

conn = sqlite3.connect('bot.db', check_same_thread=False)
cur = conn.cursor()

cur.execute('''CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT,
    name TEXT,
    phone TEXT,
    verified INTEGER DEFAULT 0,
    inviter_id INTEGER,
    score REAL DEFAULT 0.0,
    credited INTEGER DEFAULT 0
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS admins (
    user_id INTEGER PRIMARY KEY,
    is_owner INTEGER DEFAULT 0
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS required_chats (
    chat_id INTEGER PRIMARY KEY,
    username TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)''')

cur.execute('''CREATE TABLE IF NOT EXISTS withdraw_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    amount REAL,
    status TEXT DEFAULT 'pending'
)''')

cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('referral_score', '0.5')")
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('support_text', 'پشتیبانی: تماس با @admin')")
cur.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('guide_text', 'راهنما: دعوت دوستان برای امتیاز')")
cur.execute("INSERT OR IGNORE INTO admins (user_id, is_owner) VALUES (?, 1)", (OWNER_ID,))
conn.commit()

user_states = {}

def get_referral_score():
    cur.execute("SELECT value FROM settings WHERE key='referral_score'")
    return float(cur.fetchone()[0])

def set_referral_score(new_score):
    cur.execute("UPDATE settings SET value=? WHERE key='referral_score'", (str(new_score),))
    conn.commit()

def get_support_text():
    cur.execute("SELECT value FROM settings WHERE key='support_text'")
    return cur.fetchone()[0]

def set_support_text(text):
    cur.execute("UPDATE settings SET value=? WHERE key='support_text'", (text,))
    conn.commit()

def get_guide_text():
    cur.execute("SELECT value FROM settings WHERE key='guide_text'")
    return cur.fetchone()[0]

def set_guide_text(text):
    cur.execute("UPDATE settings SET value=? WHERE key='guide_text'", (text,))
    conn.commit()

def is_admin(user_id):
    cur.execute("SELECT * FROM admins WHERE user_id=?", (user_id,))
    return cur.fetchone() is not None

def is_owner(user_id):
    cur.execute("SELECT is_owner FROM admins WHERE user_id=?", (user_id,))
    row = cur.fetchone()
    return row and row[0] == 1

def get_required_chats():
    cur.execute("SELECT chat_id, username FROM required_chats")
    return cur.fetchall()

def is_member_in_all(user_id):
    required = get_required_chats()
    if not required:
        return True
    for chat_id, _ in required:
        try:
            member = bot.get_chat_member(chat_id, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except:
            return False
    return True

def get_user_referrals(user_id):
    cur.execute("SELECT user_id FROM users WHERE inviter_id=?", (user_id,))
    return [row[0] for row in cur.fetchall()]

def all_referrals_member(user_id):
    refs = get_user_referrals(user_id)
    for ref in refs:
        if not is_member_in_all(ref):
            return False
    return True

def save_user(user_id, username, name):
    cur.execute("INSERT OR REPLACE INTO users (user_id, username, name) VALUES (?, ?, ?)", (user_id, username, name))
    conn.commit()

def main_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("📩 دعوت دوستان", callback_data='invite'))
    markup.add(InlineKeyboardButton("⭐ امتیازات من", callback_data='scores'), InlineKeyboardButton("ℹ️ راهنما", callback_data='guide'))
    markup.add(InlineKeyboardButton("💰 برداشت", callback_data='withdraw'), InlineKeyboardButton("👤 پشتیبانی", callback_data='support'))
    markup.add(InlineKeyboardButton("🔄 بررسی عضویت", callback_data='check_join'))
    return markup

def withdraw_menu():
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(InlineKeyboardButton("15 استارز", callback_data='wd_15'))
    markup.add(InlineKeyboardButton("30 استارز", callback_data='wd_30'))
    markup.add(InlineKeyboardButton("100 استارز", callback_data='wd_100'))
    markup.add(InlineKeyboardButton("500 استارز", callback_data='wd_500'))
    markup.add(InlineKeyboardButton("برگشت", callback_data='back_main'))
    return markup

def admin_menu(user_id):
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    if is_owner(user_id):
        markup.add("افزودن ادمین")
    markup.add("پیام همگانی", "افزودن کانال/گروه")
    if is_owner(user_id):
        markup.add("تغییر مقدار زیرمجموعه")
    markup.add("تنظیم متن پشتیبانی", "تنظیم متن راهنما")
    markup.add("برگشت")
    return markup

def add_admin_menu():
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=1)
    markup.add("افزودن ادمین (با یوزرنیم)")
    markup.add("حذف ادمین (با یوزرنیم)")
    markup.add("برگشت")
    return markup

def join_menu():
    required = get_required_chats()
    if not required:
        return None
    markup = InlineKeyboardMarkup(row_width=1)
    for _, username in required:
        url = f"https://t.me/{username.lstrip('@')}"
        markup.add(InlineKeyboardButton(f"عضویت در {username}", url=url))
    markup.add(InlineKeyboardButton("✅ بررسی عضویت", callback_data='check_join'))
    return markup

@bot.message_handler(commands=['start'])
def start_handler(message):
    user_id = message.from_user.id
    username = message.from_user.username
    name = message.from_user.first_name
    save_user(user_id, username, name)

    args = message.text.split()
    if len(args) > 1 and args[1].startswith('ref_'):
        try:
            inviter_id = int(args[1].split('_')[1])
            cur.execute("UPDATE users SET inviter_id=? WHERE user_id=? AND inviter_id IS NULL", (inviter_id, user_id))
            conn.commit()
        except:
            pass

    cur.execute("SELECT verified FROM users WHERE user_id=?", (user_id,))
    verified = cur.fetchone()[0]

    if verified:
        join_markup = join_menu()
        if join_markup:
            bot.send_message(user_id, "برای استفاده از ربات، ابتدا در کانال‌ها و گروه‌های زیر عضو شوید:", reply_markup=join_markup)
        else:
            bot.send_message(user_id, "خوش آمدید!", reply_markup=main_menu())
    else:
        markup = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
        btn = KeyboardButton("احراز هویت با شماره ایران", request_contact=True)
        markup.add(btn)
        bot.send_message(user_id, "برای شروع، لطفا شماره تلفن ایران خود را احراز کنید.", reply_markup=markup)

@bot.message_handler(content_types=['contact'])
def contact_handler(message):
    user_id = message.from_user.id
    phone = message.contact.phone_number
    if not phone.startswith('+98') or len(phone) != 13 or not phone[3:].isdigit():
        bot.send_message(user_id, "شماره باید ایرانی معتبر باشد (+989xxxxxxxxx). لطفا دوباره امتحان کنید.")
        return

    cur.execute("UPDATE users SET phone=?, verified=1 WHERE user_id=?", (phone, user_id))
    conn.commit()
    bot.send_message(user_id, "احراز هویت موفق! حالا می‌توانید از ربات استفاده کنید.", reply_markup=ReplyKeyboardRemove())

    join_markup = join_menu()
    if join_markup:
        bot.send_message(user_id, "برای استفاده کامل، در کانال‌ها و گروه‌های زیر عضو شوید:", reply_markup=join_markup)
    else:
        bot.send_message(user_id, "منوی اصلی:", reply_markup=main_menu())

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    user_id = call.from_user.id
    data = call.data

    if data == 'invite':
        ref_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        bot.answer_callback_query(call.id, "لینک دعوت شما آماده است.")
        bot.send_message(user_id, f"لینک دعوت: {ref_link}\nهر زیرمجموعه موفق: {get_referral_score()} استارز\nزیرمجموعه باید احراز هویت کند و در تمام کانال‌ها عضو بماند.")

    elif data == 'scores':
        cur.execute("SELECT score FROM users WHERE user_id=?", (user_id,))
        score = cur.fetchone()[0]
        refs_count = len(get_user_referrals(user_id))
        bot.answer_callback_query(call.id, f"امتیاز شما: {score} استارز\nتعداد زیرمجموعه: {refs_count}")

    elif data == 'guide':
        text = get_guide_text()
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, text)

    elif data == 'support':
        text = get_support_text()
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, text)

    elif data == 'withdraw':
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "مقدار برداشت را انتخاب کنید:", reply_markup=withdraw_menu())

    elif data.startswith('wd_'):
        amount = float(data.split('_')[1])
        cur.execute("SELECT score FROM users WHERE user_id=?", (user_id,))
        score = cur.fetchone()[0]
        if score < amount:
            bot.answer_callback_query(call.id, "امتیاز کافی ندارید.")
            return
        if not all_referrals_member(user_id):
            bot.answer_callback_query(call.id, "برخی زیرمجموعه‌ها در تمام گروه‌ها عضو نیستند.")
            return
        cur.execute("INSERT INTO withdraw_requests (user_id, amount) VALUES (?, ?)", (user_id, amount))
        conn.commit()
        request_id = cur.lastrowid

        cur.execute("SELECT username, name FROM users WHERE user_id=?", (user_id,))
        username, name = cur.fetchone()

        admins_list = [row[0] for row in cur.execute("SELECT user_id FROM admins").fetchall()]
        msg = f"کاربر @{username} ({user_id}) {name} درخواست برداشت {amount} استارز کرده.\nلطفا در اسرع وقت واریز کنید."
        for adm in admins_list:
            bot.send_message(adm, msg)

        bot.answer_callback_query(call.id, "درخواست ارسال شد.")
        bot.send_message(user_id, "کاربر محترم، چند دقیقه یا چند ساعت منتظر بمانید. ادمین‌ها در حال پردازش هستند.")

    elif data == 'back_main':
        bot.answer_callback_query(call.id)
        bot.send_message(user_id, "منوی اصلی:", reply_markup=main_menu())

    elif data == 'check_join':
        if is_member_in_all(user_id):
            cur.execute("SELECT inviter_id, credited FROM users WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            inviter_id, credited = row
            if inviter_id and credited == 0:
                score_add = get_referral_score()
                cur.execute("UPDATE users SET score = score + ? WHERE user_id=?", (score_add, inviter_id))
                cur.execute("UPDATE users SET credited=1 WHERE user_id=?", (user_id,))
                conn.commit()
                bot.send_message(inviter_id, f"زیرمجموعه جدید شما تایید شد. +{score_add} استارز")
            bot.answer_callback_query(call.id, "عضویت شما در تمام کانال‌ها تایید شد.")
            bot.send_message(user_id, "منوی اصلی:", reply_markup=main_menu())
        else:
            bot.answer_callback_query(call.id, "شما هنوز در تمام کانال‌ها عضو نیستید.")

@bot.chat_member_handler()
def chat_member_update(update):
    if update.new_chat_member.status == 'left':
        user_id = update.from_user.id
        chat_id = update.chat.id
        cur.execute("SELECT * FROM required_chats WHERE chat_id=?", (chat_id,))
        if cur.fetchone():
            cur.execute("SELECT inviter_id, credited, username FROM users WHERE user_id=?", (user_id,))
            row = cur.fetchone()
            if row:
                inviter_id, credited, username = row
                if inviter_id and credited == 1:
                    score_ded = get_referral_score()
                    cur.execute("UPDATE users SET score = score - ? WHERE user_id=?", (score_ded, inviter_id))
                    cur.execute("UPDATE users SET credited=0 WHERE user_id=?", (user_id,))
                    conn.commit()
                    bot.send_message(inviter_id, f"زیرمجموعه شما @{username} از کانال لف داد. امتیاز {score_ded} کسر شد.")

@bot.message_handler(commands=['admin'])
def admin_handler(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        bot.send_message(user_id, "شما ادمین نیستید.")
        return
    bot.send_message(user_id, "پنل ادمینی:", reply_markup=admin_menu(user_id))

@bot.message_handler(commands=['end'])
def end_handler(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return
    args = message.text.split()
    if len(args) < 3:
        bot.send_message(user_id, "فرمت: /end user_id_or_username رسید")
        return
    target = args[1]
    hash_tx = args[2]
    try:
        target_id = int(target)
    except:
        try:
            target_id = bot.get_chat(target).id
        except:
            bot.send_message(user_id, "یوزرنیم یا آیدی نامعتبر.")
            return
    cur.execute("SELECT id, amount, status FROM withdraw_requests WHERE user_id=? AND status='pending'", (target_id,))
    row = cur.fetchone()
    if not row:
        bot.send_message(user_id, "درخواست pending یافت نشد.")
        return
    req_id, amount, _ = row
    cur.execute("UPDATE withdraw_requests SET status='done' WHERE id=?", (req_id,))
    cur.execute("UPDATE users SET score = score - ? WHERE user_id=?", (amount, target_id))
    conn.commit()
    bot.send_message(target_id, f"درخواست برداشت شما انجام شد. رسید تراکنش: {hash_tx}")
    bot.send_message(user_id, "تایید شد.")

@bot.message_handler(func=lambda m: True)
def text_handler(message):
    user_id = message.from_user.id
    text = message.text
    state = user_states.get(user_id)

    if state == 'broadcast':
        cur.execute("SELECT user_id FROM users")
        users = [row[0] for row in cur.fetchall()]
        for uid in users:
            try:
                bot.send_message(uid, text)
            except:
                pass
        bot.send_message(user_id, "پیام همگانی ارسال شد.")
        del user_states[user_id]

    elif state == 'add_admin':
        username = text.lstrip('@')
        try:
            new_id = bot.get_chat(f'@{username}').id
            cur.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (new_id,))
            conn.commit()
            bot.send_message(user_id, "ادمین اضافه شد.")
        except:
            bot.send_message(user_id, "یوزرنیم نامعتبر.")
        del user_states[user_id]

    elif state == 'del_admin':
        username = text.lstrip('@')
        try:
            del_id = bot.get_chat(f'@{username}').id
            cur.execute("DELETE FROM admins WHERE user_id=? AND is_owner=0", (del_id,))
            conn.commit()
            bot.send_message(user_id, "ادمین حذف شد.")
        except:
            bot.send_message(user_id, "یوزرنیم نامعتبر.")
        del user_states[user_id]

    elif state == 'add_channel':
        if text.startswith('@'):
            chat_username = text
        elif 't.me/' in text:
            chat_username = '@' + text.split('t.me/')[1].split('/')[0]
        else:
            bot.send_message(user_id, "لینک یا آیدی معتبر بفرستید.")
            return
        try:
            chat = bot.get_chat(chat_username)
            member = bot.get_chat_member(chat.id, bot.get_me().id)
            if member.status != 'administrator':
                bot.send_message(user_id, "ربات ادمین آنجا نیست.")
                return
            cur.execute("INSERT OR IGNORE INTO required_chats (chat_id, username) VALUES (?, ?)", (chat.id, chat_username))
            conn.commit()
            bot.send_message(user_id, "کانال/گروه اضافه شد.")
        except:
            bot.send_message(user_id, "خطا در افزودن.")
        del user_states[user_id]

    elif state == 'change_ref_score':
        try:
            new_score = float(text)
            set_referral_score(new_score)
            bot.send_message(user_id, "مقدار تغییر کرد.")
        except:
            bot.send_message(user_id, "عدد معتبر وارد کنید.")
        del user_states[user_id]

    elif state == 'set_support':
        set_support_text(text)
        bot.send_message(user_id, "متن پشتیبانی بروز شد.")
        del user_states[user_id]

    elif state == 'set_guide':
        set_guide_text(text)
        bot.send_message(user_id, "متن راهنما بروز شد.")
        del user_states[user_id]

    elif text == 'پیام همگانی':
        if is_admin(user_id):
            user_states[user_id] = 'broadcast'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "پیام خود را ارسال کنید تا برای همه بفرستم.", reply_markup=markup)

    elif text == 'افزودن ادمین':
        if is_owner(user_id):
            bot.send_message(user_id, "انتخاب کنید:", reply_markup=add_admin_menu())
        else:
            bot.send_message(user_id, "شما دسترسی ندارید.")

    elif text == 'افزودن ادمین (با یوزرنیم)':
        if is_owner(user_id):
            user_states[user_id] = 'add_admin'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "یوزرنیم ادمین جدید را بفرستید (@username)", reply_markup=markup)
        else:
            bot.send_message(user_id, "شما دسترسی ندارید.")

    elif text == 'حذف ادمین (با یوزرنیم)':
        if is_owner(user_id):
            user_states[user_id] = 'del_admin'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "یوزرنیم ادمین برای حذف بفرستید (@username)", reply_markup=markup)
        else:
            bot.send_message(user_id, "شما دسترسی ندارید.")

    elif text == 'افزودن کانال/گروه':
        if is_admin(user_id):
            user_states[user_id] = 'add_channel'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "ادمین محترم، اول ربات را ادمین کنید سپس آیدی یا لینک کانال/گروه را بفرستید.", reply_markup=markup)

    elif text == 'تغییر مقدار زیرمجموعه':
        if is_owner(user_id):
            user_states[user_id] = 'change_ref_score'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "مقدار جدید را وارد کنید (مثل 0.5)", reply_markup=markup)
        else:
            bot.send_message(user_id, "شما دسترسی ندارید.")

    elif text == 'تنظیم متن پشتیبانی':
        if is_admin(user_id):
            user_states[user_id] = 'set_support'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "متن جدید پشتیبانی را بفرستید.", reply_markup=markup)

    elif text == 'تنظیم متن راهنما':
        if is_admin(user_id):
            user_states[user_id] = 'set_guide'
            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add("برگشت")
            bot.send_message(user_id, "متن جدید راهنما را بفرستید.", reply_markup=markup)

    elif text == 'برگشت':
        if is_admin(user_id):
            if user_id in user_states:
                del user_states[user_id]
            bot.send_message(user_id, "بازگشت به پنل.", reply_markup=admin_menu(user_id))
        else:
            bot.send_message(user_id, "بازگشت.", reply_markup=ReplyKeyboardRemove())

bot.infinity_polling(allowed_updates=['message', 'callback_query', 'chat_member'])
