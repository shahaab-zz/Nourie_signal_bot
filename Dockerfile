# استفاده از ایمیج سبک پایتون 3.11
FROM python:3.11-slim

# تنظیم دایرکتوری کاری داخل کانتینر
WORKDIR /app

# کپی فایل requirements.txt به داخل کانتینر
COPY requirements.txt .

# نصب بسته‌ها
RUN pip install --no-cache-dir -r requirements.txt

# کپی کل کد پروژه به کانتینر
COPY . .

# تعیین متغیرهای محیطی برای Flask (اختیاری)
ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=10000

# باز کردن پورت 10000 (باید با پورت داخل برنامه هماهنگ باشه)
EXPOSE 10000

# اجرای برنامه
CMD ["python", "main.py"]
