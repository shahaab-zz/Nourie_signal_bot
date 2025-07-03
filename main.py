import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

# تنظیمات ربات
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
bot = Bot(token=TOKEN)

# داده‌های وضعیت
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)
market_open = False
last_check_time = None
data_source = "brsapi"  # پیش‌فرض

# بررسی ساعت بازار
def is_market_open():
    now = datetime.now().time()
    return dtime(9, 0) <= now <= dtime(12, 30)

# گرفتن داده از منبع brsapi
def get_brsapi_data():
    try:
        url = "https://brsapi.ir/Api/Tsetmc/AllSymbols.php"
        params = {
            "key": "Free5VSOryjPh51wo8o6tltHkv0DhsE8",
            "type": "1"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        symbol_data = next((item for item in data if item["l18"] == "نوری"), None)
        return symbol_data
    except Exception as e:
        return {"error": str(e), "url": response.url if 'response' in locals() else url}

# بررسی بازار و ارسال پیام
def check_market_and_notify():
    global market_open, last_check_time
    while True:
        now = datetime.now()
        open_status = is_market_open()
        last_check_time = now

        if open_status:
            if not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
            result = get_brsapi_data() if data_source == "brsapi" else None
            if not result or result.get("error"):
                error_text = (
                    f"🚨 خطا در اتصال به داده BrsApi:\n"
                    f"آدرس: {result.get('url') if result else 'N/A'}\n"
                    f"خطا: {result.get('error') if result else 'نامشخص'}"
                )
                bot.send_message(chat_id=CHAT_ID, text=error_text)
        else:
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")

        time.sleep(120)

# دستورات تلگرام
def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.")

def status(update, context):
    global last_check_time
    now_status = is_market_open()
    response = f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {'باز' if now_status else 'بسته'}\n📡 منبع داده: {data_source}"
    if data_source == "brsapi":
        result = get_brsapi_data()
        if not result or result.get("error"):
            response += f"\n🚨 خطا: {result.get('error')}\n🌐 URL: {result.get('url')}"
    context.bot.send_message(chat_id=update.effective_chat.id, text=response)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="♻️ ربات ریست شد.")

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("♻️ ریست /reset", callback_data='reset')],
        [InlineKeyboardButton("منبع: brsapi ✅", callback_data='brsapi')],
        [InlineKeyboardButton("منبع: sahamyab ❌", callback_data='sahamyab')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("یک گزینه انتخاب کنید:", reply_markup=reply_markup)

def button(update, context):
    global data_source
    query = update.callback_query
    query.answer()
    cmd = query.data
    if cmd == 'status':
        status(update, context)
    elif cmd == 'reset':
        reset(update, context)
    elif cmd in ['brsapi', 'sahamyab']:
        data_source = cmd
        context.bot.send_message(chat_id=query.message.chat_id, text=f"📡 منبع فعال تغییر کرد به: {cmd}")
    else:
        context.bot.send_message(chat_id=query.message.chat_id, text="دستور نامعتبر.")

# هندلرها
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

# Webhook
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# اجرا
if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
