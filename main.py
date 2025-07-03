import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

app = Flask(__name__)

# 🔐 اطلاعات توکن و چت‌آیدی اینجا قرار می‌گیرد (نه به عنوان Environment)
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

bot = Bot(token=TOKEN)
current_source = "brsapi"
last_check_time = None
market_open = False

def get_brsapi_data():
    try:
        url = "https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key=Free5VSOryjPh51wo8o6tltHkv0DhsE8&type=1"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
        for item in data:
            if item.get("InsCode") == "46602927695631802":
                return item
        return None
    except Exception as e:
        return {
            "error": str(e),
            "url": url
        }

def is_market_open():
    now = datetime.now().time()
    return dtime(9, 0) <= now <= dtime(12, 30) or dtime(13, 30) <= now <= dtime(15, 0)

def check_market_and_notify():
    global last_check_time, market_open
    notified_error = False

    while True:
        now = datetime.now()
        open_status = is_market_open()
        last_check_time = now

        if open_status:
            if not market_open:
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
            market_open = True

            result = get_brsapi_data()
            if isinstance(result, dict) and "error" in result:
                bot.send_message(chat_id=CHAT_ID, text=(
                    f"🚨 خطا در اتصال به داده BrsApi:\n"
                    f"آدرس: {result['url']}\n"
                    f"خطا: {result['error']}"
                ))
        else:
            if market_open:
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")
            market_open = False

        time.sleep(120)

@app.route("/", methods=["GET"])
def home():
    return "ربات فعال است."

@app.route("/", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

def start(update, context):
    menu(update, context)

def status(update, context):
    global last_check_time
    try:
        result = get_brsapi_data()
        msg = f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {'باز' if market_open else 'بسته'}\n📡 منبع داده: {current_source}"
        if isinstance(result, dict) and "error" in result:
            msg += f"\n🚨 خطا: {result['error']}\n🌐 URL: {result['url']}"
        else:
            msg += "\n✅ اتصال موفق!"
        context.bot.send_message(chat_id=update.effective_chat.id, text=msg)
    except Exception as e:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"خطا در بررسی وضعیت: {e}")

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="♻️ ربات ریست شد.")

def menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت", callback_data='status')],
        [InlineKeyboardButton("♻️ ریست", callback_data='reset')],
        [InlineKeyboardButton("🔘 brsapi (فعال)", callback_data='source_brsapi')],
        [InlineKeyboardButton("🔘 sahamyab (غیرفعال)", callback_data='source_sahamyab')],
        [InlineKeyboardButton("🔘 codal (غیرفعال)", callback_data='source_codal')],
        [InlineKeyboardButton("🔘 tsetmc (غیرفعال)", callback_data='source_tsetmc')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text("منو را انتخاب کن:", reply_markup=reply_markup)

def button(update, context):
    global current_source
    query = update.callback_query
    query.answer()

    if query.data == 'status':
        status(update, context)
    elif query.data == 'reset':
        reset(update, context)
    elif query.data == 'source_brsapi':
        current_source = "brsapi"
        query.edit_message_text("✅ منبع داده به brsapi تغییر کرد.")
    else:
        query.edit_message_text("❌ این منبع هنوز پشتیبانی نمی‌شود.")

from telegram.ext import Updater

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("status", status))
dispatcher.add_handler(CommandHandler("reset", reset))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, menu))
dispatcher.add_handler(CallbackQueryHandler(button))

if __name__ == "__main__":
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
