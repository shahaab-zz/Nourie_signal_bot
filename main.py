import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

app = Flask(__name__)

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"  # توکن تو
CHAT_ID = "52909831"  # آیدی چت تلگرام تو

bot = Bot(token=TOKEN)

last_check_time = None
market_open = False

def get_sahamyab_data():
    try:
        url = "https://api.sahamyab.com/stock/norie"  # نمونه فرضی، حتما اصلاح کن
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception:
        return None

def is_market_open():
    now = datetime.now().time()
    morning_start = dtime(9, 0)
    morning_end = dtime(12, 30)
    afternoon_start = dtime(13, 30)
    afternoon_end = dtime(15, 0)
    return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

def check_market_and_notify():
    global last_check_time, market_open

    while True:
        now = datetime.now()
        open_status = is_market_open()

        data = get_sahamyab_data()
        if data is None:
            bot.send_message(chat_id=CHAT_ID, text="🚨 خطا در دریافت داده از سهامیاب!")
        else:
            if open_status and not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
            elif not open_status and market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")

        last_check_time = now
        time.sleep(120)

@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.")

def status(update, context):
    global last_check_time, market_open
    status_text = f"آخرین بررسی: {last_check_time}\nوضعیت بازار: {'باز' if market_open else 'بسته'}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="ربات ریست شد.")

def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'start':
        start(update, context)
    elif query.data == 'status':
        status(update, context)
    elif query.data == 'reset':
        reset(update, context)

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("شروع /start", callback_data='start')],
        [InlineKeyboardButton("وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("ریست /reset", callback_data='reset')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('یک گزینه انتخاب کنید:', reply_markup=reply_markup)

from telegram.ext import Updater

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    # اجرای Flask روی همه آدرس‌ها و پورت 10000
    app.run(host='0.0.0.0', port=10000)
