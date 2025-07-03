import requests import time import datetime import pytz from bs4 import BeautifulSoup from flask import Flask, request

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU" CHAT_ID = "52909831" CHECK_INTERVAL = 120  # seconds (2 minutes)

متغیرهای وضعیت

last_check_time = None last_signal_status = None last_sahamyab_ok = None last_start_day = None

app = Flask(name)

def send_telegram(message): url = f"https://api.telegram.org/bot{TOKEN}/sendMessage" payload = {"chat_id": CHAT_ID, "text": message} try: requests.post(url, data=payload, timeout=10) except Exception as e: print(f"خطا در ارسال پیام تلگرام: {e}")

def get_sahamyab_data(): try: url = "https://www.sahamyab.com/quote/NOUR" response = requests.get(url, timeout=10) soup = BeautifulSoup(response.text, "html.parser")

scripts = soup.find_all("script")
    for script in scripts:
        if "finalVolume" in script.text:
            json_text = script.text.strip().split("var quote = ")[-1].split(";\n")[0]
            import json
            return json.loads(json_text)

    raise Exception("داده‌ای یافت نشد.")
except Exception as e:
    raise Exception(f"خطا در دریافت داده از sahamyab: {e}")

def is_market_open(): tz = pytz.timezone("Asia/Tehran") now = datetime.datetime.now(tz) return now.weekday() < 5 and datetime.time(9, 0) <= now.time() <= datetime.time(12, 30)

def check_entry_signal(): global last_check_time, last_signal_status, last_sahamyab_ok last_check_time = datetime.datetime.now() try: data = get_sahamyab_data() last_sahamyab_ok = True

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

    last_signal_status = candle_positive and volume_ok and legal_ok and sell_queue_removed
    return last_signal_status
except Exception as e:
    last_sahamyab_ok = False
    raise Exception(f"خطا در پردازش داده‌ها: {e}")

def market_loop(): global last_start_day send_telegram("✅ اتصال به sahamyab موفق بود.") last_start_day = datetime.date.today() send_telegram("🟢 من فعال شدم. (شروع بازار)") send_telegram("🟢 ربات نوری فعال شد.")

while is_market_open():
    try:
        if check_entry_signal():
            send_telegram("🚀 سیگنال خرید صادر شد برای نوری!")
    except Exception as e:
        send_telegram(f"⚠️ {e}")
    time.sleep(CHECK_INTERVAL)

send_telegram("🔴 ربات نوری خاموش شد.")
send_telegram("🔴 من خاموش شدم. (پایان بازار)")

@app.route("/") def home(): return "Nourie Signal Bot is running."

@app.route(f"/{TOKEN}", methods=["POST"]) def telegram_webhook(): update = request.get_json() if "message" in update and "text" in update["message"]: text = update["message"]["text"] chat_id = update["message"]["chat"]["id"]

if text.strip().lower() == "/status":
        now = datetime.datetime.now()
        last_time_str = last_check_time.strftime('%H:%M:%S %Y-%m-%d') if last_check_time else "نامشخص"
        sahamyab_status = "🟢 وصل" if last_sahamyab_ok else "🔴 قطع یا خطا"
        signal_status = "✅ سیگنال مثبت" if last_signal_status else "❌ بدون سیگنال"

        msg = (
            "📊 وضعیت ربات نوری:\n"
            f"⏱ آخرین بررسی: {last_time_str}\n"
            f"🌐 اتصال به سهام‌یاب: {sahamyab_status}\n"
            f"📈 وضعیت سیگنال: {signal_status}\n"
            "✅ من زنده‌ام و هر ۲ دقیقه بررسی می‌کنم."
        )
        send_telegram(msg)
return "ok"

if name == "main": try: if is_market_open(): market_loop() except Exception as e: send_telegram(f"⛔ خطای کلی: {e}") app.run(host="0.0.0.0", port=10000)  # برای Render

