import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater
from datetime import datetime, time as dtime

# تنظیمات اصلی
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SELECTED_SOURCE = "brsapi"
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN)
app = Flask(__name__)

last_check_time = None
market_open = False
cached_data = None
cached_time = None

# بررسی زمان بازار
def is_market_open():
    now = datetime.now().time()
    return (dtime(9, 0) <= now <= dtime(12, 30)) or (dtime(13, 30) <= now <= dtime(15, 0))

# دریافت داده از BRSAPI
def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

# بررسی بازار و ارسال نوتیفیکیشن
def check_market_and_notify():
    global last_check_time, market_open, cached_data, cached_time
    while True:
        now = datetime.now()
        open_status = is_market_open()
        last_check_time = now

        if open_status:
            data, url, error = get_brsapi_data()
            if error:
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"🚨 خطا در اتصال به داده {SELECTED_SOURCE}:\nخطا: {error}\n\n🌐 URL: {url}"
                )
            if not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
        else:
            if not market_open:
                time.sleep(120)
                continue
            market_open = False
            cached_data, cached_time = get_brsapi_data()
            bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")
        time.sleep(120)

# توابع مشترک برای گرفتن chat_id ایمن
def get_chat_id(update):
    if hasattr(update, 'effective_chat') and update.effective_chat:
        return update.effective_chat.id
    elif hasattr(update, 'chat'):
        return update.chat.id
    elif hasattr(update, 'message') and hasattr(update.message, 'chat'):
        return update.message.chat.id
    else:
        return CHAT_ID  # fallback

# روت اصلی وب‌هوک
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# دستورات اصلی
def start(update, context):
    chat_id = get_chat_id(update)
    context.bot.send_message(chat_id=chat_id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

def status(update, context):
    global last_check_time
    chat_id = get_chat_id(update)
    open_status = is_market_open()
    source = SELECTED_SOURCE
    market = 'باز' if open_status else 'بسته'
    data, url, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"🚨 خطا در اتصال به داده {source}:\nخطا: {error}\n🌐 URL: {url}")
    else:
        context.bot.send_message(chat_id=chat_id, text="✅ اتصال برقرار است.")
    context.bot.send_message(chat_id=chat_id, text=f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {market}\n📡 منبع داده: {source}")

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    chat_id = get_chat_id(update)
    context.bot.send_message(chat_id=chat_id, text="✅ ربات ریست شد.")

# هندل دکمه‌ها
def button(update, context):
    try:
        query = update.callback_query
        query.answer()
        # ارسال کل Update تا از effective_chat استفاده بشه
        if query.data == 'status':
            status(update, context)
        elif query.data == 'reset':
            reset(update, context)
        elif query.data == 'start':
            start(update, context)
        else:
            query.edit_message_text(text="دستور نامعتبر")
    except Exception as e:
        query.edit_message_text(text=f"⚠️ خطا در اجرای دستور: {e}")
        print(f"[button] ERROR: {e}")

# منوی دکمه‌ها
def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت بازار (Status)", callback_data='status')],
        [InlineKeyboardButton("🔄 ریست ربات (Reset)", callback_data='reset')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    chat_id = get_chat_id(update)
    context.bot.send_message(chat_id=chat_id, text='یک گزینه انتخاب کنید:', reply_markup=reply_markup)

# هندل پیام‌های متنی
def handle_text(update, context):
    show_menu(update, context)

# راه‌اندازی Dispatcher
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CommandHandler('reset', reset))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

# اجرای برنامه
if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
