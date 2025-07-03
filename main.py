import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

app = Flask(__name__)

# اطلاعات توکن و چت‌آی‌دی
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

bot = Bot(token=TOKEN)
selected_source = "brsapi"

last_check_time = None
market_open = False

def fetch_data_brsapi():
    try:
        url = "https://brsapi.ir/Api/Tsetmc/AllSymbols.php"
        params = {
            "key": "Free5VSOryjPh51wo8o6tltHkv0DhsE8",
            "type": "1"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data_list = response.json()
        for item in data_list:
            if item.get("symbol") == "نوری":
                return item
        return None
    except Exception as e:
        bot.send_message(
            chat_id=CHAT_ID,
            text=(
                f"🚨 خطا در اتصال به داده {selected_source}:\n"
                f"خطا: {str(e)}\n"
                f"🌐 URL: {url}?key={params['key']}&type={params['type']}"
            )
        )
        return None

def is_market_open():
    now = datetime.now().time()
    return dtime(9, 0) <= now <= dtime(12, 30)

def check_market_and_notify():
    global last_check_time, market_open
    while True:
        now = datetime.now()
        last_check_time = now
        open_status = is_market_open()
        data = fetch_data_brsapi()

        if open_status and not market_open:
            market_open = True
            bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (بازار باز است)")
        elif not open_status and market_open:
            market_open = False
            bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (بازار بسته شد)")

        time.sleep(120)

@app.route("/", methods=["GET"])
def home():
    return "ربات نوری فعال است."

@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

def start(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت", callback_data='status')],
        [InlineKeyboardButton("🔁 ریست", callback_data='reset')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text="یک گزینه را انتخاب کنید:", reply_markup=reply_markup)

def status(update, context):
    global last_check_time, market_open, selected_source
    data = fetch_data_brsapi()
    ok = "✅ اتصال برقرار است." if data else "❌ اتصال برقرار نیست."
    status_text = f"""🕓 آخرین بررسی: {last_check_time}
📈 بازار: {'باز' if market_open else 'بسته'}
📡 منبع داده: {selected_source}
{ok}"""
    context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="ریست شد.")

def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'status':
        status(query, context)
    elif query.data == 'reset':
        reset(query, context)

def menu(update, context):
    start(update, context)

# راه‌اندازی دیسپچر
from telegram.ext import Updater
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("reset", reset))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, menu))
dispatcher.add_handler(CallbackQueryHandler(button))

# شروع برنامه
if __name__ == "__main__":
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
