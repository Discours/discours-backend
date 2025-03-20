FROM python:slim

RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .

RUN pip install -r requirements.txt

COPY . .

ENV PORT=8000
EXPOSE $PORT

CMD ["python", "-m", "granian", "main:app", "--interface", "asgi", "--host", "0.0.0.0", "--port", "$PORT"]