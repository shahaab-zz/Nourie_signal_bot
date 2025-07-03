import os import time import threading import requests from flask import Flask, request from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters from datetime import datetime, time as dtime

app = Flask(name)

اطلاعات ربات

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU" CHAT_ID = "52909831"

bot = Bot(token=TOKEN)

وضعیت جهانی

last_check_time = None market_open = False selected_source = "brsapi"

دیکشنری منابع داده

DATA_SOURCES = { "brsapi": { "name": "brsapi", "url": lambda: f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key=Free5VSOryjPh51wo8o6tltHkv0DhsE8&type=1" }, "tsetmc": { "name": "tsetmc (غیرفعال)", "url": lambda: None }, "rahavard": { "name": "rahavard365 (غیرفعال)", "url": lambda: None }, "codal": { "name": "codal (غیرفعال)", "url": lambda: None } }

def is_market_open(): now = datetime.now().time() morning = dtime(9, 0) noon = dtime(12, 30) return morning <= now <= noon

def get_data(): global selected_source source = DATA_SOURCES[selected_source] url = source"url" if not url: return None, f"منبع '{selected_source}' فعال نیست.", url

try:
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    return response.json(), None, url
except Exception as e:
    return None, str(e), url

def check_market_and_notify(): global market_open, last_check_time already_warned = False

while True:
    now = datetime.now()
    open_status = is_market_open()
    last_check_time = now

    if open_status:
        data, error, url = get_data()
        if error:
            bot.send_message(
                chat_id=CHAT_ID,
                text=f"🚨 خطا در اتصال به داده {selected_source}:

🌐 URL: {url} خطا: {error}" ) if not market_open: market_open = True bot.send_message(chat_id=CHAT_ID, text="✅ بازار باز شد. من فعال شدم.") else: if market_open: market_open = False bot.send_message(chat_id=CHAT_ID, text="🔴 بازار بسته شد. من خاموش شدم.") time.sleep(120)

@app.route('/', methods=['GET']) def home(): return "ربات نوری فعال است."

@app.route('/', methods=['POST']) def webhook(): update = Update.de_json(request.get_json(force=True), bot) dispatcher.process_update(update) return 'ok'

def start(update, context): context.bot.send_message(chat_id=update.effective_chat.id, text="سلام! ربات نوری فعال است. با /menu شروع کن.")

def status(update, context): global last_check_time data, error, url = get_data() status_text = f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {'باز' if market_open else 'بسته'}\n📡 منبع داده: {selected_source}" if error: status_text += f"\n🚨 خطا: {error}\n🌐 URL: {url}" context.bot.send_message(chat_id=update.effective_chat.id, text=status_text)

def reset(update, context): global market_open, last_check_time market_open = False last_check_time = None context.bot.send_message(chat_id=update.effective_chat.id, text="ریست شد.")

def change_source(update, context): global selected_source query = update.callback_query query.answer() selected_source = query.data query.edit_message_text(text=f"✅ منبع جدید انتخاب شد: {selected_source}")

def menu(update, context): keyboard = [ [InlineKeyboardButton("📊 وضعیت", callback_data='status')], [InlineKeyboardButton("♻️ ریست", callback_data='reset')], [InlineKeyboardButton("📡 منبع: brsapi", callback_data='brsapi')], [InlineKeyboardButton("tsetmc (غیرفعال)", callback_data='tsetmc')], [InlineKeyboardButton("rahavard365 (غیرفعال)", callback_data='rahavard')], [InlineKeyboardButton("codal (غیرفعال)", callback_data='codal')] ] reply_markup = InlineKeyboardMarkup(keyboard) update.message.reply_text('🔽 یک گزینه انتخاب کن:', reply_markup=reply_markup)

def button(update, context): query = update.callback_query if query.data == 'status': status(query, context) elif query.data == 'reset': reset(query, context) elif query.data in DATA_SOURCES: change_source(update, context)

from telegram.ext import Updater updater = Updater(token=TOKEN, use_context=True) dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start)) dispatcher.add_handler(CommandHandler('menu', menu)) dispatcher.add_handler(CommandHandler('status', status)) dispatcher.add_handler(CommandHandler('reset', reset)) dispatcher.add_handler(CallbackQueryHandler(button)) dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), menu))

if name == 'main': threading.Thread(target=check_market_and_notify, daemon=True).start() app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

