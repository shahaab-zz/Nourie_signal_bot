import os
import time
import threading
import requests
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater
from datetime import datetime, time as dtime
try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:
    from pytz import timezone as ZoneInfo  # fallback if needed

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

# بررسی زمان بازار با منطقه زمانی تهران
def is_market_open():
    try:
        # اگر Python 3.9+ باشد
        now_utc = datetime.utcnow().replace(tzinfo=ZoneInfo("UTC"))
        now_tehran = now_utc.astimezone(ZoneInfo("Asia/Tehran"))
    except Exception:
        # fallback برای pytz
        tehran_tz = ZoneInfo("Asia/Tehran")
        now_tehran = datetime.now(tehran_tz)
    current_time = now_tehran.time()
    weekday = now_tehran.weekday()
    # تعطیلات بازار: جمعه (4) و شنبه (5)
    if weekday in [4, 5]:
        return False
    morning = (dtime(9, 0), dtime(12, 30))
    afternoon = (dtime(13, 30), dtime(15, 0))
    return (morning[0] <= current_time <= morning[1]) or (afternoon[0] <= current_time <= afternoon[1])

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

# بررسی سیگنال ورود برای نماد نوری با توضیح شرایط
def check_nouri_signal_verbose(data):
    try:
        for item in data:
            if item.get("l18") == "نوری":  # اصلاح کلید به l18 که نمونه داده شماست
                vol = int(item.get("tvol", 0))
                buy_ind = int(item.get("Buy_I_Volume", 0))
                sell_ind = int(item.get("Sell_I_Volume", 0))
                last = float(item.get("pc", 0))
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
        return False, "❌ نماد نوری در داده‌ها یافت نشد."
    except Exception as e:
        return False, f"❌ خطا در پردازش اطلاعات: {str(e)}"

# بررسی بازار و سیگنال به صورت خودکار
def check_market_and_notify():
    global last_check_time, market_open, check_thread_running
    bot.send_message(chat_id=CHAT_ID, text="🚀 ربات بررسی بازار شروع به کار کرد.")
    while check_thread_running:
        now = datetime.now()
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

# دانلود JSON داده‌ها و ارسال به تلگرام
def download_json(update, context):
    data, url, error = get_brsapi_data()
    chat_id = update.effective_chat.id
    if error:
        context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در دریافت داده‌ها: {error}")
        return
    # ارسال فایل JSON به صورت متن (اگر فایل بخواهی بسازم اطلاع بده)
    import json
    json_text = json.dumps(data, ensure_ascii=False, indent=2)
    # اگر حجم داده زیاد است پیام را به چند قسمت تقسیم کن (اینجا ساده ارسال می‌کنم)
    if len(json_text) > 4000:
        parts = [json_text[i:i+4000] for i in range(0, len(json_text), 4000)]
        for part in parts:
            context.bot.send_message(chat_id=chat_id, text=part)
    else:
        context.bot.send_message(chat_id=chat_id, text=json_text)

# صفحه اصلی
@app.route('/', methods=['GET'])
def home():
    return "ربات نوری فعال است."

@app.route('/', methods=['POST'])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return 'ok'

def start(update, context):
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text="سلام! ربات نوری فعال است.")
    show_menu(update, context)

def show_menu(update, context):
    keyboard = [
        [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')],
        [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')],
        [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')],
        [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')],
        [InlineKeyboardButton("📥 دانلود JSON داده‌ها", callback_data='download_json')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    chat_id = update.effective_chat.id
    context.bot.send_message(chat_id=chat_id, text='یک گزینه را انتخاب کنید:', reply_markup=reply_markup)

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
        download_json(update, context)
    else:
        query.edit_message_text(text="دستور نامعتبر")

def handle_text(update, context):
    show_menu(update, context)

# راه‌اندازی ربات
updater = Updater(token=TOKEN, use_context=True)
dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start))
dispatcher.add_handler(CommandHandler('status', status))
dispatcher.add_handler(CallbackQueryHandler(button))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

# اجرای بررسی خودکار
if __name__ == '__main__':
    threading.Thread(target=check_market_and_notify, daemon=True).start()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))
