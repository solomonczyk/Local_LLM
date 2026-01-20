# Multi-stage build для оптимизации размера образа
FROM python:3.9-slim as base

# Устанавливаем системные зависимости
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    libpq-dev \
    curl \
    git \
    ripgrep \
    && rm -rf /var/lib/apt/lists/*

# Создаем пользователя для безопасности
RUN useradd -m -u 1000 agent && \
    mkdir -p /app && \
    chown -R agent:agent /app

WORKDIR /app

# Копируем requirements и устанавливаем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код приложения
COPY --chown=agent:agent . .

# Создаем необходимые директории
RUN mkdir -p /app/logs /app/data /app/.agent_conversations && \
    chown -R agent:agent /app

# Переключаемся на непривилегированного пользователя
USER agent

# Открываем порты
EXPOSE 7864 8010 8011

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8010/health || exit 1

# Команда по умолчанию
CMD ["python", "docker_entrypoint.py"]
