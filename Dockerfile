# syntax=docker/dockerfile:1

# ── Stage 1: build the Vite/React frontend ───────────────────────────────────
FROM node:22-bookworm-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# ── Stage 2: FastAPI backend + Playwright Chromium, serving the built UI ──────
FROM python:3.11-slim-bookworm AS app
ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    AGENT_STUDIO_DB=/data/agent_studio.db

WORKDIR /app

# Python deps first (best layer caching).
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# Real Chrome for the agent's browser tools (+ all system libs it needs).
RUN python -m playwright install --with-deps chromium

# App code + the frontend build output (main.py serves ../frontend/dist).
COPY backend/ backend/
COPY --from=frontend /app/frontend/dist frontend/dist

# Persistent data dir (SQLite settings + chat history) — mount a volume here.
RUN mkdir -p /data

EXPOSE 8000
WORKDIR /app/backend
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
