import os
import time
import threading
import requests
import json
from datetime import datetime, time as dtime
from io import BytesIO
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    Dispatcher, CommandHandler, CallbackQueryHandler,
    MessageHandler, Filters, Updater
)
import pandas as pd

# --- تنظیمات اصلی ---
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SELECTED_SOURCE = "brsapi"
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN)
app = Flask(__name__)

last_check_time = None
market_open = False
check_thread_running = True

# --- بررسی زمان بازار ---
def is_market_open():
    now = datetime.utcnow().time()  # زمان UTC، اگر لازم بود به IR تبدیل کن
    return (dtime(5, 30) <= now <= dtime(9, 0)) or (dtime(9, 0) <= now <= dtime(10, 30))

# --- دریافت داده از BRSAPI ---
def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

# --- بررسی سیگنال نوری با جزئیات ---
def check_nouri_signal_verbose(data):
    try:
        nouri = next((item for item in data if item.get("l18") == "نوری"), None)
        if not nouri:
            return False, "📊 بررسی شرایط سیگنال ورود نوری:\n❌ نماد نوری در داده‌ها یافت نشد.\n⛔ بررسی سایر شرط‌ها امکان‌پذیر نیست."

        vol = int(nouri.get("tvol", 0))
        buy_ind = int(nouri.get("Buy_I_Volume", 0))
        sell_ind = int(nouri.get("Sell_I_Volume", 0))
        last = float(nouri.get("pl", 0))
        close = float(nouri.get("py", 0))

        cond1 = vol > 500000
        cond2 = last > close
        cond3 = buy_ind > sell_ind
        all_pass = cond1 and cond2 and cond3

        message = "📊 بررسی شرایط سیگنال ورود نوری:\n"
        message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
        message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
        message += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"

        return all_pass, message
    except Exception as e:
        return False, f"❌ خطا در پردازش اطلاعات: {str(e)}"

# --- بررسی خودکار بازار و سیگنال ---
def check_market_and_notify():
    global last_check_time, market_open, check_thread_running
    while check_thread_running:
        now = datetime.utcnow()
        last_check_time = now
        open_status = is_market_open()

        if open_status:
            data, url, error = get_brsapi_data()
            if error:
                bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}")
            else:
                signal, _ = check_nouri_signal_verbose(data)
                if signal:
                    bot.send_message(chat_id=CHAT_ID, text="🚀 سیگنال ورود به نوری شناسایی شد!")

            if not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
        else:
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")

        time.sleep(120)

# --- بررسی دستی سیگنال ---
def manual_check(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در اتصال: {error}")
        return

    signal, explanation = check_nouri_signal_verbose(data)
    context.bot.send_message(chat_id=chat_id, text=explanation)
    if signal:
        context.bot.send_message(chat_id=chat_id, text="🚀 سیگنال ورود تایید شد!")
    else:
        context.bot.send_message(chat_id=chat_id, text="📉 هنوز سیگنال ورود کامل نیست.")

# --- توقف و ادامه بررسی خودکار ---
def stop_check(update, context):
    global check_thread_running
    check_thread_running = False
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="⏹ بررسی خودکار متوقف شد.")

def resume_check(update, context):
    global check_thread_running
    if not check_thread_running:
        check_thread_running = True
        threading.Thread(target=check_market_and_notify, daemon=True).start()
        context.bot.send_message(chat_id=update.effective_chat.id, text="▶️ بررسی خودکار دوباره فعال شد.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="✅ بررسی خودکار از قبل فعال بوده است.")

# --- بررسی وضعیت اتصال ---
def status(update, context):
    global last_check_time
    chat_id = update.effective_chat.id
    open_status = is_market_open()
    market = 'باز' if open_status else 'بسته'
    data, url, error = get_brsapi_data()

    if error:
        context.bot.send_message(chat_id=chat_id, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}\n🌐 {url}")
    else:
        context.bot.send_message(chat_id=chat_id, text="✅ اتصال برقرار است.")
    context.bot.send_message(chat_id=chat_id, text=f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {market}\n📡 منبع داده: {SELECTED_SOURCE}")

# --- ارسال فایل JSON ---
def download_json(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id

    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت داده‌ها: {error}")
        return

    json_bytes = BytesIO()
    json.dump(data, json_bytes, ensure_ascii=False, indent=2)
    json_bytes.seek(0)

    context.bot.send_document(chat_id=chat_id, document=json_bytes, filename="nouri_data.json", caption="📄 داده‌های JSON دریافت شد.")

# --- ارسال فایل Excel فقط برای نوری ---
def download_nouri_excel(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id

    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت داده‌ها: {error}")
        return

    nouri_data = next((item for item in data if item.get("l18") == "نوری"), None)
    if not nouri_data:
        context.bot.send_message(chat_id=chat_id, text="❌ نماد نوری یافت نشد.")
        return

    df = pd.DataFrame([nouri_data])
    excel_bytes = BytesIO()
    df.to_excel(excel_bytes, index=False)
    excel_bytes.seek(0)

    context.bot.send_document(
        chat_id=chat_id,
        document=excel_bytes,
        filename="nouri_data.xlsx",
        caption="📊 اطلاعات نماد نوری (Excel)"
    )

# --- رابط وب برای اتصال وب‌هوک ---
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# --- دکمه‌ها ---
def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')],
        [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')],
        [InlineKeyboardButton("📥 دریافت کل داده‌ها (JSON)", callback_data='download_json')],
        [InlineKeyboardButton("📈 دریافت اطلاعات نوری (Excel)", callback_data='download_excel')],
        [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')],
        [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="یک گزینه را انتخاب کنید:", reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'check_signal':
        manual_check(update, context)
    elif query.data == 'status':
        status(update, context)
    elif query.data == 'download_json':
        download_json(update, context)
    elif query.data == 'download_excel':
        download_nouri_excel(update, context)
    elif query.data == 'stop':
        stop_check(update, context)
    elif query.data == 'resume':
        resume_check(update, context)
    else:
        query.edit_message_text(text="دستور نامعتبر")

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

def handle_text(update, context):
    show_menu(update, context)

# --- راه‌اندازی ربات ---
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher
dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

# --- شروع ترد بررسی خودکار ---
if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
