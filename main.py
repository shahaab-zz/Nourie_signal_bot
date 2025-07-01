from flask import Flask
import threading
import requests
from datetime import datetime, time as dtime
import pytz
import time

# تنظیمات
app = Flask(__name__)
SYMBOL_ID = "46602927695631802"  # نوری
TZ = pytz.timezone('Asia/Tehran')
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

def send_notification(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=5
        )
    except:
        print("❌ ارسال پیام با خطا مواجه شد")

def get_data():
    try:
        response = requests.get(
            "https://rahavard365.com/asset/47042308668866690", timeout=10
        )
        response.raise_for_status()
        return response.text
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت داده از رهاورد:\n{str(e)}")
        return None

def check_market():
    started = False

    # 🚀 تست اولیه: آیا می‌توان از رهاورد خواند؟
    test = get_data()
    if test:
        send_notification("✅ اتصال به رهاورد موفق بود.")
    else:
        send_notification("❌ اتصال به رهاورد شکست خورد.")

    while True:
        now = datetime.now(TZ).time()

        if now >= dtime(8, 59) and not started:
            send_notification("🟢 ربات نوری فعال شد.")
            started = True

        if dtime(9, 0) <= now <= dtime(12, 30):
            html = get_data()
            if html:
                print("✅ در حال بررسی بازار...")
        elif now >= dtime(12, 31) and started:
            send_notification("🔴 ربات نوری خاموش شد.")
            started = False

        time.sleep(120)

@app.route("/")
def home():
    return "ربات نوری فعال است."

# اجرای بررسی در ترد جداگانه
threading.Thread(target=check_market, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
