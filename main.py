import os
import time
import threading
import requests
from datetime import datetime, time as dtime
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters

app = Flask(__name__)

# 🔐 توکن و آیدی مستقیم در کد (امن برای پروژه شخصی)
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
BRSAPI_KEY = os.environ.get("BRSAPI_KEY")  # فقط این در env باقی بمونه

bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

data_source = "brsapi"
market_open = False
last_check_time = None

def is_market_open():
    now = datetime.now().time()
    morning_start = dtime(9, 0)
    morning_end = dtime(12, 30)
    afternoon_start = dtime(13, 30)
    afternoon_end = dtime(15, 0)
    return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

def get_brsapi_data():
    try:
        url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
        response = requests.get(url, timeout=10)

        if response.status_code != 200:
            raise requests.HTTPError(f"کد وضعیت: {response.status_code}")

        data_list = response.json()
        if not isinstance(data_list, list):
            raise ValueError("پاسخ BRSAPI معتبر نیست.")

        for item in data_list:
            if item.get("Symbol") == "نوری":
                return {
                    "name": item.get("Name", "ناموجود"),
                    "last": item.get("Last"),
                    "close": item.get("Close"),
                    "symbol": item.get("Symbol")
                }

        raise ValueError("نماد 'نوری' در لیست یافت نشد.")

    except Exception as e:
        return {
            "error": str(e),
            "source_url": url
        }

def get_selected_data():
    if data_source == "brsapi":
        return get_brsapi_data()
    return {"error": "منبع داده تعریف نشده."}

def check_market_and_notify():
    global market_open, last_check_time

    already_notified_closed = False

    while True:
        now = datetime.now()
        open_status = is_market_open()
        data = get_selected_data()
        last_check_time = now

        if open_status:
            if not market_open:
                market_open = True
                already_notified_closed = False
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (بازار باز است)")

            if "error" in data:
                msg = f"🚨 خطا در اتصال به داده BrsApi:\nآدرس: {data.get('source_url')}\nخطا: {data['error']}"
                bot.send_message(chat_id=CHAT_ID, text=msg)

        else:
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 بازار بسته شد. من غیرفعالم.")
            elif not already_notified_closed:
                already_notified_closed = True
                # فقط یک بار در زمان بسته بودن

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
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت", callback_data='status')],
        [InlineKeyboardButton("🔄 ریست", callback_data='reset')],
        [InlineKeyboardButton("🎯 منبع: BrsApi (فعال)", callback_data='source_brsapi')],
        [InlineKeyboardButton("🔘 منبع: Sahamyab (غیرفعال)", callback_data='source_sahamyab')],
        [InlineKeyboardButton("🔘 منبع: TSETMC (غیرفعال)", callback_data='source_tsetmc')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("یک گزینه انتخاب کنید:", reply_markup=reply_markup)

def status(update, context):
    now = datetime.now()
    text = f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {'باز' if market_open else 'بسته'}\n📡 منبع داده: {data_source}"

    data = get_selected_data()
    if "error" in data:
        text += f"\n🚨 خطا: {data['error']}\n🌐 URL: {data.get('source_url')}"
    else:
        text += f"\n\n📍 نماد: {data['symbol']}\n🔹 نام: {data['name']}\n💵 آخرین: {data['last']}\n🔚 پایانی: {data['close']}"

    context.bot.send_message(chat_id=update.effective_chat.id, text=text)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="ریست شد.")

def button(update, context):
    global data_source
    query = update.callback_query
    query.answer()

    if query.data == 'status':
        status(update, context)
    elif query.data == 'reset':
        reset(update, context)
    elif query.data.startswith('source_'):
        selected = query.data.replace('source_', '')
        data_source = selected
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ منبع داده تغییر کرد: {data_source}")
        start(update, context)

def menu(update, context):
    start(update, context)

# ثبت دستورها
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("reset", reset))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))
dispatcher.add_handler(CallbackQueryHandler(button))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
