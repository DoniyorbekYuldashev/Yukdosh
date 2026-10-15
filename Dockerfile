# Yukdosh image — works on x86 and ARM (Oracle Ampere): python:slim is multi-arch.
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TZ=Asia/Tashkent

WORKDIR /app

# Dependencies first (cached layer — only rebuilt when requirements.txt changes)
COPY requirements.txt .
RUN pip install -r requirements.txt

# Run as a non-root user. /app/state holds the Telegram session (mounted as a volume).
RUN useradd --create-home --uid 1000 yukdosh \
 && mkdir -p /app/state && chown yukdosh:yukdosh /app/state

COPY --chown=yukdosh:yukdosh . .
USER yukdosh

# Default = web admin. bot / scheduler override this in docker-compose.yml.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
