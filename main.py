import requests
import time
import datetime
import pytz
from flask import Flask
from threading import Thread

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SAHAM_YAB_URL = "https://www.sahamyab.com/quote/نوری"

tehran = pytz.timezone('Asia/Tehran')
app = Flask(__name__)

last_start_day = None
last_end_day = None
last_signal_status = None

def send_telegram_message(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": message}
    try:
        requests.post(url, data=data)
    except:
        pass

def get_sahamyab_data():
    try:
        response = requests.get(SAHAM_YAB_URL, timeout=10)
        response.raise_for_status()
        if "نوری" in response.text:
            return {"valid": True}
        return {"valid": False}
    except Exception as e:
        raise Exception(f"خطا در دریافت داده از سهام‌یاب: {e}")

def check_entry_signal():
    try:
        data = get_sahamyab_data()
        return data.get("valid", False)
    except:
        return False

def is_market_open():
    now = datetime.datetime.now(tehran)
    if now.weekday() >= 5:
        return False
    return datetime.time(9, 0) <= now.time() <= datetime.time(12, 30)

def run_bot():
    global last_start_day, last_end_day, last_signal_status

    # تست اتصال sahamyab در لحظه شروع
    try:
        get_sahamyab_data()
        send_telegram_message("✅ اتصال به sahamyab موفق بود.")
    except Exception as e:
        send_telegram_message(f"🚨 خطا در اتصال اولیه به sahamyab: {e}")

    while True:
        now = datetime.datetime.now(tehran)
        date_str = now.date().isoformat()

        if is_market_open():
            if last_start_day != date_str:
                send_telegram_message("🟢 من فعال شدم. (شروع بازار)")
                last_start_day = date_str
                last_signal_status = None

            # بررسی سیگنال هر 2 دقیقه
            try:
                signal = check_entry_signal()
                if signal and last_signal_status != "buy":
                    send_telegram_message("📈 سیگنال ورود نوری شناسایی شد!")
                    last_signal_status = "buy"
                elif not signal and last_signal_status != "no_buy":
                    send_telegram_message("❌ شرایط ورود مناسب نیست.")
                    last_signal_status = "no_buy"
            except Exception as e:
                send_telegram_message(f"⚠️ خطا در بررسی سیگنال: {e}")
        else:
            if last_end_day != date_str:
                send_telegram_message("🔴 من خاموش شدم. (پایان بازار)")
                last_end_day = date_str

        time.sleep(120)

@app.route('/')
def index():
    return "ربات نوری فعال است."

if __name__ == '__main__':
    t = Thread(target=run_bot)
    t.start()
    app.run(host='0.0.0.0', port=10000)
