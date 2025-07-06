import os
import time
import threading
import requests
import json
import pandas as pd
from flask import Flask, request, send_file
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater
from datetime import datetime, time as dtime
import pytz
from io import BytesIO

# توکن‌ها و تنظیمات (مقادیر خودتان را جایگزین کنید)
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = 52909831
RAHAVARD_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NTE4MjE1MDEsImp0aSI6IjVmOTc3ZDA3YWY5ODQ0ODBiY2IzMzBlM2NlZTBjNjM0Iiwic3ViIjoiMTc4MTE4MyIsIm5iZiI6MTc1MTgyMTUwMSwiZXhwIjoxNzU5NTk3NTYxLCJpc3MiOiJjb20ubWFibmFkcC5hcGkucmFoYXZhcmQzNjUudjEifQ.nWrNfmZvFXfjBylDhaDq6yT1Tirdk4yyXXyVUJ7-TnHF2NzRIhRH08trAD82Fm3Mm3rAJOadN1RbeFe05tQIRECe68oyGKgKOS4cst0fRUfDr-AHDZHOPNYY6MPpshe18_vueFoNWkahPpLNxbx7obIMT_elK_2UALMKDxh1BL8mTYSquJoo3xwfscUT55GPi9X0hMxUu_igXcoC-ZoKEDji4nqcYmUZ7UKJ9yreb0hIN_uu5I3KH8hGFOETBx39z7WjK2KwwcFs3J2K-FrefExkd1ynsrxgHbbiaWyNbWil5o7CP13SZ3P9PYjNPZqabGQzMl07wP4V6NbIEPEjDw"

# منبع داده پیش‌فرض
SELECTED_SOURCE = "brsapi"

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, workers=0)

last_check_time = None
market_open = False
check_thread_running = True

# منطقه زمانی تهران
tehran_tz = pytz.timezone("Asia/Tehran")

# بررسی باز بودن بازار بر اساس ساعت تهران
def is_market_open():
    now = datetime.now(tehran_tz).time()
    return (dtime(9, 0) <= now <= dtime(12, 30))  # فقط صبح

# دریافت داده از BRSAPI
def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key=Free5VSOryjPh51wo8o6tltHkv0DhsE8&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

# دریافت داده از Rahavard365
def get_rahavard_data():
    url = "https://rahavard365.com/api/v2/chart/bars?countback=1&symbol=exchange.asset:673:real_close:type0&resolution=D"
    headers = {
        "Authorization": f"Bearer {RAHAVARD_TOKEN}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "platform": "web",
        "application-name": "rahavard"
    }
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

# چک کردن سیگنال ورود نوری در داده
def check_nouri_signal_verbose(data):
    try:
        # بسته به منبع داده ساختار متفاوت است
        if SELECTED_SOURCE == "brsapi":
            # جستجو در داده برساپی
            for item in data:
                if item.get("LVal18AFC") == "نوری" or item.get("l18") == "نوری":
                    vol = int(item.get("QTotTran5J", 0))
                    buy_ind = int(item.get("Buy_I_Volume", 0))
                    sell_ind = int(item.get("Sell_I_Volume", 0))
                    last = float(item.get("PDrCotVal", 0))
                    close = float(item.get("PClosing", 0))

                    cond1 = vol > 500000
                    cond2 = last > close
                    cond3 = buy_ind > sell_ind
                    all_pass = cond1 and cond2 and cond3

                    message = "📊 بررسی شرایط سیگنال ورود نوری:\n"
                    message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
                    message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
                    message += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"
                    return all_pass, message
            return False, "❌ نماد نوری در داده‌ها یافت نشد."
        elif SELECTED_SOURCE == "rahavard":
            # داده rahavard ساختار متفاوت دارد، باید با توجه به داده، مقدارها استخراج شود
            # فرض: آخرین کندل روزانه
            bars = data.get("data", [])
            if not bars:
                return False, "❌ داده‌های رهاورد خالی است."
            bar = bars[-1]
            # در اینجا مقادیر نمونه فرضی برای بررسی شرط می‌گذاریم
            vol = int(bar.get("volume", 0))
            # برای خرید و فروش حقیقی داده در دسترس نیست؛ شرط سوم نادیده گرفته می‌شود
            last = float(bar.get("close", 0))
            close = float(bar.get("open", 0))

            cond1 = vol > 500000
            cond2 = last > close
            cond3 = True  # چون داده ندارد، قبول می‌کنیم

            all_pass = cond1 and cond2 and cond3

            message = "📊 بررسی شرایط سیگنال ورود نوری (رهاورد):\n"
            message += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
            message += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت شروع ({last} > {close})\n"
            message += "✅ خرید حقیقی > فروش حقیقی (داده در دسترس نیست، قبول شده)\n"
            return all_pass, message
    except Exception as e:
        return False, f"❌ خطا در پردازش اطلاعات: {str(e)}"

# ادامه در پیام بعدی...
# ادامه بخش دوم کد

# ساخت فایل اکسل از داده نوری (brsapi)
def create_excel_nouri(data):
    # جستجو برای نوری در داده brsapi
    rows = []
    for item in data:
        if item.get("LVal18AFC") == "نوری" or item.get("l18") == "نوری":
            rows.append(item)
    if not rows:
        return None
    df = pd.DataFrame(rows)
    output = BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output

# ساخت فایل json از داده کامل
def create_json_file(data):
    output = BytesIO()
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    output.write(json_str.encode('utf-8'))
    output.seek(0)
    return output

# ارسال پیام وضعیت بازار و سیگنال
def send_status(update=None, context=None, manual=False):
    global market_open, last_check_time

    # چک باز بودن بازار
    market_open = is_market_open()
    now = datetime.now(tehran_tz)
    last_check_time = now

    # دریافت داده از منبع انتخابی
    if SELECTED_SOURCE == "brsapi":
        data, url, error = get_brsapi_data()
    else:
        data, url, error = get_rahavard_data()

    if error:
        msg = f"🚨 خطا در اتصال به داده {SELECTED_SOURCE}:\n{error}\nURL: {url}"
        if update:
            update.message.reply_text(msg)
        else:
            bot.send_message(chat_id=CHAT_ID, text=msg)
        return

    all_pass, signal_message = check_nouri_signal_verbose(data)

    status_msg = f"Norie signal bot:\n"
    status_msg += f"🕓 آخرین بررسی: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
    status_msg += f"📈 بازار: {'باز' if market_open else 'بسته'}\n"
    status_msg += f"📡 منبع داده: {SELECTED_SOURCE}\n\n"
    status_msg += signal_message + "\n\n"
    status_msg += "📉 سیگنال ورود کامل است." if all_pass else "📉 هنوز سیگنال ورود کامل نیست."

    if update:
        update.message.reply_text(status_msg)
    else:
        bot.send_message(chat_id=CHAT_ID, text=status_msg)

# مدیریت دکمه‌ها
def button(update: Update, context):
    query = update.callback_query
    query.answer()

    global SELECTED_SOURCE

    if query.data == "manual_check":
        send_status(update, context, manual=True)

    elif query.data == "download_json":
        if SELECTED_SOURCE == "brsapi":
            data, _, error = get_brsapi_data()
        else:
            data, _, error = get_rahavard_data()

        if error or not data:
            query.edit_message_text(f"⛔ خطا در دریافت داده برای دانلود:\n{error}")
            return

        json_file = create_json_file(data)
        if json_file:
            json_file.name = "data.json"
            bot.send_document(chat_id=query.message.chat_id, document=json_file, filename="data.json")
        else:
            query.edit_message_text("⛔ خطا در ساخت فایل JSON.")

    elif query.data == "download_excel":
        if SELECTED_SOURCE == "brsapi":
            data, _, error = get_brsapi_data()
            if error or not data:
                query.edit_message_text(f"⛔ خطا در دریافت داده برای دانلود:\n{error}")
                return
            excel_file = create_excel_nouri(data)
            if excel_file:
                excel_file.name = "nouri.xlsx"
                bot.send_document(chat_id=query.message.chat_id, document=excel_file, filename="nouri.xlsx")
            else:
                query.edit_message_text("⛔ نماد نوری در داده‌ها یافت نشد.")
        else:
            query.edit_message_text("⚠️ فایل اکسل فقط برای منبع brsapi پشتیبانی می‌شود.")

    elif query.data == "source_brsapi":
        SELECTED_SOURCE = "brsapi"
        query.edit_message_text("✅ منبع داده به brsapi تغییر کرد.")

    elif query.data == "source_rahavard":
        SELECTED_SOURCE = "rahavard"
        query.edit_message_text("✅ منبع داده به rahavard تغییر کرد.")

    elif query.data == "start_check":
        global check_thread_running
        if not check_thread_running:
            check_thread_running = True
            threading.Thread(target=auto_check, daemon=True).start()
        query.edit_message_text("🟢 بررسی خودکار فعال شد.")

    elif query.data == "stop_check":
        check_thread_running = False
        query.edit_message_text("🔴 بررسی خودکار متوقف شد.")

# منوی اصلی با دکمه‌ها
def main_menu():
    keyboard = [
        [InlineKeyboardButton("✅ بررسی دستی سیگنال", callback_data="manual_check")],
        [InlineKeyboardButton("📥 دانلود JSON", callback_data="download_json")],
        [InlineKeyboardButton("📥 دانلود Excel (فقط brsapi)", callback_data="download_excel")],
        [InlineKeyboardButton("🌐 تغییر منبع به brsapi", callback_data="source_brsapi")],
        [InlineKeyboardButton("🌐 تغییر منبع به rahavard", callback_data="source_rahavard")],
        [InlineKeyboardButton("▶️ شروع بررسی خودکار", callback_data="start_check")],
        [InlineKeyboardButton("⏸ توقف بررسی خودکار", callback_data="stop_check")]
    ]
    return InlineKeyboardMarkup(keyboard)

def start(update, context):
    update.message.reply_text("سلام! ربات سیگنال نوری فعال شد. منوی زیر را انتخاب کنید:", reply_markup=main_menu())

def auto_check():
    global check_thread_running
    while check_thread_running:
        now = datetime.now(tehran_tz)
        if dtime(9, 0) <= now.time() <= dtime(12, 30):
            send_status()
        time.sleep(600)  # هر 10 دقیقه

# تنظیم هندلرها
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))

@app.route("/", methods=["GET", "POST"])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
    return "ok"

if __name__ == "__main__":
    threading.Thread(target=auto_check, daemon=True).start()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")))
