import requests
from datetime import datetime, time, date
import pytz
import os
import time as t

# تنظیمات
SYMBOL = "نوری"
TZ = pytz.timezone('Asia/Tehran')
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

# وضعیت پیام شروع/پایان بازار
last_start_day = None

def send_notification(message):
    print(f"📤 {message}")
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
    try:
        url = f"https://www.sahamyab.com/stock/{SYMBOL}"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.text  # در صورت نیاز، تحلیل HTML اینجا انجام میشه
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت اطلاعات از sahamyab:\n{e}")
        return None

def check_entry_signal():
    html = get_sahamyab_data()
    if not html:
        return

    # 👇 اینجا فعلاً فقط تست اتصال به سایت است
    # در مرحله بعدی داده‌های دقیق را از HTML استخراج می‌کنیم
    print("✅ sahamyab page loaded successfully.")
    # send_notification("📊 داده sahamyab با موفقیت دریافت شد.")

if __name__ == "__main__":
    global last_start_day

    while True:
        now = datetime.now(TZ).time()
        today = date.today()

        # پیام شروع بازار (فقط یک‌بار در روز)
        if now >= time(8, 59) and (last_start_day != today):
            if get_sahamyab_data():
                send_notification("✅ اتصال به sahamyab موفق بود.")
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            last_start_day = today

        # بررسی سیگنال در ساعات بازار
        if is_market_open():
            check_entry_signal()

        # پیام پایان بازار (فقط یک‌بار در روز)
        if now >= time(12, 31) and last_start_day == today:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            last_start_day = None

        t.sleep(120)
