import requests
from datetime import datetime, time, date
import pytz
import os
import time as t

# تنظیمات
SYMBOL_ID = "46602927695631802"  # نوری در سهام‌یاب
TZ = pytz.timezone('Asia/Tehran')
BOT_TOKEN = os.getenv("BOT_TOKEN") or "توکن_ربات_تو_اینجا_بزار"
CHAT_ID = os.getenv("CHAT_ID") or "آیدی_چت_تو_اینجا_بزار"

def send_notification(message):
    print(f"ارسال پیام: {message}")
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
    url = f"https://api.sahamyab.com/api/v1/instruments/{SYMBOL_ID}"
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        return data
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت داده‌ها از sahamyab: {e}")
        return None

def check_entry_signal():
    data = get_sahamyab_data()
    if data is None:
        send_notification("🚨 خطا در دریافت داده‌ها در حین بازار!")
        return

    try:
        latest = data["lastPrice"]
        low = data["low"]
        # شرط ساده ورود: قیمت پایانی > کمینه قیمت روز
        if latest > low:
            send_notification("✅ سیگنال ورود به نوری صادر شد.")
        else:
            print("شرایط ورود مهیا نیست.")
    except Exception as e:
        send_notification(f"🚨 خطا در پردازش داده‌ها: {e}")

if __name__ == "__main__":
    started = False
    last_start_day = None

    while True:
        now = datetime.now(TZ)
        current_day = now.date()
        current_time = now.time()

        # فقط یک بار شروع بازار رو اعلام کن
        if is_market_open() and (not started or last_start_day != current_day):
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            started = True
            last_start_day = current_day

        # فقط یک بار پایان بازار رو اعلام کن
        if current_time > time(12, 30) and started and last_start_day == current_day:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            started = False

        # در زمان باز بودن بازار چک کن
        if is_market_open():
            check_entry_signal()

        t.sleep(120)
