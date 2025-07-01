import requests
from datetime import datetime, time
import pytz
import os
import time as t

# تنظیمات
SYMBOL_ID = "46602927695631802"  # نماد نوری در سایت سهام‌یاب
TZ = pytz.timezone('Asia/Tehran')
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"  # توکن ربات تلگرام
CHAT_ID = "52909831"  # آیدی چت تلگرام

def send_notification(message):
    print(f"ارسال پیام: {message}")
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=5
        )
    except:
        print("❌ خطا در ارسال پیام تلگرام")

def is_market_open():
    now = datetime.now(TZ).time()
    return time(9, 0) <= now <= time(12, 30)

def get_sahamyab_data():
    url = f'https://api.sahamyab.com/api/v1/quote/{SYMBOL_ID}/trade'
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except:
        send_notification("🚨 خطا در دریافت داده از sahamyab")
        raise

def check_entry_signal(data):
    # شرط‌های ورود نمونه (باید با منطق خودت تطبیق بدی)
    try:
        today = data['todayPrice']['close']
        yesterday = data['yesterdayPrice']['close']
        volume_today = data['todayPrice']['volume']
        volume_yesterday = data['yesterdayPrice']['volume']

        candle_positive = today > yesterday
        volume_ok = volume_today > volume_yesterday

        return candle_positive and volume_ok
    except:
        return False

if __name__ == "__main__":
    market_started = False
    market_ended = False
    norie_active = False
    norie_inactive = False

    while True:
        now = datetime.now(TZ).time()

        # شروع بازار
        if time(8, 59) <= now < time(9, 1) and not market_started:
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            market_started = True
            market_ended = False

        # پایان بازار
        if now >= time(12, 30) and not market_ended:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            market_ended = True
            market_started = False

        if is_market_open():
            try:
                data = get_sahamyab_data()
                send_notification("✅ اتصال به sahamyab موفق بود.")
            except:
                data = None

            if data:
                signal = check_entry_signal(data)
                if signal and not norie_active:
                    send_notification("🟢 ربات نوری فعال شد.")
                    norie_active = True
                    norie_inactive = False
                elif not signal and not norie_inactive:
                    send_notification("🔴 ربات نوری خاموش شد.")
                    norie_inactive = True
                    norie_active = False
            else:
                if not norie_inactive:
                    send_notification("🚨 خطا در دریافت داده نوری، ربات نوری خاموش شد.")
                    norie_inactive = True
                    norie_active = False

        t.sleep(120)
