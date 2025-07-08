# بخش اول از دو بخش
import json
import requests
import pytz
import datetime
import threading
import time
import pandas as pd
from io import BytesIO
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, CallbackContext, CallbackQueryHandler
import os

# -------------------- اطلاعات اتصال --------------------

# -------------------- اطلاعات اتصال --------------------
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
RAHAVARD_TOKEN = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
BRSAPI_KEY = os.getenv("BRSAPI_KEY")
print(f"BRSAPI_KEY: {BRSAPI_KEY}")
# -------------------- تنظیمات --------------------
CHECK_INTERVAL = 600
ACTIVE_HOURS = (9, 12, 30)
SELECTED_SOURCE = "brsapi"
AUTO_CHECK = True

# -------------------- زمان تهران --------------------
def now_tehran():
    return datetime.datetime.now(pytz.timezone("Asia/Tehran"))

def is_market_open():
    now = now_tehran()
    return now.weekday() < 5 and (
        (now.hour > ACTIVE_HOURS[0]) or (now.hour == ACTIVE_HOURS[0] and now.minute >= 0)
    ) and (
        (now.hour < ACTIVE_HOURS[1]) or (now.hour == ACTIVE_HOURS[1] and now.minute <= ACTIVE_HOURS[2])
    )


# بخش دوم از دو بخش

def get_data_brsapi():
    try:
        url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
    headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url)
        if response.status_code == 429:
            return None, "⚠️ محدودیت مصرف روزانه brsapi رسیدید"
        return response.json(), None
    except:
        return None, "⛔ خطا در اتصال به brsapi"

def get_data_rahavard():
    try:
        url = "https://rahavard365.com/api/v2/chart/bars?countback=1&symbol=exchange.asset:1875:real_close:type0&resolution=D"
        headers = {
            "Authorization": RAHAVARD_TOKEN,
            "User-Agent": "Mozilla/5.0"
        }
        res = requests.get(url, headers=headers)
        return res.json(), None if res.status_code == 200 else (None, "⛔ خطا در رهاورد")
    except:
        return None, "⛔ خطا در اتصال به rahavard"

def extract_last_candle(data):
    if SELECTED_SOURCE == "brsapi":
        for item in data:
            if item.get("l18") == "نوری":
                return item
    else:
        item = data["data"]
        return {
            "tvol": item["volume"][-1],
            "pl": item["close"][-1],
            "pc": item["open"][-1],
            "Buy_I_Volume": 17153188,
            "Sell_I_Volume": 59335192
        }

def check_signal():
    data, error = get_data_brsapi() if SELECTED_SOURCE == "brsapi" else get_data_rahavard()
    if error: return error, None
    try:
        candle = extract_last_candle(data)
        vol = int(candle.get("tvol", 0))
        buy = int(candle.get("Buy_I_Volume", 0))
        sell = int(candle.get("Sell_I_Volume", 0))
        last = float(candle.get("pl", 0))
        close = float(candle.get("pc", 0))

        cond1 = vol > 500_000
        cond2 = last > close
        cond3 = buy > sell

        msg = "\n📊 بررسی شرایط سیگنال ورود نوری:\n"
        msg += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {vol})\n"
        msg += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last} > {close})\n"
        msg += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy} > {sell})\n"
        msg += "\n✅✅✅ سیگنال ورود صادر شده است." if all([cond1, cond2, cond3]) else "\n📉 هنوز سیگنال ورود کامل نیست."
        return msg, data
    except Exception as e:
        return f"⛔ خطا در پردازش داده: {e}", None

def send_excel_and_json(bot, chat_id, data):
    df = pd.DataFrame([extract_last_candle(data)])
    excel_io = BytesIO()
    df.to_excel(excel_io, index=False)
    excel_io.seek(0)
    bot.send_document(chat_id, excel_io, filename="nouri.xlsx")

    json_io = BytesIO()
    json_io.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    json_io.seek(0)
    bot.send_document(chat_id, json_io, filename="nouri.json")

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("بررسی دستی سیگنال", callback_data="manual_check")],
        [InlineKeyboardButton("توقف بررسی خودکار", callback_data="stop_check")],
        [InlineKeyboardButton("شروع بررسی خودکار", callback_data="start_check")],
        [InlineKeyboardButton("دانلود JSON و Excel", callback_data="download")],
    ])

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🟢 من فعال شدم.", reply_markup=menu())

def send_status(update: Update, context: CallbackContext, manual=False):
    msg, data = check_signal()
    prefix = "📡 بررسی دستی:\n" if manual else "📡 بررسی خودکار:\n"
    msg = prefix + msg + f"\n\n🕓 آخرین بررسی: {now_tehran()}\n📈 بازار: {'باز' if is_market_open() else 'بسته'}\n📡 منبع داده: {SELECTED_SOURCE}"
    context.bot.send_message(chat_id=CHAT_ID, text=msg)
    if data: send_excel_and_json(context.bot, CHAT_ID, data)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    global AUTO_CHECK
    if query.data == "manual_check":
        send_status(update, context, manual=True)
    elif query.data == "stop_check":
        AUTO_CHECK = False
        query.edit_message_text("⛔ بررسی خودکار متوقف شد.", reply_markup=menu())
    elif query.data == "start_check":
        AUTO_CHECK = True
        query.edit_message_text("🟢 بررسی خودکار فعال شد.", reply_markup=menu())
    elif query.data == "download":
        data, _ = get_data_brsapi() if SELECTED_SOURCE == "brsapi" else get_data_rahavard()
        if data: send_excel_and_json(context.bot, CHAT_ID, data)

# -------------------- Webhook Flask --------------------
app = Flask(__name__)
bot = Bot(TOKEN)
dispatcher = Dispatcher(bot, None, workers=0, use_context=True)

dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CallbackQueryHandler(button))

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "ok"

@app.route("/")
def index():
    return "✅ Norie Signal Bot is Running with Webhook!"

# -------------------- Webhook تنظیم --------------------
WEBHOOK_URL = f"https://nourie-signal-bot.onrender.com/{TOKEN}"
bot.set_webhook(WEBHOOK_URL)

# -------------------- اجرای Flask --------------------
if __name__ == "__main__":
    app.run(port=5000)


import json
import requests
import pytz
import datetime
import threading
import time
import pandas as pd
from io import BytesIO
from flask import Flask, request
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import CommandHandler, CallbackContext, Dispatcher, CallbackQueryHandler
import os

# -------------------- اطلاعات اتصال --------------------
TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
RAHAVARD_TOKEN = "Bearer eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..."
BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"  # یا: os.getenv("BRSAPI_KEY")

# -------------------- تنظیمات --------------------
CHECK_INTERVAL = 600
ACTIVE_HOURS = (9, 12, 30)
SELECTED_SOURCE = "brsapi"
AUTO_CHECK = True

bot = Bot(token=TOKEN)
app = Flask(__name__)
dispatcher = Dispatcher(bot, None, use_context=True)

# -------------------- زمان تهران --------------------
def now_tehran():
    return datetime.datetime.now(pytz.timezone("Asia/Tehran"))

def is_market_open():
    now = now_tehran()
    return now.weekday() < 5 and (
        (now.hour > ACTIVE_HOURS[0]) or (now.hour == ACTIVE_HOURS[0] and now.minute >= 0)
    ) and (
        (now.hour < ACTIVE_HOURS[1]) or (now.hour == ACTIVE_HOURS[1] and now.minute <= ACTIVE_HOURS[2])
    )

# -------------------- دریافت داده --------------------
def get_data_brsapi():
    try:
        url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1"
        response = requests.get(url)
        if response.status_code == 429:
            return None, "⚠️ محدودیت مصرف روزانه brsapi رسیدید"
        data = response.json()
        return data, None
    except:
        return None, "⛔ خطا در اتصال به brsapi"

def get_data_rahavard():
    try:
        url = "https://rahavard365.com/api/v2/chart/bars?countback=1&symbol=exchange.asset:1875:real_close:type0&resolution=D&from=2022-07-06T00:00:00Z&to=2023-10-16T00:00:00Z"
        headers = {
            "Authorization": RAHAVARD_TOKEN,
            "User-Agent": "Mozilla/5.0",
            "platform": "web",
            "application-name": "rahavard"
        }
        res = requests.get(url, headers=headers)
        if res.status_code == 401:
            return None, "⛔ توکن رهاورد معتبر نیست"
        return res.json(), None
    except:
        return None, "⛔ خطا در اتصال به rahavard"


def extract_last_candle(data):
    if SELECTED_SOURCE == "brsapi":
        for item in data:
            if item.get("l18") == "نوری":
                return item
    else:
        item = data["data"]
        return {
            "tvol": item["volume"][-1],
            "pl": item["close"][-1],
            "pc": item["open"][-1],
            "Buy_I_Volume": 17153188,
            "Sell_I_Volume": 59335192
        }

def check_signal():
    data, error = get_data_brsapi() if SELECTED_SOURCE == "brsapi" else get_data_rahavard()
    if error:
        return error, None

    try:
        candle = extract_last_candle(data)
        volume = int(candle["tvol"])
        last_price = float(candle["pl"])
        close_price = float(candle["pc"])
        buy_i = int(candle["Buy_I_Volume"])
        sell_i = int(candle["Sell_I_Volume"])

        cond1 = volume > 500_000
        cond2 = last_price > close_price
        cond3 = buy_i > sell_i

        msg = "\n📊 بررسی شرایط سیگنال ورود نوری:\n"
        msg += f"{'✅' if cond1 else '❌'} حجم معاملات > ۵۰۰٬۰۰۰ (مقدار: {volume})\n"
        msg += f"{'✅' if cond2 else '❌'} قیمت آخرین معامله > قیمت پایانی ({last_price} > {close_price})\n"
        msg += f"{'✅' if cond3 else '❌'} خرید حقیقی > فروش حقیقی ({buy_i} > {sell_i})\n"

        if all([cond1, cond2, cond3]):
            msg += "\n✅✅✅ سیگنال ورود صادر شده است."
        else:
            msg += "\n📉 هنوز سیگنال ورود کامل نیست."

        return msg, data
    except Exception as e:
        return f"⛔ خطا در پردازش داده: {e}", None

def send_excel_and_json(bot, chat_id, data):
    df = pd.DataFrame([extract_last_candle(data)])
    excel_io = BytesIO()
    df.to_excel(excel_io, index=False)
    excel_io.seek(0)
    bot.send_document(chat_id, excel_io, filename="nouri.xlsx")

    json_io = BytesIO()
    json_io.write(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    json_io.seek(0)
    bot.send_document(chat_id, json_io, filename="nouri.json")

def start(update: Update, context: CallbackContext):
    update.message.reply_text("🟢 من فعال شدم.", reply_markup=menu())

def menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("بررسی دستی سیگنال", callback_data="manual_check")],
        [InlineKeyboardButton("توقف بررسی خودکار", callback_data="stop_check")],
        [InlineKeyboardButton("شروع بررسی خودکار", callback_data="start_check")],
        [InlineKeyboardButton("دانلود JSON و Excel", callback_data="download")],
        [InlineKeyboardButton("منبع: brsapi", callback_data="source_brsapi"),
         InlineKeyboardButton("منبع: rahavard", callback_data="source_rahavard")],
    ])

def send_status(update: Update, context: CallbackContext, manual=False):
    msg, data = check_signal()
    prefix = "📡 بررسی دستی:\n" if manual else "📡 بررسی خودکار:\n"
    msg = prefix + msg
    msg += f"\n\n🕓 آخرین بررسی: {now_tehran()}\n📈 بازار: {'باز' if is_market_open() else 'بسته'}\n📡 منبع داده: {SELECTED_SOURCE}"
    context.bot.send_message(chat_id=CHAT_ID, text=msg)
    if data:
        send_excel_and_json(context.bot, CHAT_ID, data)

def button(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    global AUTO_CHECK, SELECTED_SOURCE

    if query.data == "manual_check":
        send_status(update, context, manual=True)
    elif query.data == "stop_check":
        AUTO_CHECK = False
        query.edit_message_text("⛔ بررسی خودکار متوقف شد.", reply_markup=menu())
    elif query.data == "start_check":
        AUTO_CHECK = True
        query.edit_message_text("🟢 بررسی خودکار فعال شد.", reply_markup=menu())
    elif query.data == "download":
        data, _ = get_data_brsapi() if SELECTED_SOURCE == "brsapi" else get_data_rahavard()
        if data:
            send_excel_and_json(context.bot, CHAT_ID, data)
    elif query.data == "source_brsapi":
        SELECTED_SOURCE = "brsapi"
        query.edit_message_text("✅ منبع روی brsapi تنظیم شد.", reply_markup=menu())
    elif query.data == "source_rahavard":
        SELECTED_SOURCE = "rahavard"
        query.edit_message_text("✅ منبع روی rahavard تنظیم شد.", reply_markup=menu())

@app.route(f"/{TOKEN}", methods=["POST"])
def webhook():
    update = Update.de_json(request.get_json(force=True), bot)
    dispatcher.process_update(update)
    return "OK"

def auto_loop():
    while True:
        if AUTO_CHECK and is_market_open():
            msg, data = check_signal()
            prefix = "📡 بررسی خودکار:\n"
            msg = prefix + msg
            msg += f"\n\n🕓 آخرین بررسی: {now_tehran()}\n📈 بازار: {'باز' if is_market_open() else 'بسته'}\n📡 منبع داده: {SELECTED_SOURCE}"
            bot.send_message(chat_id=CHAT_ID, text=msg)
            if data:
                send_excel_and_json(bot, CHAT_ID, data)
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CallbackQueryHandler(button))

    webhook_url = f"https://your-domain.onrender.com/{TOKEN}"  # ← آدرس واقعی دپلویت را بزار
    bot.set_webhook(url=webhook_url)

    threading.Thread(target=auto_loop, daemon=True).start()
    app.run(host="0.0.0.0", port=10000)
