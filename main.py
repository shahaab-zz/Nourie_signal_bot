import requests
from datetime import datetime, time
import pytz
import os
import time as t

# تنظیمات
TZ = pytz.timezone('Asia/Tehran')
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
SAHAMYAB_URL = "https://www.sahamyab.com/stock-info/nouri"

# وضعیت‌ها برای جلوگیری از تکرار
last_start_day = None
market_started = False
market_ended = False
notified_sahamyab = False


def send_notification(message):
    print(f"پیام ارسالی: {message}")
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
        res = requests.get(SAHAMYAB_URL, timeout=10)
        res.raise_for_status()
        if "نوری" in res.text:
            return {
                "finalVolume": 1000000,  # مقدار تستی
                "avgVolume5Day": 800000,
                "closingPrice": 4250,
                "prevClosingPrice": 4200,
                "buyLegalValue": 500000000,
                "sellLegalValue": 300000000
            }
        else:
            raise Exception("داده نوری در پاسخ یافت نشد.")
    except Exception as e:
        send_notification(f"🚨 خطا در دریافت داده از sahamyab:\n{e}")
        return None


def check_entry_signal():
    data = get_sahamyab_data()
    if not data:
        return False

    try:
        final_volume = data.get('finalVolume', 0)
        avg_volume_5d = data.get('avgVolume5Day', 1)
        closing_price = data.get('closingPrice', 0)
        yesterday_closing = data.get('prevClosingPrice', 0)
        buy_legal = data.get('buyLegalValue', 0)
        sell_legal = data.get('sellLegalValue', 0)

        candle_positive = closing_price > yesterday_closing
        volume_ok = final_volume > avg_volume_5d
        legal_ok = (buy_legal - sell_legal) > 0
        sell_queue_removed = closing_price > yesterday_closing

        return all([candle_positive, volume_ok, legal_ok, sell_queue_removed])
    except Exception as e:
        send_notification(f"🚨 خطا در پردازش داده‌ها:\n{e}")
        return False


if __name__ == "__main__":
    while True:
        now = datetime.now(TZ)
        today = now.date()
        current_time = now.time()

        # شروع بازار
        if time(8, 59) <= current_time <= time(9, 1):
            if last_start_day != today:
                last_start_day = today
                market_started = True
                market_ended = False
                notified_sahamyab = False
                send_notification("🟢 من فعال شدم. (شروع بازار)")

        # حین بازار
        if is_market_open():
            if not notified_sahamyab:
                data = get_sahamyab_data()
                if data:
                    send_notification("✅ اتصال به sahamyab موفق بود.")
                    notified_sahamyab = True
                else:
                    send_notification("❌ خطا در دریافت داده sahamyab در زمان بازار.")
                    notified_sahamyab = True
            else:
                if check_entry_signal():
                    send_notification("✅ سیگنال ورود نوری صادر شد.")
        else:
            # پایان بازار
            if current_time >= time(12, 31) and not market_ended:
                send_notification("🔴 من خاموش شدم. (پایان بازار)")
                market_ended = True

        t.sleep(120)  # هر 2 دقیقه یکبار چک شود
