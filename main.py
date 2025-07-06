import os
import time
import threading
import requests
import json
from flask import Flask
from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler
from datetime import datetime, time as dtime
import io
import pandas as pd
import pytz
import urllib.request

# توکن‌ها و شناسه چت - اینها را دقیقاً اینجا قرار بده:
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"  # توکن ربات تلگرام خودت
CHAT_ID = 52909831  # چت آی دی تلگرام
RAHAVARD_API_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NTE4MjE1MDEsImp0aSI6IjVmOTc3ZDA3YW5kODQ0ODBiY2IzMzBlM2NlZTBjNjM0Iiwic3ViIjoiMTc4MTE4MyIsIm5iZiI6MTc1MTgyMTUwMSwiZXhwIjoxNzU5NTk3NTYxLCJpc3MiOiJjb20ubWFibmFkcC5hcGkucmFoYXZhcmQzNjUudjEifQ.nWrNfmZvFXfjBylDhaDq6yT1Tirdk4yyXXyVUJ7-TnHF2NzRIhRH08trAD82Fm3Mm3rAJOadN1RbeFe05tQIRECe68oyGKgKOS4cst0fRUfDr-AHDZHOPNYY6MPpshe18_vueFoNWkahPpLNxbx7obIMT_elK_2UALMKDxh1BL8mTYSquJoo3xwfscUT55GPi9X0hMxUu_igXcoC-ZoKEDji4nqcYmUZ7UKJ9yreb0hIN_uu5I3KH8hGFOETBx39z7WjK2KwwcFs3J2K-FrefExkd1ynsrxgHbbiaWyNbWil5o7CP13SZ3P9PYjNPZqabGQzMl07wP4V6NbIEPEjDw"

SELECTED_SOURCE = "brsapi"
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN)
app = Flask(__name__)

last_check_time = None
check_thread_running = False

def now_tehran():
    tz = pytz.timezone('Asia/Tehran')
    return datetime.now(tz)

def is_market_open():
    now = now_tehran().time()
    morning_open = dtime(9, 0)
    morning_close = dtime(12, 30)
    afternoon_open = dtime(13, 30)
    afternoon_close = dtime(15, 0)
    return (morning_open <= now <= morning_close) or (afternoon_open <= now <= afternoon_close)

def get_brsapi_data():
    url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        return response.json(), url, None
    except Exception as e:
        return None, url, str(e)

def get_rahavard_data():
    url = "https://rahavard365.com/api/v2/chart/bars?countback=1&symbol=exchange.asset:673:real_close:type0&resolution=D"
    headers = {
        "Authorization": f"Bearer {RAHAVARD_API_TOKEN}",
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
        "platform": "web",
        "application-name": "rahavard"
    }
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req) as response:
            data = json.load(response)
            return data, url, None
    except Exception as e:
        return None, url, str(e)

def extract_nouri_brsapi(data):
    for item in data:
        if item.get("l18") == "نوری":
            return item
    return None

def check_nouri_signal_brsapi(data):
    nouri = extract_nouri_brsapi(data)
    if not nouri:
        return False, "❌ نماد نوری در داده‌ها یافت نشد.\n⛔ بررسی سایر شرط‌ها امکان‌پذیر نیست."
    vol = int(nouri.get("tvol", 0))
    last = float(nouri.get("pc", 0))
    close = float(nouri.get("py", 0))
    buy_ind = int(nouri.get("Buy_I_Volume", 0))
    sell_ind = int(nouri.get("Sell_I_Volume", 0))

    cond_vol = vol > 500000
    cond_price = last > close
    cond_buy = buy_ind > sell_ind

    msg = "📊 بررسی شرایط سیگنال ورود نوری:\n"
    msg += f"{'✅' if cond_vol else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
    msg += f"{'✅' if cond_price else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
    msg += f"{'✅' if cond_buy else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"

    signal = cond_vol and cond_price and cond_buy
    if signal:
        msg += "\n🚀 سیگنال ورود کامل است."
    else:
        msg += "\n📉 هنوز سیگنال ورود کامل نیست."

    return signal, msg

def extract_nouri_rahavard(data):
    if not data or "values" not in data:
        return None
    last_candle = data["values"][-1] if data["values"] else None
    return last_candle

def check_nouri_signal_rahavard(data):
    candle = extract_nouri_rahavard(data)
    if not candle:
        return False, "❌ داده نوری از رهاورد یافت نشد."
    vol = candle[5]
    close = candle[4]
    last = candle[1]
    buy_ind = 1
    sell_ind = 0

    cond_vol = vol > 500000
    cond_price = last > close
    cond_buy = buy_ind > sell_ind

    msg = "📊 بررسی شرایط سیگنال ورود نوری (رهاورد):\n"
    msg += f"{'✅' if cond_vol else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
    msg += f"{'✅' if cond_price else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
    msg += f"{'✅' if cond_buy else '❌'} خرید حقیقی > فروش حقیقی ({buy_ind} > {sell_ind})\n"

    signal = cond_vol and cond_price and cond_buy
    if signal:
        msg += "\n🚀 سیگنال ورود کامل است."
    else:
        msg += "\n📉 هنوز سیگنال ورود کامل نیست."

    return signal, msg

def get_data_by_source():
    if SELECTED_SOURCE == "brsapi":
        data, url, err = get_brsapi_data()
    else:
        data, url, err = get_rahavard_data()
    return data, url, err

def save_json_memory(data):
    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    return io.BytesIO(json_str.encode('utf-8'))

def save_excel_nouri(data):
    nouri = extract_nouri_brsapi(data)
    if not nouri:
        return None
    df = pd.DataFrame([nouri])
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return output

def check_and_notify():
    global last_check_time, check_thread_running
    while check_thread_running:
        if is_market_open():
            data, url, err = get_data_by_source()
            now = now_tehran()
            last_check_time = now
            if err:
                text = f"🚨 خطا در اتصال به داده {SELECTED_SOURCE}:\n{err}\nURL: {url}"
                bot.send_message(chat_id=CHAT_ID, text=text)
            else:
                if SELECTED_SOURCE == "brsapi":
                    signal, msg = check_nouri_signal_brsapi(data)
                else:
                    signal, msg = check_nouri_signal_rahavard(data)
                bot.send_message(chat_id=CHAT_ID, text=f"🕓 آخرین بررسی: {now}\n📡 منبع داده: {SELECTED_SOURCE}\n\n{msg}")
        else:
            bot.send_message(chat_id=CHAT_ID, text="📈 بازار: بسته است.")
        time.sleep(600)

def start(update: Update, context):
    keyboard = [
        [InlineKeyboardButton("بررسی دستی سیگنال", callback_data='check_signal')],
        [InlineKeyboardButton("تغییر منبع داده", callback_data='change_source')],
        [InlineKeyboardButton("دریافت JSON", callback_data='download_json')],
        [InlineKeyboardButton("دریافت Excel نوری", callback_data='download_excel')],
        [InlineKeyboardButton("توقف بررسی خودکار", callback_data='stop_auto')],
        [InlineKeyboardButton("شروع بررسی خودکار", callback_data='start_auto')],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    update.message.reply_text('ربات بررسی سیگنال نوری', reply_markup=reply_markup)

def button(update: Update, context):
    query = update.callback_query
    query.answer()
    data = query.data

    global SELECTED_SOURCE
    global check_thread_running

    if data == "check_signal":
        data_obj, url, err = get_data_by_source()
        if err:
            text = f"🚨 خطا در اتصال به داده {SELECTED_SOURCE}:\n{err}\nURL: {url}"
            query.edit_message_text(text)
            return
        if SELECTED_SOURCE == "brsapi":
            _, msg = check_nouri_signal_brsapi(data_obj)
        else:
            _, msg = check_nouri_signal_rahavard(data_obj)
        query.edit_message_text(msg)

    elif data == "change_source":
        SELECTED_SOURCE = "rahavard" if SELECTED_SOURCE == "brsapi" else "brsapi"
        query.edit_message_text(f"منبع داده تغییر کرد به: {SELECTED_SOURCE}")

    elif data == "download_json":
        data_obj, url, err = get_data_by_source()
        if err:
            query.edit_message_text(f"🚨 خطا در دریافت داده:\n{err}")
            return
        bio = save_json_memory(data_obj)
        bio.name = "data.json"
        bot.send_document(chat_id=query.message.chat.id, document=bio)
        query.edit_message_text("✅ فایل JSON ارسال شد.")

    elif data == "download_excel":
        if SELECTED_SOURCE != "brsapi":
            query.edit_message_text("⚠️ فایل Excel فقط برای منبع brsapi فعال است.")
            return
        data_obj, url, err = get_brsapi_data()
        if err:
            query.edit_message_text(f"🚨 خطا در دریافت داده:\n{err}")
            return
        bio = save_excel_nouri(data_obj)
        if bio is None:
            query.edit_message_text("❌ داده نوری یافت نشد، امکان ساخت فایل Excel نیست.")
            return
        bio.name = "nouri.xlsx"
        bot.send_document(chat_id=query.message.chat.id, document=bio)
        query.edit_message_text("✅ فایل Excel نوری ارسال شد.")

    elif data == "stop_auto":
        if check_thread_running:
            check_thread_running = False
            query.edit_message_text("🛑 بررسی خودکار متوقف شد.")
        else:
            query.edit_message_text("🟢 بررسی خودکار در حال حاضر فعال نیست.")

    elif data == "start_auto":
        if not check_thread_running:
            check_thread_running = True
            threading.Thread(target=check_and_notify, daemon=True).start()
            query.edit_message_text("▶️ بررسی خودکار فعال شد.")
        else:
            query.edit_message_text("🟢 بررسی خودکار قبلا فعال بوده.")

def main():
    dispatcher = Dispatcher(bot, None, use_context=True)
    dispatcher.add_handler(CommandHandler('start', start))
    dispatcher.add_handler(CallbackQueryHandler(button))
    from flask import request

    @app.route('/', methods=['GET', 'POST'])
    def webhook():
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok'

    # شروع بررسی خودکار در ترد جداگانه
    global check_thread_running
    if not check_thread_running:
        check_thread_running = True
        threading.Thread(target=check_and_notify, daemon=True).start()

    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

if __name__ == '__main__':
    main()
