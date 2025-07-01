import requests
from bs4 import BeautifulSoup
import time
from datetime import datetime, time as dt_time
import pytz

# تنظیمات
SYMBOL_CODE = "nori"  # کد نماد در رهاورد (برای نوری: nori)
TZ = pytz.timezone("Asia/Tehran")

# توکن و آیدی تلگرام خودت
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

def send_telegram_message(text):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": text}
    try:
        requests.post(url, data=data, timeout=5)
    except Exception as e:
        print(f"خطا در ارسال پیام تلگرام: {e}")

def get_stock_data():
    url = f"https://rahavard365.com/stock/{SYMBOL_CODE}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        r = requests.get(url, headers=headers, timeout=10)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")

        price_close_tag = soup.find("div", attrs={"data-test": "last-price"})
        price_close = float(price_close_tag.text.replace(",", "")) if price_close_tag else None

        volume_tag = soup.find("div", attrs={"data-test": "volume"})
        volume_text = volume_tag.text.replace(",", "") if volume_tag else None
        volume = int(volume_text) if volume_text and volume_text.isdigit() else None

        return price_close, volume
    except Exception as e:
        send_telegram_message(f"🚨 خطا در دریافت داده از رهاورد: {e}")
        return None, None

def check_signal():
    price_close, volume = get_stock_data()
    if price_close is None or volume is None:
        print("داده ناقص است")
        return

    avg_volume = 100000  # مثال میانگین حجم

    candle_positive = price_close > 4000  # قیمت بالاتر از 4000

    volume_ok = volume > avg_volume

    if candle_positive and volume_ok:
        send_telegram_message("✅ سیگنال ورود نوری صادر شد.")
    else:
        print("شرایط ورود هنوز مهیا نیست.")

if __name__ == "__main__":
    started = False
    while True:
        now = datetime.now(TZ).time()
        if now >= dt_time(8, 59) and not started:
            send_telegram_message("🟢 ربات نوری فعال شد (شروع بازار)")
            started = True

        if dt_time(9, 0) <= now <= dt_time(12, 30):
            check_signal()
        elif now > dt_time(12, 30) and started:
            send_telegram_message("🔴 ربات نوری خاموش شد (پایان بازار)")
            started = False

        time.sleep(120)
