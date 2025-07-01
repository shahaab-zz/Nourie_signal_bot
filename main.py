import requests
from datetime import datetime, time, date
import pytz
import time as t

# تنظیمات
SYMBOL = "نوری"
TZ = pytz.timezone('Asia/Tehran')

# اینجا توکن و چت آیدی تلگرام را مستقیم وارد کن
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

def send_notification(message):
    print(f"📤 {message}")
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=5
        )
    except Exception as e:
        print(f"❌ خطا در ارسال پیام تلگرام: {e}")

def is_market_open():
    now = datetime.now(TZ).time()
    return time(9, 0) <= now <= time(12, 30)

def get_sahamyab_data():
    try:
        url = f"https://www.sahamyab.com/stock/{SYMBOL}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت اطلاعات از sahamyab:\n{e}")
        return None

def check_entry_signal():
    html = get_sahamyab_data()
    if not html:
        return

    print("✅ sahamyab page loaded successfully.")
    # اینجا میتونی کد پردازش html را اضافه کنی

if __name__ == "__main__":
    last_start_day = None

    while True:
        now = datetime.now(TZ).time()
        today = date.today()

        if now >= time(8, 59) and (last_start_day != today):
            if get_sahamyab_data():
                send_notification("✅ اتصال به sahamyab موفق بود.")
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            last_start_day = today

        if is_market_open():
            check_entry_signal()

        if now >= time(12, 31) and last_start_day == today:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            last_start_day = None

        t.sleep(120)
