import requests import json import pandas as pd import pytz import datetime import threading import time import logging from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, Bot from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, CallbackContext from flask import Flask, request import os

--- تنظیمات اولیه ---

TOKEN = "7923807074:AAEz5TI4rIlZZ1M7UhEbfhjP7m3fgYY6weU" CHAT_ID = "52909831" SELECTED_SOURCE = "brsapi"  # یا "rahavard" RAHAVARD_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJpYXQiOjE3NTE4MjE1MDEsImp0aSI6IjVmOTc3ZDA3YWY5ODQ0ODBiY2IzMzBlM2NlZTBjNjM0Iiwic3ViIjoiMTc4MTE4MyIsIm5iZiI6MTc1MTgyMTUwMSwiZXhwIjoxNzU5NTk3NTYxLCJpc3MiOiJjb20ubWFibmFkcC5hcGkucmFoYXZhcmQzNjUudjEifQ.nWrNfmZvFXfjBylDhaDq6yT1Tirdk4yyXXyVUJ7-TnHF2NzRIhRH08trAD82Fm3Mm3rAJOadN1RbeFe05tQIRECe68oyGKgKOS4cst0fRUfDr-AHDZHOPNYY6MPpshe18_vueFoNWkahPpLNxbx7obIMT_elK_2UALMKDxh1BL8mTYSquJoo3xwfscUT55GPi9X0hMxUu_igXcoC-ZoKEDji4nqcYmUZ7UKJ9yreb0hIN_uu5I3KH8hGFOETBx39z7WjK2KwwcFs3J2K-FrefExkd1ynsrxgHbbiaWyNbWil5o7CP13SZ3P9PYjNPZqabGQzMl07wP4V6NbIEPEjDw"

bot = Bot(token=TOKEN) app = Flask(name) updater = Updater(token=TOKEN, use_context=True) dispatcher = updater.dispatcher

--- بررسی باز بودن بازار ---

def is_market_open(): tehran = pytz.timezone('Asia/Tehran') now = datetime.datetime.now(tehran) if now.weekday() >= 5: return False start = now.replace(hour=9, minute=0, second=0, microsecond=0) end = now.replace(hour=12, minute=30, second=0, microsecond=0) return start <= now <= end

ادامه کد در بخش دوم...

elif query.data == "check_connection":
        try:
            if SELECTED_SOURCE == "brsapi":
                response = requests.get(BRSAPI_URL)
                if response.status_code == 200:
                    bot.send_message(chat_id=CHAT_ID, text="✅ اتصال به brsapi برقرار است.")
                else:
                    bot.send_message(chat_id=CHAT_ID, text=f"⛔ خطا در اتصال به brsapi: {response.status_code}")
            elif SELECTED_SOURCE == "rahavard":
                headers = {
                    "Authorization": f"Bearer {RAHAVARD_TOKEN}",
                    "User-Agent": "Mozilla/5.0",
                    "Accept": "application/json",
                    "platform": "web",
                    "application-name": "rahavard"
                }
                url = "https://rahavard365.com/api/v2/chart/bars?countback=1&symbol=exchange.asset:673:real_close:type0&resolution=D"
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req) as response:
                    if response.status == 200:
                        bot.send_message(chat_id=CHAT_ID, text="✅ اتصال به Rahavard برقرار است.")
        except Exception as e:
            bot.send_message(chat_id=CHAT_ID, text=f"⛔ خطا در بررسی اتصال: {e}")

def main():
    updater = Updater(TOKEN, use_context=True)
    dp = updater.dispatcher

    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CallbackQueryHandler(button))
    dp.add_handler(CommandHandler("status", status))
    dp.add_handler(CommandHandler("manual_check", lambda update, context: send_status(update, context, manual=True)))

    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
