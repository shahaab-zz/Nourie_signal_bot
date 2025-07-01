import requests
from datetime import datetime, time
import pytz
import time as t

# === تنظیمات شما ===
SYMBOL_ID = "46602927695631802"  # نماد نوری در سهامیاب
BOT_TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU"
CHAT_ID = "52909831"
TZ = pytz.timezone('Asia/Tehran')

# === وضعیت‌های ذخیره شده برای جلوگیری از ارسال پیام تکراری ===
last_bot_status = None        # 'active' یا 'inactive'
last_market_status = None     # 'open' یا 'closed'
last_data_connected = None    # True یا False

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
    # API سهامیاب برای نماد نوری
    url = f'https://api.sahamyab.com/v1/quotes/{SYMBOL_ID}/trade'
    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        data = res.json()
        # بر اساس مستندات سهامیاب داده‌های لازم را استخراج می‌کنیم
        # چک کنیم حجم، قیمت پایانی، حجم میانگین و خرید حقوقی را
        return data
    except Exception as e:
        raise Exception(f"خطا در دریافت داده از سهامیاب: {e}")

def check_entry_signal():
    data = get_sahamyab_data()
    # داده‌ها را با دقت چک می‌کنیم
    try:
        # مثال فرضی: چک حجم، کندل مثبت، خرید حقوقی و صف فروش برداشته شده
        final_volume = data.get('finalVolume', 0)
        avg_volume_5d = data.get('avgVolume5Day', 1)  # فرض کنیم 1 اگر نبود
        closing_price = data.get('closingPrice', 0)
        yesterday_closing = data.get('prevClosingPrice', 0)
        buy_legal = data.get('buyLegalValue', 0)
        sell_legal = data.get('sellLegalValue', 0)

        candle_positive = closing_price > yesterday_closing
        volume_ok = final_volume > avg_volume_5d
        legal_ok = (buy_legal - sell_legal) > 0
        sell_queue_removed = closing_price > yesterday_closing

        if all([candle_positive, volume_ok, legal_ok, sell_queue_removed]):
            return True
        else:
            return False
    except Exception as e:
        raise Exception(f"خطا در پردازش داده‌ها: {e}")

def main():
    global last_bot_status, last_market_status, last_data_connected

    while True:
        now = datetime.now(TZ).time()
        market_open = is_market_open()

        # چک اتصال به داده سهامیاب
        data_ok = True
        try:
            # فقط برای چک اول و وقتی بازار باز هست داده چک میشه دقیق
            get_sahamyab_data()
        except Exception as e:
            data_ok = False
            if last_data_connected != False:
                send_notification(f"🚨 خطا در اتصال به داده سهامیاب: {e}")
            last_data_connected = False

        if market_open:
            # بازار باز شده
            if last_market_status != 'open':
                send_notification("🟢 من فعال شدم. (شروع بازار)")
                last_market_status = 'open'

            if not data_ok:
                # اگر دیتا نرسید، پیام داده شد، فقط منتظر باشیم
                pass
            else:
                # چک سیگنال ورود
                try:
                    signal = check_entry_signal()
                    if signal:
                        if last_bot_status != 'active':
                            send_notification("🟢 ربات نوری فعال شد. سیگنال ورود صادر شد.")
                            last_bot_status = 'active'
                    else:
                        if last_bot_status != 'inactive':
                            send_notification("🔴 ربات نوری خاموش شد. شرایط ورود نیست.")
                            last_bot_status = 'inactive'
                except Exception as e:
                    send_notification(f"🚨 خطا در بررسی سیگنال: {e}")

        else:
            # بازار بسته شده
            if last_market_status != 'closed':
                send_notification("🔴 من خاموش شدم. (پایان بازار)")
                last_market_status = 'closed'
            if last_bot_status != None:
                send_notification("🔴 ربات نوری خاموش شد.")
                last_bot_status = None

        last_data_connected = data_ok

        t.sleep(120)  # هر ۲ دقیقه یک بار چک شود

if __name__ == "__main__":
    main()
