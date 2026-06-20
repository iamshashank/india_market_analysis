FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    CACHE_DIR=/tmp/ima-cache

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Single worker (keeps the in-memory cache/background thread coherent) with
# multiple threads so the UI stays responsive while analysis runs.
CMD ["sh", "-c", "gunicorn web:app --bind 0.0.0.0:${PORT:-8000} --worker-class gthread --workers 1 --threads 8 --timeout 300 --graceful-timeout 30"]
