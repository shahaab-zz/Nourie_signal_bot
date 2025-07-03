import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater
from datetime import datetime, time as dtime

app = Flask(__name__)

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

bot = Bot(token=TOKEN)
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

last_check_time = None
market_open = False
last_error_sent = False  # برای کنترل پیام خطا در حالت باز بودن بازار

SOURCE_FILE = 'selected_source.txt'

# تابع ذخیره منبع انتخاب شده
def save_selected_source(source):
    with open(SOURCE_FILE, 'w') as f:
        f.write(source)

# تابع خواندن منبع انتخاب شده
def load_selected_source():
    if not os.path.exists(SOURCE_FILE):
        # منبع پیش‌فرض
        return 'sahamyab'
    with open(SOURCE_FILE, 'r') as f:
        return f.read().strip()

# توابع نمونه گرفتن داده از منابع مختلف (باید بر اساس API واقعی نوشته شود)
def get_data_from_sahamyab():
    try:
        url = "https://api.sahamyab.com/stock/norie"
        r = requests.get(url, timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def get_data_from_kodal():
    # نمونه فرضی
    return None

def get_data_from_rahavard():
    # نمونه فرضی
    return None

def get_data_from_tsetmc():
    # نمونه فرضی
    return None

# تابع کلی گرفتن دیتا بر اساس منبع انتخاب شده
def get_data():
    source = load_selected_source()
    if source == 'sahamyab':
        return get_data_from_sahamyab()
    elif source == 'kodal':
        return get_data_from_kodal()
    elif source == 'rahavard':
        return get_data_from_rahavard()
    elif source == 'tsetmc':
        return get_data_from_tsetmc()
    else:
        return None

def is_market_open():
    now = datetime.now().time()
    morning_start = dtime(9, 0)
    morning_end = dtime(12, 30)
    afternoon_start = dtime(13, 30)
    afternoon_end = dtime(15, 0)
    return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

def check_market_and_notify():
    global last_check_time, market_open, last_error_sent

    while True:
        now = datetime.now()
        open_status = is_market_open()
        data = get_data()

        if open_status:
            if data is None:
                # بازار باز و دیتا نیست، هر بار پیام خطا بده
                bot.send_message(chat_id=CHAT_ID, text="🚨 خطا در دریافت داده از منبع انتخاب شده!")
            else:
                last_error_sent = False  # دیتا اومد، پس پیام خطا را ریست کن
                if not market_open:
                    market_open = True
                    bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
        else:
            # بازار بسته است
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")
            # در حالت بسته بودن فقط یک بار پیام خطا بده اگر دیتا نیست و هنوز خطا نفرستادی
            if data is None and not last_error_sent:
                bot.send_message(chat_id=CHAT_ID, text="🚨 خطا در دریافت داده از منبع انتخاب شده (بازار بسته)!")
                last_error_sent = True
            # اگر دیتا آمد، پیام خطا را ریست کن
            if data is not None:
                last_error_sent = False

        last_check_time = now
        time.sleep(120)

# منوها و هندلرها

def main_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 انتخاب منبع داده", callback_data='select_source')],
        [InlineKeyboardButton("وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("ریست /reset", callback_data='reset')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    if update.message:
        update.message.reply_text("منوی اصلی:", reply_markup=reply_markup)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="منوی اصلی:", reply_markup=reply_markup)

def sources_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("سهامیاب", callback_data='source_sahamyab')],
        [InlineKeyboardButton("کدال", callback_data='source_kodal')],
        [InlineKeyboardButton("رهاورد 365", callback_data='source_rahavard')],
        [InlineKeyboardButton("TSETMC", callback_data='source_tsetmc')],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='main_menu')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    query = update.callback_query
    query.edit_message_text(text="لطفا منبع داده را انتخاب کنید:", reply_markup=reply_markup)

def status(update, context):
    global last_check_time, market_open
    status_text = f"آخرین بررسی: {last_check_time}\nوضعیت بازار: {'باز' if market_open else 'بسته'}\nمنبع انتخاب شده: {load_selected_source()}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="ربات ریست شد.")

def button_handler(update, context):
    query = update.callback_query
    query.answer()
    data = query.data

    if data == 'main_menu':
        main_menu(update, context)
    elif data == 'select_source':
        sources_menu(update, context)
    elif data == 'status':
        status(update, context)
    elif data == 'reset':
        reset(update, context)
    elif data.startswith('source_'):
        selected_source = data.replace('source_', '')
        save_selected_source(selected_source)
        query.edit_message_text(text=f"شما منبع داده '{selected_source}' را انتخاب کردید.")
        # بعد از انتخاب منبع، منوی اصلی رو نشون بده
        main_menu(update, context)

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.")
    main_menu(update, context)

def menu(update, context):
    main_menu(update, context)

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('menu', menu))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
