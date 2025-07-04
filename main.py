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
import io

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

# منطقه زمانی تهران
tehran_tz = pytz.timezone('Asia/Tehran')

# بررسی زمان بازار با توجه به ساعت ایران
def is_market_open():
    now = datetime.now(tehran_tz).time()
    morning_start = dtime(9, 0)
    morning_end = dtime(12, 30)
    afternoon_start = dtime(13, 30)
    afternoon_end = dtime(15, 0)
    # فقط شنبه تا چهارشنبه بازار باز است
    today = datetime.now(tehran_tz).weekday()  # شنبه=5، جمعه=4 و ...
    if today in [4, 5, 6]:  # جمعه و تعطیلات آخر هفته بازار بسته
        return False
    return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

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

# بررسی سیگنال ورود برای نماد نوری با پیام وضعیت هر شرط
def check_nouri_signal_verbose(data):
    try:
        for item in data:
            if item.get("l18") == "نوری":
                vol = int(item.get("tvol", 0))
                buy_ind = int(item.get("Buy_I_Volume", 0))
                sell_ind = int(item.get("Sell_I_Volume", 0))
                last = float(item.get("pc", 0))
                close = float(item.get("py", 0))

                cond1 = vol > 500000
                cond2 = last > close
                cond3 = buy_ind > sell_ind

                all_pass = cond1 and cond2 and cond3

                message = "📊 بررسی شرایط سیگنال ورود نوری:\n"
                message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
                message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
                message += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"

                return all_pass, message
        return False, "❌ نماد نوری در داده‌ها یافت نشد.\n⛔ بررسی سایر شرط‌ها امکان‌پذیر نیست."
    except Exception as e:
        return False, f"❌ خطا در پردازش اطلاعات: {str(e)}"

# بررسی بازار و ارسال نوتیفیکیشن خودکار هر 2 دقیقه
def check_market_and_notify():
    global last_check_time, market_open, check_thread_running
    while check_thread_running:
        now = datetime.now(tehran_tz)
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

# بررسی دستی سیگنال
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

# توقف بررسی خودکار
def stop_check(update, context):
    global check_thread_running
    check_thread_running = False
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="⏹ بررسی خودکار متوقف شد.")

# فعال‌سازی مجدد بررسی خودکار
def resume_check(update, context):
    global check_thread_running
    if not check_thread_running:
        check_thread_running = True
        threading.Thread(target=check_market_and_notify, daemon=True).start()
        chat_id = update.effective_chat.id
        context.bot.send_message(chat_id=chat_id, text="▶️ بررسی خودکار دوباره فعال شد.")
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text="✅ بررسی خودکار از قبل فعال بوده است.")

# بررسی وضعیت اتصال و بازار
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

# ارسال فایل JSON کامل دیتا
def send_json(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت JSON: {error}")
        return
    json_str = requests.utils.json.dumps(data, ensure_ascii=False)
    bio = io.BytesIO()
    bio.write(json_str.encode('utf-8'))
    bio.seek(0)
    context.bot.send_document(chat_id=chat_id, document=bio, filename="data.json")

# ارسال فایل اکسل فقط نماد نوری
def send_excel(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت داده‌ها: {error}")
        return
    # استخراج داده نوری
    nouri_data = [item for item in data if item.get("l18") == "نوری"]
    if not nouri_data:
        context.bot.send_message(chat_id=chat_id, text="❌ نماد نوری در داده‌ها یافت نشد.")
        return
    df = pd.DataFrame(nouri_data)
    bio = io.BytesIO()
    df.to_excel(bio, index=False)
    bio.seek(0)
    context.bot.send_document(chat_id=chat_id, document=bio, filename="nouri.xlsx")

# منوی اصلی ربات
def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')],
        [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')],
        [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')],
        [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')],
        [InlineKeyboardButton("📥 دانلود JSON کامل", callback_data='download_json')],
        [InlineKeyboardButton("📥 دانلود Excel نوری", callback_data='download_excel')]
    ]
    chat_id = update.effective_chat.id
    reply_markup = InlineKeyboardMarkup(keyboard)
    context.bot.send_message(chat_id=chat_id, text='یک گزینه را انتخاب کنید:', reply_markup=reply_markup)

# هندلر دکمه‌ها
def button(update, context):
    query = update.callback_query
    query.answer()
    if query.data == 'check_signal':
        manual_check(update, context)
    elif query.data == 'stop':
        stop_check(update, context)
    elif query.data == 'resume':
        resume_check(update, context)
    elif query.data == 'status':
        status(update, context)
    elif query.data == 'download_json':
        send_json(update, context)
    elif query.data == 'download_excel':
        send_excel(update, context)
    else:
        query.edit_message_text(text="دستور نامعتبر")

# پاسخ به متن
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
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

def start(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
