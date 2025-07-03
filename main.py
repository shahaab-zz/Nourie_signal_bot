import requests
import json
import time
from flask import Flask, request

app = Flask(__name__)

TELEGRAM_TOKEN = "توکن_ربات_تو_اینجا"
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"

last_check_time = 0

def send_telegram_message(text, chat_id):
    payload = {
        'chat_id': chat_id,
        'text': text
    }
    requests.post(f"{TELEGRAM_API}/sendMessage", data=payload)

def send_custom_keyboard(chat_id):
    keyboard = {
        "keyboard": [
            [{"text": "/start"}, {"text": "/status"}, {"text": "/reset"}]
        ],
        "resize_keyboard": True,
        "one_time_keyboard": False
    }
    payload = {
        'chat_id': chat_id,
        'text': "لطفا یک گزینه انتخاب کنید:",
        'reply_markup': json.dumps(keyboard)
    }
    requests.post(f"{TELEGRAM_API}/sendMessage", data=payload)

@app.route('/', methods=['POST'])
def webhook():
    global last_check_time
    data = request.get_json()
    if "message" in data:
        chat_id = data['message']['chat']['id']
        message = data['message'].get('text', '')

        if message == "/start":
            send_custom_keyboard(chat_id)
            send_telegram_message("ربات فعال شد. گزینه مورد نظر را انتخاب کنید.", chat_id)

        elif message == "/status":
            # اینجا میتونی وضعیت ربات یا آخرین زمان چک رو ارسال کنی
            now = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
            send_telegram_message(f"✅ ربات فعال است.\nآخرین بررسی در: {now}", chat_id)

        elif message == "/reset":
            last_check_time = 0
            send_telegram_message("ربات ریست شد.", chat_id)

        else:
            send_telegram_message("دستور نامعتبر است. لطفا از دکمه‌ها استفاده کنید.", chat_id)

    return "ok"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=10000)
