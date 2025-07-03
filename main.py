import os import json import time import threading import requests from flask import Flask, request from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters from datetime import datetime, time as dtime

app = Flask(name)

ثابت‌ها

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"  # توکن بات CHAT_ID = "52909831"  # آی‌دی چت bot = Bot(token=TOKEN)

تنظیمات وضعیت و منبع داده

last_check_time = None market_open = False selected_source = "brsapi"  # پیش‌فرض منبع فعال

لینک BRSAPI برای دریافت همه نمادها

BRSAPI_URL = "https://brsapi.ir/Api/Tsetmc/AllSymbols.php" BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

def is_market_open(): now = datetime.now().time() return dtime(9, 0) <= now <= dtime(12, 30)

def get_brsapi_data(): url = f"{BRSAPI_URL}?key={BRSAPI_KEY}&type=1" try: response = requests.get(url, timeout=10) response.raise_for_status()

# بررسی اینکه آیا پاسخ JSON معتبر دارد یا نه
    data = response.json()
    if isinstance(data, list):
        return {"success": True, "data": data, "url": url}
    else:
        return {"success": False, "error": "پاسخ JSON نامعتبر", "url": url}

except Exception as e:
    return {"success": False, "error": str(e), "url": url}

def check_market_and_notify(): global last_check_time, market_open while True: now = datetime.now() open_status = is_market_open()

# فقط وقتی بازار بازه هر دو دقیقه چک کنه
    if open_status:
        result = get_brsapi_data()
        if not result["success"]:
            bot.send_message(chat_id=CHAT_ID,
                             text=f"🚨 خطا در اتصال به داده BrsApi:\n🌐 URL: {result['url']}\n⚠️ خطا: {result['error']}")
        elif not market_open:
            bot.send_message(chat_id=CHAT_ID, text="🟢 بازار باز شد. من فعال شدم.")
    elif market_open:
        bot.send_message(chat_id=CHAT_ID, text="🔴 بازار بسته شد. من خاموش شدم.")

    market_open = open_status
    last_check_time = now
    time.sleep(120)

@app.route('/', methods=['GET']) def home(): return "ربات نوری فعال است."

@app.route('/', methods=['POST']) def webhook(): update = Update.de_json(request.get_json(force=True), bot) dispatcher.process_update(update) return 'ok'

def start(update, context): menu(update, context)

def status(update, context): global last_check_time, market_open result = get_brsapi_data() msg = f"🕓 آخرین بررسی: {last_check_time}\n" msg += f"📈 بازار: {'باز' if market_open else 'بسته'}\n" msg += f"📡 منبع داده: {selected_source}\n"

if result["success"]:
    msg += "✅ اتصال موفق به BrsApi"
else:
    msg += f"🚨 خطا: {result['error']}\n🌐 URL: {result['url']}"

context.bot.send_message(chat_id=update.effective_chat.id, text=msg)

def reset(update, context): global market_open, last_check_time market_open = False last_check_time = None context.bot.send_message(chat_id=update.effective_chat.id, text="🔄 ربات ریست شد.")

def button(update, context): query = update.callback_query query.answer() data = query.data if data == 'status': status(query, context) elif data == 'reset': reset(query, context) elif data == 'menu': menu(query, context)

def menu(update, context): keyboard = [ [InlineKeyboardButton("📊 وضعیت بازار", callback_data='status')], [InlineKeyboardButton("🔄 ریست ربات", callback_data='reset')], ] reply_markup = InlineKeyboardMarkup(keyboard) if update.callback_query: update.callback_query.edit_message_text('گزینه موردنظر را انتخاب کنید:', reply_markup=reply_markup) else: update.message.reply_text('گزینه موردنظر را انتخاب کنید:', reply_markup=reply_markup)

from telegram.ext import Updater updater = Updater(token=TOKEN, use_context=True) dispatcher = updater.dispatcher

هندلرها

dispatcher.add_handler(CommandHandler('start', start)) dispatcher.add_handler(CommandHandler('status', status)) dispatcher.add_handler(CommandHandler('reset', reset)) dispatcher.add_handler(CallbackQueryHandler(button)) dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if name == 'main': threading.Thread(target=check_market_and_notify, daemon=True).start() app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

