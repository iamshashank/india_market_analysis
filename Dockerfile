# ---- stage 1: build the React SPA into backend/static/spa ----
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build          # vite outDir -> /app/backend/static/spa

# ---- stage 2: python backend ----
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8000 \
    CACHE_DIR=/tmp/ima-cache

WORKDIR /app

COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/ ./backend/
COPY pipelines/ ./pipelines/
# fresh SPA build from stage 1 (overrides any committed bundle)
COPY --from=frontend /app/backend/static/spa ./backend/static/spa

EXPOSE 8000

# Run from the backend package (flat module imports); single worker keeps the
# in-memory cache + background threads coherent, threads keep the UI responsive.
CMD ["sh", "-c", "gunicorn --chdir backend wsgi:app --bind 0.0.0.0:${PORT:-8000} --worker-class gthread --workers 1 --threads 8 --timeout 300 --graceful-timeout 30"]
