import requests
from datetime import datetime, time
import pytz
import time as t

# تنظیمات
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SYMBOL = "NORI"  # نماد نوری در رهاورد365
TZ = pytz.timezone("Asia/Tehran")

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

def get_rahavard_data(symbol, retries=3):
    url = f"https://rahavard365.com/api/v1/market/instrument/{symbol}"
    headers = {
        "User-Agent": "Mozilla/5.0"
    }
    for attempt in range(retries):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            return data
        except Exception as e:
            print(f"⚠️ تلاش {attempt+1} برای دریافت دیتا با خطا مواجه شد: {e}")
            if attempt < retries -1:
                t.sleep(5)
    send_notification("🚨 خطا در دریافت داده از رهاورد پس از چندین تلاش")
    return None

def is_market_open():
    now = datetime.now(TZ).time()
    return time(9, 0) <= now <= time(12, 30)

def check_entry_signal():
    data = get_rahavard_data(SYMBOL)
    if data is None:
        return

    try:
        latest_price = data['lastPrice']
        yesterday_close = data['prevClosePrice']
        volume_today = data['volume']
        avg_volume_5d = data['avgVolume5D']
        buy_legal = data['buyLegalCount'] * data['buyLegalValue']
        sell_legal = data['sellLegalCount'] * data['sellLegalValue']

        candle_positive = latest_price > yesterday_close
        volume_ok = volume_today > avg_volume_5d
        legal_ok = (buy_legal - sell_legal) > 0
        sell_queue_removed = latest_price > yesterday_close

        if all([candle_positive, volume_ok, legal_ok, sell_queue_removed]):
            send_notification("✅ سیگنال ورود به نوری صادر شد.")
        else:
            print("❌ هنوز شرایط ورود کامل نیست.")
    except Exception as e:
        send_notification(f"🚨 خطا در پردازش داده‌های رهاورد: {e}")

if __name__ == "__main__":
    started = False
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

        t.sleep(120)  # هر ۲ دقیقه بررسی شود
