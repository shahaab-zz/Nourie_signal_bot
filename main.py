import os
import time
import threading
import requests
import pandas as pd
from flask import Flask, request, send_file
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater
from datetime import datetime, time as dtime
import pytz
import json

# ====== تنظیمات ======
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SELECTED_SOURCE = "brsapi"
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN)
app = Flask(__name__)
tehran = pytz.timezone("Asia/Tehran")

last_check_time = None
market_open = False
check_thread_running = True

# ====== بررسی باز بودن بازار ======
def is_market_open():
    now = datetime.now(tehran).time()
    return dtime(9, 0) <= now <= dtime(12, 30)

# ====== دریافت داده از brsapi ======
def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

# ====== بررسی سیگنال نوری ======
def check_nouri_signal_verbose(data):
    try:
        for item in data:
            if item.get("l18") == "نوری":
                vol = int(item.get("tvol", 0))
                buy_ind = int(item.get("Buy_I_Volume", 0))
                sell_ind = int(item.get("Sell_I_Volume", 0))
                last = float(item.get("pl", 0))
                close = float(item.get("pc", 0))

                cond1 = vol > 500000
                cond2 = last > close
                cond3 = buy_ind > sell_ind

                all_pass = cond1 and cond2 and cond3

                message = "📊 بررسی شرایط سیگنال ورود نوری:\n"
                message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
                message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
                message += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"

                return all_pass, message, item
        return False, "❌ نماد نوری در داده‌ها یافت نشد.\n⛔ بررسی سایر شرط‌ها امکان‌پذیر نیست.", None
    except Exception as e:
        return False, f"❌ خطا در پردازش اطلاعات: {str(e)}", None

# ====== بررسی خودکار بازار ======
def check_market_and_notify():
    global last_check_time, market_open, check_thread_running
    while check_thread_running:
        now = datetime.now(tehran)
        last_check_time = now
        if is_market_open():
            data, url, error = get_brsapi_data()
            if error:
                bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}")
            else:
                signal, msg, _ = check_nouri_signal_verbose(data)
                if signal:
                    bot.send_message(chat_id=CHAT_ID, text="🚀 سیگنال ورود به نوری شناسایی شد!")
            if not market_open:
                market_open = True
                bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
        else:
            if market_open:
                market_open = False
                bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")
        time.sleep(600)

# ====== بررسی دستی ======
def manual_check(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در اتصال: {error}")
        return
    signal, explanation, _ = check_nouri_signal_verbose(data)
    context.bot.send_message(chat_id=chat_id, text=explanation)
    if signal:
        context.bot.send_message(chat_id=chat_id, text="🚀 سیگنال ورود تایید شد!")
    else:
        context.bot.send_message(chat_id=chat_id, text="📉 هنوز سیگنال ورود کامل نیست.")

# ====== توقف و ادامه ======
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
        chat_id = update.effective_chat.id
        context.bot.send_message(chat_id=chat_id, text="▶️ بررسی خودکار دوباره فعال شد.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="✅ بررسی خودکار از قبل فعال بوده است.")

# ====== وضعیت ======
def status(update, context):
    global last_check_time
    chat_id = update.effective_chat.id
    market = 'باز' if is_market_open() else 'بسته'
    data, url, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}\n🌐 {url}")
    else:
        context.bot.send_message(chat_id=chat_id, text="✅ اتصال برقرار است.")
        context.bot.send_message(chat_id=chat_id, text=f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {market}\n📡 منبع داده: {SELECTED_SOURCE}")

# ====== دریافت فایل ======
def download_json(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت JSON: {error}")
        return
    filepath = "/tmp/nouri_data.json"
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    context.bot.send_document(chat_id=chat_id, document=open(filepath, 'rb'))

def download_excel(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت Excel: {error}")
        return
    for item in data:
        if item.get("l18") == "نوری":
            df = pd.DataFrame([item])
            filepath = "/tmp/nouri_data.xlsx"
            df.to_excel(filepath, index=False)
            context.bot.send_document(chat_id=chat_id, document=open(filepath, 'rb'))
            return
    context.bot.send_message(chat_id=chat_id, text="❌ نماد نوری در داده‌ها یافت نشد.")

# ====== منو ======
def start(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')],
        [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')],
        [InlineKeyboardButton("📥 دریافت JSON", callback_data='json')],
        [InlineKeyboardButton("📊 دریافت Excel نوری", callback_data='excel')],
        [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')],
        [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="یک گزینه را انتخاب کنید:", reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    if data == 'check_signal':
        manual_check(query, context)
    elif data == 'stop':
        stop_check(query, context)
    elif data == 'resume':
        resume_check(query, context)
    elif data == 'status':
        status(query, context)
    elif data == 'json':
        download_json(query, context)
    elif data == 'excel':
        download_excel(query, context)
    else:
        query.edit_message_text(text="دستور نامعتبر")

def handle_text(update, context):
    show_menu(update, context)

# ====== Webhook ======
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# ====== اجرا ======
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
