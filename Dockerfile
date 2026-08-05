FROM python:3.10-slim

WORKDIR /app

# تثبيت المتطلبات
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# نسخ الملفات
COPY . .

# ===== متغيرات البيئة لتقليل الـ logs =====
ENV PYTHONUNBUFFERED=0
ENV PYTHONIOENCODING=utf-8
ENV UVICORN_LOG_LEVEL=critical
ENV LOG_LEVEL=critical

# ===== تشغيل بدون logs =====
CMD ["python", "-u", "checker_api2.py", "2>/dev/null", "1>/dev/null"]
