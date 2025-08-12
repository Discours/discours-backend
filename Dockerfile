FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

RUN apt-get update && apt-get install -y \
    postgresql-client \
    git \
    curl \
    build-essential \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install only transitive deps first (cache-friendly layer)
COPY pyproject.toml .
COPY uv.lock .
RUN uv sync --no-install-project

# Add project sources and finalize env
COPY . .
RUN uv sync --no-editable

# Установка Node.js LTS и npm
RUN curl -fsSL https://deb.nodesource.com/setup_lts.x | bash - && \
    apt-get install -y nsolid \
    && rm -rf /var/lib/apt/lists/*

RUN npm upgrade -g npm
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build
RUN pip install -r requirements.txt

EXPOSE 8000

CMD ["python", "-m", "granian", "main:app", "--interface", "asgi", "--host", "0.0.0.0", "--port", "8000"]
