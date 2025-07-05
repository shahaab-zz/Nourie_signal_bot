import os
import time
import threading
import requests
import pandas as pd
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater
from datetime import datetime, time as dtime
import pytz
import json

# تنظیمات اصلی
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SELECTED_SOURCE = "brsapi"
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN)
app = Flask(__name__)

last_check_time = None
market_open = False
check_thread_running = True

# تنظیم منطقه زمانی به وقت ایران
iran_tz = pytz.timezone("Asia/Tehran")

def get_current_tehran_time():
    return datetime.now(iran_tz)

# بررسی زمان بازار
def is_market_open():
    now = get_current_tehran_time().time()
    return (dtime(9, 0) <= now <= dtime(12, 30)) or (dtime(13, 30) <= now <= dtime(15, 0))

# دریافت داده از BRSAPI
def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 429:
            return None, url, "🔴 محدودیت مصرف روزانه بررسAPI به پایان رسیده."
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, f"خطا در اتصال به منبع: {str(e)}"

# بررسی سیگنال ورود
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

                message = "📊 بررسی شرایط سیگنال ورود نوری:\n"
                message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
                message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
                message += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})"

                return cond1 and cond2 and cond3, message

        return False, "❌ نماد نوری در داده‌ها یافت نشد.\n⛔ بررسی سایر شرط‌ها امکان‌پذیر نیست."
    except Exception as e:
        return False, f"❌ خطا در تحلیل داده: {str(e)}"

# بررسی بازار و سیگنال به‌صورت خودکار
def check_market_and_notify():
    global last_check_time, market_open, check_thread_running
    while check_thread_running:
        now = get_current_tehran_time()
        last_check_time = now
        open_status = is_market_open()

        if open_status:
            data, url, error = get_brsapi_data()
            if error:
                bot.send_message(chat_id=CHAT_ID, text=f"🚨 {error}\n🌐 {url}")
            else:
                signal, explanation = check_nouri_signal_verbose(data)
                if signal:
                    bot.send_message(chat_id=CHAT_ID, text="🚀 سیگنال ورود به نوری شناسایی شد!")
        if open_status and not market_open:
            market_open = True
            bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
        elif not open_status and market_open:
            market_open = False
            bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")

        time.sleep(600)  # هر ۱۰ دقیقه

# بررسی دستی
def manual_check(update, context):
    chat_id = update.effective_chat.id
    data, url, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ {error}\n🌐 {url}")
        return
    signal, explanation = check_nouri_signal_verbose(data)
    context.bot.send_message(chat_id=chat_id, text=explanation)
    if signal:
        context.bot.send_message(chat_id=chat_id, text="✅ سیگنال ورود تأیید شد.")
    else:
        context.bot.send_message(chat_id=chat_id, text="📉 هنوز سیگنال ورود کامل نیست.")

# ارسال فایل داده
def send_json(update, context):
    data, url, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ {error}")
        return
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    file_path = "/tmp/nouri_data.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json_str)
    context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(file_path), filename="nouri_data.json")

def send_excel(update, context):
    data, url, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ {error}")
        return
    nouri_data = [item for item in data if item.get("l18") == "نوری"]
    if not nouri_data:
        context.bot.send_message(chat_id=update.effective_chat.id, text="❌ نماد نوری یافت نشد.")
        return
    df = pd.DataFrame(nouri_data)
    file_path = "/tmp/nouri_data.xlsx"
    df.to_excel(file_path, index=False)
    context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(file_path), filename="nouri_data.xlsx")

# کنترل‌ها
def stop_check(update, context):
    global check_thread_running
    check_thread_running = False
    context.bot.send_message(chat_id=update.effective_chat.id, text="⏹ بررسی خودکار متوقف شد.")

def resume_check(update, context):
    global check_thread_running
    if not check_thread_running:
        check_thread_running = True
        threading.Thread(target=check_market_and_notify, daemon=True).start()
        context.bot.send_message(chat_id=update.effective_chat.id, text="▶️ بررسی خودکار دوباره فعال شد.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="✅ بررسی خودکار از قبل فعال بوده است.")

def status(update, context):
    global last_check_time
    open_status = is_market_open()
    market = 'باز' if open_status else 'بسته'
    now = last_check_time if last_check_time else get_current_tehran_time()
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"🕓 آخرین بررسی: {now}\n📈 بازار: {market}\n📡 منبع داده: {SELECTED_SOURCE}")

def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')],
        [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')],
        [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')],
        [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')],
        [InlineKeyboardButton("📥 دریافت فایل JSON", callback_data='download_json')],
        [InlineKeyboardButton("📊 دریافت Excel نوری", callback_data='download_excel')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text="لطفاً یک گزینه را انتخاب کنید:", reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'check_signal':
        manual_check(update, context)
    elif query.data == 'status':
        status(update, context)
    elif query.data == 'stop':
        stop_check(update, context)
    elif query.data == 'resume':
        resume_check(update, context)
    elif query.data == 'download_json':
        send_json(update, context)
    elif query.data == 'download_excel':
        send_excel(update, context)

def handle_text(update, context):
    show_menu(update, context)

@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

# راه‌اندازی ربات
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
dispatcher.add_handler(CommandHandler('status', status))

# شروع بررسی خودکار
if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
