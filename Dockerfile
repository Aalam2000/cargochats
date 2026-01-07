FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src

COPY requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

# Alembic files inside container (for migrations)
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations

COPY src /app/src

CMD ["python", "-m", "src.main"]
