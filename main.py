import os import time import threading import requests from flask import Flask, request from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters from datetime import datetime, time as dtime

--- تنظیمات اصلی ---

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"  # توکن بات CHAT_ID = "52909831"  # آیدی چت تلگرام SELECTED_SOURCE = "brsapi"  # منبع انتخاب شده پیش‌فرض BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN) app = Flask(name)

last_check_time = None market_open = False

کش آخرین وضعیت دستی برای جلوگیری از خطا در بازار بسته

cached_data = None cached_time = None

def is_market_open(): now = datetime.now().time() morning_start = dtime(9, 0) morning_end = dtime(12, 30) afternoon_start = dtime(13, 30) afternoon_end = dtime(15, 0) return (morning_start <= now <= morning_end) or (afternoon_start <= now <= afternoon_end)

def get_brsapi_data(): try: url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1" headers = {"User-Agent": "Mozilla/5.0"} response = requests.get(url, headers=headers, timeout=10) response.raise_for_status() return response.json(), url, None except Exception as e: return None, url, str(e)

def check_market_and_notify(): global last_check_time, market_open, cached_data, cached_time

while True:
    now = datetime.now()
    open_status = is_market_open()
    last_check_time = now

    if open_status:
        data, url, error = get_brsapi_data()
        if error:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در اتصال به داده {SELECTED_SOURCE}:

خطا: {error}\n\n🌐 URL: {url}") if not market_open: market_open = True bot.send_message(chat_id=CHAT_ID, text="🟢 من فعال شدم. (شروع بازار)") else: if not market_open: time.sleep(120) continue market_open = False cached_data, cached_time = get_brsapi_data() bot.send_message(chat_id=CHAT_ID, text="🔴 من خاموش شدم. (پایان بازار)")

time.sleep(120)

@app.route('/', methods=['GET']) def home(): return "ربات نوری فعال است."

@app.route('/', methods=['POST']) def webhook(): update = Update.de_json(request.get_json(force=True), bot) dispatcher.process_update(update) return 'ok'

def start(update, context): context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است.") show_menu(update, context)

def status(update, context): global last_check_time, cached_time

open_status = is_market_open()
source = SELECTED_SOURCE
market = 'باز' if open_status else 'بسته'

# بررسی دستی اتصال در همین لحظه
data, url, error = get_brsapi_data()

if error:
    context.bot.send_message(chat_id=update.effective_chat.id, text=f"🚨 خطا در اتصال به داده {source}:

خطا: {error}\n\n🌐 URL: {url}") else: context.bot.send_message(chat_id=update.effective_chat.id, text=f"✅ اتصال برقرار است.")

context.bot.send_message(chat_id=update.effective_chat.id, text=f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {market}\n📡 منبع داده: {source}")

def reset(update, context): global market_open, last_check_time market_open = False last_check_time = None context.bot.send_message(chat_id=update.effective_chat.id, text="✅ ربات ریست شد.")

def button(update, context): query = update.callback_query query.answer()

if query.data == 'status':
    status(query, context)
elif query.data == 'reset':
    reset(query, context)
elif query.data == 'start':
    start(query, context)
else:
    query.edit_message_text(text="دستور نامعتبر")

def show_menu(update, context): keyboard = [ [InlineKeyboardButton("📊 وضعیت بازار (Status)", callback_data='status')], [InlineKeyboardButton("🔄 ریست ربات (Reset)", callback_data='reset')], ] reply_markup = InlineKeyboardMarkup(keyboard) context.bot.send_message(chat_id=update.effective_chat.id, text='یک گزینه انتخاب کنید:', reply_markup=reply_markup)

def handle_text(update, context): show_menu(update, context)

from telegram.ext import Updater updater = Updater(token=TOKEN, use_context=True) dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start)) dispatcher.add_handler(CommandHandler('status', status)) dispatcher.add_handler(CommandHandler('reset', reset)) dispatcher.add_handler(CallbackQueryHandler(button)) dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

if name == 'main': threading.Thread(target=check_market_and_notify, daemon=True).start() app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

