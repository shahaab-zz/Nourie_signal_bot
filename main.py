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
TOKEN = "توکن ربات شما"
CHAT_ID = "آیدی شما"
SELECTED_SOURCE = "brsapi"
BRSAPI_KEY = "کلید BRSAPI شما"

bot = Bot(token=TOKEN)
app = Flask(__name__)
last_check_time = None
market_open = False
check_thread_running = True

# تنظیم ساعت ایران
iran_tz = pytz.timezone("Asia/Tehran")

def now_tehran():
    return datetime.now(iran_tz)

# بررسی زمان بازار
def is_market_open():
    now = now_tehran().time()
    return (dtime(9, 0) <= now <= dtime(12, 30)) or (dtime(13, 30) <= now <= dtime(15, 0))

# دریافت داده از BRSAPI
def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 429:
            return None, url, "محدودیت روزانه BRSAPI"
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

# بررسی سیگنال ورود برای نماد نوری با جزئیات
def check_nouri_signal_verbose(data):
    try:
        for item in data:
            if item.get("l18") == "نوری":
                vol = int(item.get("tvol", 0))
                buy_ind = int(item.get("Buy_I_Volume", 0))
                sell_ind = int(item.get("Sell_I_Volume", 0))
                last = float(item.get("pl", 0))
                close = float(item.get("py", 0))

                cond1 = vol > 500000
                cond2 = last > close
                cond3 = buy_ind > sell_ind

                message = "📊 بررسی شرایط سیگنال ورود نوری:\n"
                message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
                message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
                message += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"

                all_pass = cond1 and cond2 and cond3
                return all_pass, message
        return False, "📊 بررسی شرایط سیگنال ورود نوری:\n❌ نماد نوری در داده‌ها یافت نشد.\n⛔ بررسی سایر شرط‌ها امکان‌پذیر نیست."
    except Exception as e:
        return False, f"❌ خطا در پردازش اطلاعات: {str(e)}"

# بررسی خودکار بازار و ارسال سیگنال
def check_market_and_notify():
    global last_check_time, market_open, check_thread_running
    while check_thread_running:
        now = now_tehran()
        last_check_time = now
        open_status = is_market_open()

        if open_status:
            data, url, error = get_brsapi_data()
            if error:
                if "محدودیت" in error:
                    bot.send_message(chat_id=CHAT_ID, text="🚫 محدودیت روزانه BRSAPI فرا رسیده. بررسی متوقف شد.")
                    check_thread_running = False
                    break
                else:
                    bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}")
            else:
                signal, msg = check_nouri_signal_verbose(data)
                if signal:
                    bot.send_message(chat_id=CHAT_ID, text="🚀 سیگنال ورود به نوری شناسایی شد!")
        if open_status and not market_open:
            market_open = True
            bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)")
        elif not open_status and market_open:
            market_open = False
            bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")
        time.sleep(600)  # هر 10 دقیقه

# بررسی دستی
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

# توقف و فعال‌سازی بررسی خودکار
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

# وضعیت اتصال
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

# ارسال فایل json و excel
def send_json(update, context):
    data, url, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ خطا در اتصال: {error}")
        return
    json_data = json.dumps(data, ensure_ascii=False, indent=2)
    file_path = "/tmp/data.json"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(json_data)
    context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(file_path), filename="nouri_data.json")

def send_excel(update, context):
    data, _, error = get_brsapi_data()
    if error:
        context.bot.send_message(chat_id=update.effective_chat.id, text=f"❌ خطا: {error}")
        return
    for item in data:
        if item.get("l18") == "نوری":
            df = pd.DataFrame([item])
            file_path = "/tmp/nouri.xlsx"
            df.to_excel(file_path, index=False)
            context.bot.send_document(chat_id=update.effective_chat.id, document=InputFile(file_path), filename="nouri.xlsx")
            return
    context.bot.send_message(chat_id=update.effective_chat.id, text="❌ نماد نوری در داده‌ها پیدا نشد.")

# رابط کاربری
def start(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')],
        [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')],
        [InlineKeyboardButton("⬇️ دانلود فایل JSON", callback_data='get_json')],
        [InlineKeyboardButton("⬇️ دانلود فایل Excel نوری", callback_data='get_excel')],
        [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')],
        [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=update.effective_chat.id, text="یک گزینه را انتخاب کنید:", reply_markup=reply_markup)

def button(update, context):
    query = update.callback_query
    query.answer()
    data = query.data
    if data == 'check_signal':
        manual_check(update, context)
    elif data == 'status':
        status(update, context)
    elif data == 'get_json':
        send_json(update, context)
    elif data == 'get_excel':
        send_excel(update, context)
    elif data == 'stop':
        stop_check(update, context)
    elif data == 'resume':
        resume_check(update, context)

def handle_text(update, context):
    show_menu(update, context)

# اجرای برنامه
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
