FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev curl \
    libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt requirements-ai.txt ./
RUN pip install --no-cache-dir -r requirements.txt -r requirements-ai.txt

COPY . .

ENV PYTHONPATH=/app
