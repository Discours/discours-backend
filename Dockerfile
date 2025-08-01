FROM python:slim

RUN apt-get update && apt-get install -y \
    postgresql-client \
    curl \
    build-essential \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Установка Node.js LTS и npm
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nsolid \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["python", "-m", "granian", "main:app", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000"]
