FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    gcc \
    libpq-dev \
    netcat-openbsd \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r /app/requirements.txt

COPY . /app

RUN chmod +x /app/scripts/entrypoint.sh && \
    chmod +x /app/scripts/start-web.sh && \
    chmod +x /app/scripts/start-worker.sh

ENTRYPOINT ["/app/scripts/entrypoint.sh"]