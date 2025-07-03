import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

# توکن و آیدی
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# تنظیمات
selected_source = "brsapi"
last_check_time = None
market_open = False

def is_market_open():
    now = datetime.now().time()
    return dtime(9, 0) <= now <= dtime(12, 30)

def fetch_data_brsapi():
    try:
        url = "https://brsapi.ir/Api/Tsetmc/AllSymbols.php"
        params = {
            "key": "Free5VSOryjPh51wo8o6tltHkv0DhsE8",
            "type": "1"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        all_data = response.json()

        for item in all_data:
            if item.get("InsCode") == "46602927695631802":
                return item

        raise ValueError("سهم نوری در داده موجود نیست.")
    except Exception as e:
        error = str(e)
        full_url = f"{url}?key={params['key']}&type={params['type']}"
        bot.send_message(
            chat_id=CHAT_ID,
            text=f"""🚨 خطا در اتصال به داده {selected_source}:
خطا: {error}
🌐 URL: {full_url}"""
        )
        return None

def check_market_and_notify():
    global last_check_time, market_open
    notified_error = False

    while True:
        now = datetime.now()
        open_status = is_market_open()
        last_check_time = now

        if open_status:
            if not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
            data = fetch_data_brsapi()
            if data:
                notified_error = False
            elif not notified_error:
                notified_error = True
        else:
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")

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
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.\nاز /menu برای مشاهده گزینه‌ها استفاده کن.")

def status(update, context):
    global last_check_time, market_open, selected_source
    try:
        _ = fetch_data_brsapi()
        ok = "✅ اتصال برقرار است."
    except:
        ok = "❌ اتصال برقرار نیست."
    status_text = f"""🕓 آخرین بررسی: {last_check_time}
📈 بازار: {'باز' if market_open else 'بسته'}
📡 منبع داده: {selected_source}
{ok}"""
    context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="✅ ربات ریست شد.")

def button(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    if data == 'start':
        start(update, context)
    elif data == 'status':
        status(update, context)
    elif data == 'reset':
        reset(update, context)

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("وضعیت 🟡", callback_data='status')],
        [InlineKeyboardButton("ریست ♻️", callback_data='reset')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('📋 گزینه‌ها:', reply_markup=reply_markup)

# هندلرها
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(CommandHandler('menu', menu))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
