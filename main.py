import requests
from datetime import datetime, time
import pytz
import time as t
from flask import Flask
import threading

app = Flask(__name__)  # پورت جعلی برای Render

# 🛠 تنظیمات شخصی شهاب
SYMBOL_ID = "46602927695631802"
TZ = pytz.timezone('Asia/Tehran')
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"

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

def get_tsetmc_data():
    url = f'https://cdn.tsetmc.com/api/ClosingPrice/GetClosingPriceDailyList/{SYMBOL_ID}'
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        days = res.json()["closingPriceDaily"]
        return days[-1], days[-2]
    except:
        send_notification("🚨 خطا در دریافت اطلاعات قیمت نوری از TSETMC")
        raise

def get_instrument_info():
    url = f'https://cdn.tsetmc.com/api/Instrument/GetInstrumentStats/{SYMBOL_ID}'
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        return res.json()
    except:
        send_notification("🚨 خطا در دریافت اطلاعات حقوقی نوری از TSETMC")
        raise

def check_entry_signal():
    latest, yesterday = get_tsetmc_data()
    info = get_instrument_info()

    candle_positive = latest["pClosing"] > latest["priceMin"]
    volume_today = latest["finalVolume"]
    avg_volume_2d = sum([d["finalVolume"] for d in [latest, yesterday]]) / 2
    volume_ok = volume_today > avg_volume_2d

    buy_legal = info['buy_CountI_Corp'] * info['buy_ValI_Corp']
    sell_legal = info['sell_CountI_Corp'] * info['sell_ValI_Corp']
    legal_ok = (buy_legal - sell_legal) > 0

    sell_queue_removed = latest['pClosing'] > yesterday['pClosing']

    if all([candle_positive, volume_ok, legal_ok, sell_queue_removed]):
        send_notification("✅ سیگنال ورود به نوری صادر شد.")
    else:
        print("هنوز شرایط ورود کامل نیست.")

@app.route('/')
def fake_web():
    return "🟢 ربات نوری در حال اجراست"

def monitor_loop():
    started = False
    send_notification("✅ پیام تست: ربات با موفقیت اجرا شد.")
    while True:
        now = datetime.now(TZ).time()

        if now >= time(8, 59) and not started:
            send_notification("🟢 من فعال شدم. (شروع بازار)")
            started = True

        if is_market_open():
            try:
                check_entry_signal()
            except Exception as e:
                print(f"⚠️ خطا در بررسی دیتا: {e}")
        elif now >= time(12, 31) and started:
            send_notification("🔴 من خاموش شدم. (پایان بازار)")
            started = False

        t.sleep(120)  # بررسی هر ۲ دقیقه

if __name__ == "__main__":
    threading.Thread(target=monitor_loop).start()
    app.run(host="0.0.0.0", port=10000)
