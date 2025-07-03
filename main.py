import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

app = Flask(__name__)
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
            bot.send_message(
                chat_id=CHAT_ID,
                text=f"❗ پاسخ غیرموفق از API:\nکد وضعیت: {status}\nمتن:\n{text}\nآدرس:\n{url}"
            )
            return None

        if not text:
            bot.send_message(
                chat_id=CHAT_ID,
                text=f"⚠️ پاسخ خالی از API دریافت شد:\nآدرس: {url}"
            )
            return None

        return response.json()

    except Exception as e:
        bot.send_message(
            chat_id=CHAT_ID,
            text=f"🚨 خطا در اتصال به داده BrsApi:\nآدرس: {url}\nخطا: {e}"
        )
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

        if selected_source == "brsapi":
            symbol_id = "46602927695631802"
            data = get_brsapi_data(symbol_id)
        else:
            data = None  # منابع بعدی

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

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("♻️ ریست /reset", callback_data='reset')],
        [InlineKeyboardButton("🔍 منبع: BrsApi", callback_data='source_brsapi')],
        [InlineKeyboardButton("🔒 منبع: Sahamyab (غیرفعال)", callback_data='source_sahamyab')],
        [InlineKeyboardButton("🔒 منبع: TSETMC (غیرفعال)", callback_data='source_tsetmc')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('یکی از گزینه‌ها را انتخاب کن:', reply_markup=reply_markup)

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.")
    menu(update, context)

def status(update, context):
    global last_check_time, market_open, selected_source
    now_status = "باز" if market_open else "بسته"
    text = f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {now_status}\n📡 منبع داده: {selected_source}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="♻️ ربات ریست شد.")

def button(update, context):
    global selected_source
    query = update.callback_query
    query.answer()
    if query.data == 'start':
        start(update, context)
    elif query.data == 'status':
        status(update, context)
    elif query.data == 'reset':
        reset(update, context)
    elif query.data.startswith("source_"):
        selected_source = query.data.split("_")[1]
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ منبع داده تغییر یافت به: {selected_source}")

from telegram.ext import Updater
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('menu', menu))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
