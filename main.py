import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters
from datetime import datetime, time as dtime

# =========================
# تنظیمات توکن و آیدی تلگرام
# =========================
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

# =========================
# متغیرهای عمومی
# =========================
last_check_time = None
market_open = False
current_source = "brsapi"  # منبع پیش‌فرض

# =========================
# تابع بررسی باز بودن بازار
# =========================
def is_market_open():
    now = datetime.now().time()
    return dtime(9, 0) <= now <= dtime(12, 30)

# =========================
# دریافت داده از BrsApi
# =========================
def get_brsapi_data():
    try:
        url = "https://brsapi.ir/Api/Tsetmc/AllSymbols.php"
        params = {
            "key": "Free5VSOryjPh51wo8o6tltHkv0DhsE8",
            "type": "1"
        }
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        try:
            data = response.json()
        except ValueError:
            return {"error": "پاسخ JSON معتبری نبود", "url": response.url}

        symbol_data = next((item for item in data if item.get("l18") == "نوری"), None)
        if not symbol_data:
            return {"error": "❌ سهم نوری در داده‌ها پیدا نشد", "url": response.url}

        return symbol_data

    except requests.exceptions.HTTPError as e:
        return {"error": f"خطای HTTP: {e}", "url": url}
    except requests.exceptions.ConnectionError as e:
        return {"error": f"اتصال برقرار نشد: {e}", "url": url}
    except requests.exceptions.Timeout:
        return {"error": "⏱️ خطای Timeout در دریافت پاسخ", "url": url}
    except Exception as e:
        return {"error": f"خطای ناشناخته: {e}", "url": url}

# =========================
# چک خودکار بازار
# =========================
def check_market_and_notify():
    global last_check_time, market_open

    while True:
        now = datetime.now()
        open_status = is_market_open()
        last_check_time = now

        if open_status and not market_open:
            market_open = True
            bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (بازار باز شد)")
        elif not open_status and market_open:
            market_open = False
            bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (بازار بسته شد)")

        # در زمان باز بودن بازار فقط چک کنیم
        if open_status:
            data = get_brsapi_data()
            if isinstance(data, dict) and "error" in data:
                bot.send_message(
                    chat_id=CHAT_ID,
                    text=f"🚨 خطا در اتصال به داده BrsApi:\nآدرس: {data.get('url')}\nخطا: {data.get('error')}"
                )

        time.sleep(120)

# =========================
# هندلرهای تلگرام
# =========================
def start(update, context):
    show_menu(update)

def show_menu(update):
    keyboard = [
        [InlineKeyboardButton("📊 وضعیت /status", callback_data='status')],
        [InlineKeyboardButton("🔁 ریست /reset", callback_data='reset')],
        [InlineKeyboardButton("📡 منبع داده: brsapi (فعال)", callback_data='source_brsapi')],
        [InlineKeyboardButton("📡 منبع sahamyab (غیرفعال)", callback_data='source_sahamyab')],
        [InlineKeyboardButton("📡 منبع rahavard365 (غیرفعال)", callback_data='source_rahavard')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    bot.send_message(chat_id=update.effective_chat.id, text="منوی اصلی:", reply_markup=reply_markup)

def status(update, context):
    now = datetime.now()
    open_status = is_market_open()
    source = current_source

    msg = f"🕓 آخرین بررسی: {now}\n"
    msg += f"📈 بازار: {'باز' if open_status else 'بسته'}\n"
    msg += f"📡 منبع داده: {source}\n"

    if source == "brsapi":
        data = get_brsapi_data()
        if isinstance(data, dict) and "error" in data:
            msg += f"🚨 خطا: {data.get('error')}\n🌐 URL: {data.get('url')}"

    context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def reset(update, context):
    global market_open, last_check_time
    market_open = False
    last_check_time = None
    context.bot.send_message(chat_id=update.effective_chat.id, text="✅ ربات ریست شد.")

def button(update, context):
    global current_source
    query = update.callback_query
    query.answer()

    if query.data == 'status':
        status(query, context)
    elif query.data == 'reset':
        reset(query, context)
    elif query.data == 'source_brsapi':
        current_source = "brsapi"
        query.edit_message_text("✅ منبع داده به brsapi تغییر کرد.")
    else:
        query.edit_message_text("❌ این منبع هنوز پشتیبانی نمی‌شود.")

def handle_text(update, context):
    show_menu(update)

# =========================
# فل ask Webhook
# =========================
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# =========================
# راه‌اندازی بات
# =========================
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

# =========================
# اجرای Flask و Thread مانیتورینگ
# =========================
if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
