import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

app = Flask(__name__)

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BRSAPI_KEY = os.environ.get("BRSAPI_KEY")

bot = Bot(token=TOKEN)

last_check_time = None
market_open = False
selected_source = "brsapi"  # منبع پیش‌فرض

def get_brsapi_data(symbol_id):
    url = f"https://brsapi.ir/api/v1/stock-info/{symbol_id}"
    headers = {
        "Authorization": f"Bearer {BRSAPI_KEY}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        status = response.status_code
        text = response.text.strip()
        if status != 200:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در BrsApi:\nآدرس: {url}\nوضعیت: {status}\nمتن پاسخ: {text}")
            return None
        if not text:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 پاسخ خالی از BrsApi دریافت شد:\nآدرس: {url}")
            return None
        data = response.json()
        return data
    except requests.exceptions.RequestException as e:
        bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در ارتباط با BrsApi:\nآدرس: {url}\nخطا: {str(e)}")
        return None
    except ValueError as e:
        bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در تجزیه JSON پاسخ BrsApi:\nآدرس: {url}\nپاسخ:\n{text}\nخطا: {str(e)}")
        return None

def get_sahamyab_data():
    # نمونه تابع که بعدا کامل میشه
    return None

def get_codal_data():
    # نمونه تابع که بعدا کامل میشه
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

    symbol_id = "46602927695631802"  # نوری

    while True:
        now = datetime.now()
        open_status = is_market_open()

        if selected_source == "brsapi":
            data = get_brsapi_data(symbol_id)
        elif selected_source == "sahamyab":
            data = get_sahamyab_data()
        elif selected_source == "codal":
            data = get_codal_data()
        else:
            data = None

        if data is None:
            if open_status:
                bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در دریافت داده از منبع {selected_source}!")
        else:
            if open_status and not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text=f"🟢 من فعال شدم. (شروع بازار) منبع: {selected_source}")
            elif not open_status and market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text=f"🔴 من خاموش شدم. (پایان بازار) منبع: {selected_source}")

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
    global last_check_time, market_open, selected_source
    status_text = f"آخرین بررسی: {last_check_time}\nوضعیت بازار: {'باز' if market_open else 'بسته'}\nمنبع فعلی: {selected_source}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="ربات ریست شد.")

def select_source(update, context):
    keyboard = [
        [InlineKeyboardButton("BrsApi", callback_data='source_brsapi')],
        [InlineKeyboardButton("Sahamyab", callback_data='source_sahamyab')],
        [InlineKeyboardButton("Codal", callback_data='source_codal')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('لطفاً منبع داده را انتخاب کنید:', reply_markup=reply_markup)

def button(update, context):
    global selected_source
    query = update.callback_query
    query.answer()
    data = query.data

    if data == 'start':
        start(update, context)
    elif data == 'status':
        status(update, context)
    elif data == 'reset':
        reset(update, context)
    elif data == 'select_source':
        select_source(update, context)
    elif data == 'source_brsapi':
        selected_source = 'brsapi'
        query.edit_message_text(text="منبع داده به BrsApi تغییر یافت.")
    elif data == 'source_sahamyab':
        selected_source = 'sahamyab'
        query.edit_message_text(text="منبع داده به Sahamyab تغییر یافت.")
    elif data == 'source_codal':
        selected_source = 'codal'
        query.edit_message_text(text="منبع داده به Codal تغییر یافت.")
    else:
        query.edit_message_text(text="دستور ناشناخته!")

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("شروع /start", callback_data='start')],
        [InlineKeyboardButton("وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("ریست /reset", callback_data='reset')],
        [InlineKeyboardButton("انتخاب منبع داده", callback_data='select_source')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('یک گزینه انتخاب کنید:', reply_markup=reply_markup)

from telegram.ext import Updater

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(CommandHandler('menu', menu))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
