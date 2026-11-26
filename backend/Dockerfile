FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Runtime dependencies only: tests and pytest come from requirements-dev.txt.
COPY requirements.txt ./
RUN pip install --no-cache-dir --timeout 60 --retries 5 -r requirements.txt

# The app needs the demo corpus at runtime: the demo run ingests backend/demo/*.txt.
COPY alembic.ini ./
COPY alembic ./alembic
COPY app ./app
COPY demo ./demo

EXPOSE 8000

# Migrate, then serve on the port Render assigns ($PORT), defaulting to 8000 locally.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
