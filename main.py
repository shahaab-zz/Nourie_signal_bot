import os import time import threading import requests from flask import Flask, request from telegram import Bot, Update, InlineKeyboardMarkup, InlineKeyboardButton from telegram.ext import Dispatcher, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, Updater from datetime import datetime, time as dtime

تنظیمات اصلی

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU" CHAT_ID = "52909831" SELECTED_SOURCE = "brsapi" BRSAPI_KEY = "Free5VSOryjPh51wo8o6tltHkv0DhsE8"

bot = Bot(token=TOKEN) app = Flask(name)

last_check_time = None market_open = False check_thread_running = True

بررسی زمان بازار

def is_market_open(): now = datetime.now().time() return (dtime(9, 0) <= now <= dtime(12, 30)) or (dtime(13, 30) <= now <= dtime(15, 0))

دریافت داده از BRSAPI

def get_brsapi_data(): url = f"https://brsapi.ir/Api/Tsetmc/AllSymbols.php?key={BRSAPI_KEY}&type=1" headers = {"User-Agent": "Mozilla/5.0"} try: response = requests.get(url, headers=headers, timeout=10) response.raise_for_status() return response.json(), url, None except Exception as e: return None, url, str(e)

بررسی سیگنال ورود برای نماد نوری

def check_nouri_signal(data): try: for item in data: if item.get("LVal18AFC") == "نوری": vol = int(item.get("QTotTran5J", 0)) buy_ind = int(item.get("Buy_I_Volume", 0)) sell_ind = int(item.get("Sell_I_Volume", 0)) last = float(item.get("PDrCotVal", 0)) close = float(item.get("PClosing", 0))

if vol > 500000 and last > close and buy_ind > sell_ind:
                return True, item
    return False, None
except:
    return False, None

بررسی بازار و سیگنال به صورت خودکار

def check_market_and_notify(): global last_check_time, market_open, check_thread_running while check_thread_running: now = datetime.now() last_check_time = now open_status = is_market_open()

if open_status:
        data, url, error = get_brsapi_data()
        if error:
            bot.send_message(chat_id=CHAT_ID, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}")
        else:
            signal, info = check_nouri_signal(data)
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

بررسی دستی سیگنال

def manual_check(update, context): data, url, error = get_brsapi_data() chat_id = update.effective_chat.id if error: context.bot.send_message(chat_id=chat_id, text=f"❌ خطا در اتصال: {error}") return signal, info = check_nouri_signal(data) if signal: context.bot.send_message(chat_id=chat_id, text="🚀 سیگنال ورود به نوری شناسایی شد!") else: context.bot.send_message(chat_id=chat_id, text="📉 هنوز سیگنال ورود وجود ندارد.")

توقف بررسی خودکار

def stop_check(update, context): global check_thread_running check_thread_running = False chat_id = update.effective_chat.id context.bot.send_message(chat_id=chat_id, text="⏹ بررسی خودکار متوقف شد.")

فعال‌سازی مجدد بررسی خودکار

def resume_check(update, context): global check_thread_running if not check_thread_running: check_thread_running = True threading.Thread(target=check_market_and_notify, daemon=True).start() chat_id = update.effective_chat.id context.bot.send_message(chat_id=chat_id, text="▶️ بررسی خودکار دوباره فعال شد.") else: context.bot.send_message(chat_id=update.effective_chat.id, text="✅ بررسی خودکار از قبل فعال بوده است.")

بررسی وضعیت ارتباط و بازار

def status(update, context): global last_check_time chat_id = update.effective_chat.id open_status = is_market_open() market = 'باز' if open_status else 'بسته' data, url, error = get_brsapi_data() if error: context.bot.send_message(chat_id=chat_id, text=f"🚨 خطا در اتصال به {SELECTED_SOURCE}: {error}\n🌐 {url}") else: context.bot.send_message(chat_id=chat_id, text="✅ اتصال برقرار است.") context.bot.send_message(chat_id=chat_id, text=f"🕓 آخرین بررسی: {last_check_time}\n📈 بازار: {market}\n📡 منبع داده: {SELECTED_SOURCE}")

@app.route('/', methods=['GET']) def home(): return "ربات نوری فعال است."

@app.route('/', methods=['POST']) def webhook(): update = Update.de_json(request.get_json(force=True), bot) dispatcher.process_update(update) return 'ok'

def start(update, context): chat_id = update.effective_chat.id context.bot.send_message(chat_id=chat_id, text="سلام! ربات نوری فعال است.") show_menu(update, context)

def show_menu(update, context): keyboard = [ [InlineKeyboardButton("📊 بررسی دستی سیگنال نوری", callback_data='check_signal')], [InlineKeyboardButton("📡 بررسی اتصال و وضعیت بازار", callback_data='status')], [InlineKeyboardButton("⏹ توقف بررسی خودکار", callback_data='stop')], [InlineKeyboardButton("▶️ فعال‌سازی مجدد بررسی", callback_data='resume')] ] reply_markup = InlineKeyboardMarkup(keyboard) chat_id = update.effective_chat.id context.bot.send_message(chat_id=chat_id, text='یک گزینه را انتخاب کنید:', reply_markup=reply_markup)

def button(update, context): query = update.callback_query query.answer() if query.data == 'check_signal': manual_check(update, context) elif query.data == 'stop': stop_check(update, context) elif query.data == 'resume': resume_check(update, context) elif query.data == 'status': status(update, context) else: query.edit_message_text(text="دستور نامعتبر")

def handle_text(update, context): show_menu(update, context)

راه‌اندازی ربات

updater = Updater(token=TOKEN, use_context=True) dispatcher = updater.dispatcher

dispatcher.add_handler(CommandHandler('start', start)) dispatcher.add_handler(CommandHandler('status', status)) dispatcher.add_handler(CallbackQueryHandler(button)) dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), handle_text))

اجرای بررسی خودکار

if name == 'main': threading.Thread(target=check_market_and_notify, daemon=True).start() app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 10000)))

