import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

# ----- اطلاعات مهم -----
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
API_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"  # از BRSAPI

# ------------------------

app = Flask(__name__)
bot = Bot(token=TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# وضعیت‌های برنامه
last_check_time = None
market_open = False
selected_source = "brsapi"  # منبع پیش‌فرض

# ------------------- توابع کمکی -------------------

def is_market_open():
    now = datetime.now().time()
    return dtime(9, 0) <= now <= dtime(12, 30)

# ------------------- تابع وضعیت (اصلاح‌شده) -------------------

def status(update, context):
    global last_check_time, market_open, selected_source

    last_check_time_str = last_check_time if last_check_time else "هنوز بررسی نشده"
    market_status_str = 'باز' if market_open else 'بسته'

    if selected_source == "brsapi":
        url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={API_KEY}&type=1"
    else:
        url = None

    if url is None:
        context.bot.send_message(chat_id=update.effective_chat.id, text="📡 منبع داده انتخاب نشده است.")
        return

    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        data_text = resp.text

        status_text = (f"🕓 آخرین بررسی: {last_check_time_str}\n"
                       f"📈 بازار: {market_status_str}\n"
                       f"📡 منبع داده: {selected_source}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

        context.bot.send_document(chat_id=update.effective_chat.id,
                                  document=data_text.encode('utf-8'),
                                  filename="market_data.json")

    except Exception as e:
        error_text = (f"🚨 خطا در اتصال به داده {selected_source}:\n"
                      f"آدرس: {url}\n"
                      f"خطا: {str(e)}")
        context.bot.send_message(chat_id=update.effective_chat.id, text=error_text)

# ------------------- سایر توابع -------------------

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.\nبرای استفاده، منو را باز کنید.")

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="✅ تنظیمات ربات ریست شد.")

def select_source(update, context):
    query = update.callback_query
    global selected_source
    selected_source = query.data
    query.answer()
    query.edit_message_text(text=f"📡 منبع داده انتخاب‌شده: {selected_source}")

def menu(update, context):
    buttons = [
        [InlineKeyboardButton("📊 وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("♻️ ریست /reset", callback_data='reset')],
        [InlineKeyboardButton("منبع: brsapi (فعال)", callback_data='brsapi')],
        [InlineKeyboardButton("منبع: sahamyab (غیرفعال)", callback_data='sahamyab')],
    ]
    reply_markup = InlineKeyboardMarkup(buttons)
    update.message.reply_text("یک گزینه انتخاب کنید:", reply_markup=reply_markup)

def button_handler(update, context):
    query = update.callback_query
    if query.data == 'status':
        status(update, context)
    elif query.data == 'reset':
        reset(update, context)
    elif query.data in ['brsapi', 'sahamyab']:
        select_source(update, context)

# ------------------- Flask Route -------------------

@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# ------------------- هندلرها -------------------

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("reset", reset))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

# ------------------- اجرا -------------------

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
