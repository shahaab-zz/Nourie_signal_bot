import requests
from bs4 import BeautifulSoup
from datetime import datetime, time
import pytz
import os
import time as t

# تنظیمات
SYMBOL = "نوری"
BASE_URL = f"https://www.sahamyab.com/stock/{SYMBOL}"
TZ = pytz.timezone('Asia/Tehran')

BOT_TOKEN = os.getenv("BOT_TOKEN") or "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = os.getenv("CHAT_ID") or "52909831"

def send_notification(message):
    print("📢 ارسال پیام:", message)
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=5
        )
    except Exception as e:
        print("❌ خطا در ارسال پیام:", e)

def is_market_open():
    now = datetime.now(TZ).time()
    return time(9, 0) <= now <= time(12, 30)

def get_data_from_sahamyab():
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(BASE_URL, headers=headers, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت داده از سهامیاب:\n{e}")
        raise

def parse_data(html):
    soup = BeautifulSoup(html, "html.parser")
    try:
        text = soup.get_text()
        price_pos = "قیمت آخر:"
        vol_pos = "حجم معاملات:"
        corp_pos = "حقوقی خرید:"
        
        price = float(text.split(price_pos)[1].split("تومان")[0].strip().replace(",", ""))
        volume = int(text.split(vol_pos)[1].split("")[0].strip().replace(",", ""))
        legal_buy = "حقوقی خرید" in text

        return price, volume, legal_buy
    except Exception as e:
        send_notification(f"⚠️ خطا در تحلیل اطلاعات صفحه:\n{e}")
        raise

def check_entry_signal():
    html = get_data_from_sahamyab()
    price, volume, legal_buy = parse_data(html)

    candle_positive = price > 0  # فرض مثبت بودن کندل با قیمت آخر مثبت
    volume_ok = volume > 100000  # مقدار تقریبی برای مثال
    legal_ok = legal_buy
    sell_queue_removed = True  # قابل بررسی دقیق نیست از sahamyab

    if all([candle_positive, volume_ok, legal_ok, sell_queue_removed]):
        send_notification("✅ سیگنال ورود به نوری صادر شد.")
    else:
        print("⛔ شرایط ورود هنوز کامل نیست.")

if __name__ == "__main__":
    started = False
    while True:
        now = datetime.now(TZ).time()
        if now >= time(8, 59) and not started:
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            started = True

        if is_market_open():
            try:
                check_entry_signal()
            except Exception as e:
                print("خطا در بررسی:", e)
        elif now >= time(12, 31) and started:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            started = False

        t.sleep(120)
