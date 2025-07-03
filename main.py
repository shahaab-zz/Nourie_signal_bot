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
last_error_sent = False
SOURCE_FILE = 'selected_source.txt'

def save_selected_source(source):
    with open(SOURCE_FILE, 'w') as f:
        f.write(source)

def load_selected_source():
    if not os.path.exists(SOURCE_FILE):
        return 'brsapi'
    return open(SOURCE_FILE).read().strip()

def get_brsapi_data():
    api_key = os.environ.get("BRSAPI_KEY", "Free5VSOryjPh51wo8o6tltHkv0DhsE8")
    url = "https://brsapi.ir/api/v1/stock-info/46602927695631802"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در BrsApi (نوری):\nآدرس: {url}\nخطا: {e}")
        return None

def get_other_data():
    url = "https://example.com/api/other-source"  # جایگزین کن
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.RequestException as e:
        bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در منبع دیگر:\nآدرس: {url}\nخطا: {e}")
        return None

def get_data():
    src = load_selected_source()
    if src == 'brsapi':
        return get_brsapi_data()
    elif src == 'other':
        return get_other_data()
    else:
        return None

def is_market_open():
    now = datetime.now().time()
    return (dtime(9,0) <= now <= dtime(12,30)) or (dtime(13,30) <= now <= dtime(15,0))

def check_market_and_notify():
    global last_check_time, market_open, last_error_sent
    while True:
        now = datetime.now()
        open_ = is_market_open()
        data = get_data()

        if open_:
            if not data:
                bot.send_message(chat_id=CHAT_ID, text="🚨 خطا در دریافت داده!")
            else:
                last_error_sent = False
                if not market_open:
                    market_open = True
                    bot.send_message(chat_id=CHAT_ID, text="🟢 آغاز بازار")
        else:
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 پایان بازار")
            if not data and not last_error_sent:
                bot.send_message(chat_id=CHAT_ID, text="🚨 خطا (بازار بسته)!")
                last_error_sent = True
            if data:
                last_error_sent = False

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

def main_menu(update, context):
    kb = [
        [InlineKeyboardButton("🟢 BrsApi (نوری)", callback_data='source_brsapi')],
        [InlineKeyboardButton("🔷 منبع دیگر", callback_data='source_other')],
        [InlineKeyboardButton("📊 وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("🔄 ریست /reset", callback_data='reset')],
    ]
    markup = InlineKeyboardMarkup(kb)
    if update.message:
        update.message.reply_text("منوی انتخاب منبع:", reply_markup=markup)
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="منوی انتخاب منبع:", reply_markup=markup)

def status(update, context):
    global last_check_time, market_open
    src = load_selected_source()
    data = get_data()
    ds = "✅ وصل شدم" if data else "❌ نشد"
    txt = f"آخرین بررسی: {last_check_time}\nبازار: {'باز' if market_open else 'بسته'}\nمنبع: {src}\nاتصال: {ds}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=txt)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="🛠️ ربات ری‌ست شد.")

def button_handler(update, context):
    q = update.callback_query
    q.answer()
    d = q.data
    if d.startswith('source_'):
        sel = d.split('_')[1]
        save_selected_source('brsapi' if sel=='brsapi' else 'other')
        q.edit_message_text(text=f"منبع داده تغییر کرد: {sel}")
        main_menu(update, context)
    elif d == 'status':
        status(update, context)
    elif d == 'reset':
        reset(update, context)

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! من فعالم 😊")
    main_menu(update, context)

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), start))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=10000)
