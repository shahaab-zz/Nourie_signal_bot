import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

# --- تنظیمات ثابت
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
BRSAPI_KEY = os.environ.get("BRSAPI_KEY")

app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

last_check_time = None
market_open = False
selected_source = "brsapi"

# --- دریافت اطلاعات از brsapi
def get_brsapi_data(symbol_id):
    url = f"https://brsapi.ir/api/v1/stock-info/{symbol_id}"
    headers = {
        "Authorization": f"Bearer {BRSAPI_KEY}",
        "User-Agent": "Mozilla/5.0"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        status = response.status_code
        if status != 200:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در BrsApi (نوری):\nآدرس: {url}\nخطا: {status} - {response.text.strip()}")
            return None
        return response.json()
    except Exception as e:
        bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در اتصال به داده BrsApi:\nآدرس: {url}\nخطا: {e}")
        return None

# --- بررسی باز یا بسته بودن بازار
def is_market_open():
    now = datetime.now().time()
    return (dtime(9, 0) <= now <= dtime(12, 30)) or (dtime(13, 30) <= now <= dtime(15, 0))

# --- چک بازار و هشدار
def check_market_and_notify():
    global last_check_time, market_open
    symbol_id = "46602927695631802"

    while True:
        now = datetime.now()
        open_status = is_market_open()

        if selected_source == "brsapi":
            data = get_brsapi_data(symbol_id)
        else:
            data = None

        if data is None:
            if open_status:
                bot.send_message(chat_id=CHAT_ID, text="🚨 خطا در دریافت داده از منبع انتخابی!")
        else:
            if open_status and not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 شروع بازار - من فعال شدم.")
            elif not open_status and market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 پایان بازار - من خاموش شدم.")

        last_check_time = now
        time.sleep(120)

# --- فرمان‌ها
def start(update, context):
    update.message.reply_text("سلام! ربات نوری فعال است.")

def status(update, context):
    msg = f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {'باز' if market_open else 'بسته'}\n📡 منبع داده: {selected_source}"
    update.message.reply_text(msg)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    update.message.reply_text("♻️ ربات ریست شد.")

def select_source(update, context):
    keyboard = [
        [InlineKeyboardButton("BrsApi", callback_data='source_brsapi')],
        [InlineKeyboardButton("Sahamyab (غیرفعال)", callback_data='source_sahamyab')],
        [InlineKeyboardButton("Codal (غیرفعال)", callback_data='source_codal')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("✅ لطفاً منبع داده را انتخاب کنید:", reply_markup=reply_markup)

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("🎯 وضعیت", callback_data='status')],
        [InlineKeyboardButton("♻️ ریست", callback_data='reset')],
        [InlineKeyboardButton("📡 منبع داده", callback_data='select_source')],
    ]
    update.message.reply_text("📋 لطفاً یک گزینه را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

def button(update, context):
    global selected_source
    query = update.callback_query
    query.answer()
    data = query.data

    if data == 'status':
        status(query, context)
    elif data == 'reset':
        reset(query, context)
    elif data == 'select_source':
        select_source(query, context)
    elif data.startswith('source_'):
        selected_source = data.split('_')[1]
        query.edit_message_text(text=f"✅ منبع تغییر کرد به: {selected_source}")
    else:
        query.edit_message_text("❓ گزینه نامعتبر")

# --- هندلرها
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("reset", reset))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

# --- Webhook
@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/", methods=["GET"])
def home():
    return "ربات نوری فعال است."

# --- اجرا
if __name__ == "__main__":
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
