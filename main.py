import requests
from bs4 import BeautifulSoup
from datetime import datetime, time
import pytz
import os
import time as t

# توکن و شناسه چت تلگرام
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

# منطقه زمانی تهران
TZ = pytz.timezone("Asia/Tehran")

# تنظیمات نماد
SYMBOL = "نوری"

# تابع ارسال پیام به تلگرام
def send_notification(message):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": message},
            timeout=5
        )
    except Exception as e:
        print("❌ خطا در ارسال پیام تلگرام:", e)

# دریافت HTML سایت سهامیاب
def get_data_from_sahamyab():
    try:
        url = f"https://www.sahamyab.com/stock-info/{SYMBOL}"
        headers = {
            "User-Agent": "Mozilla/5.0",
        }
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        return res.text
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت داده از سهامیاب:\n{e}")
        return None

# تحلیل داده‌ها از HTML
def parse_data(html):
    try:
        soup = BeautifulSoup(html, "html.parser")

        price_tag = soup.find("div", class_="price")
        volume_tag = soup.find("div", string="حجم معاملات")
        legal_tag = soup.find("div", string="خرید حقوقی")

        price = price_tag.text.strip() if price_tag else None
        volume = volume_tag.find_next("div").text.strip() if volume_tag else None
        legal_buy = legal_tag.find_next("div").text.strip() if legal_tag else None

        return price, volume, legal_buy
    except Exception as e:
        send_notification(f"⚠️ خطا در تحلیل داده‌ها:\n{e}")
        return None, None, None

# بررسی باز بودن بازار
def is_market_open():
    now = datetime.now(TZ).time()
    return time(9, 0) <= now <= time(12, 30)

# بررسی سیگنال ورود (نماد نوری)
def check_entry_signal():
    html = get_data_from_sahamyab()
    if not html:
        return

    price, volume, legal = parse_data(html)

    if all([price, volume, legal]):
        send_notification(f"📈 بررسی نوری:\nقیمت: {price}\nحجم: {volume}\nخرید حقوقی: {legal}")
    else:
        send_notification("❌ برخی اطلاعات نوری کامل دریافت نشد.")

# اجرای اصلی
if __name__ == "__main__":
    started = False

    # بررسی اولیه (مهم نیست بازار باز یا بسته)
    html = get_data_from_sahamyab()
    if html:
        send_notification("✅ اتصال به sahamyab موفق بود.")
    else:
        send_notification("🚨 اتصال به sahamyab شکست خورد (قبل از شروع بازار).")

    while True:
        now = datetime.now(TZ).time()

        if now >= time(8, 59) and not started:
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            started = True

        if is_market_open():
            check_entry_signal()
        elif now >= time(12, 31) and started:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            started = False

        t.sleep(120)
