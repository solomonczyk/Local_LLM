#!/bin/bash

# 🔒 Скрипт настройки HTTPS для Agent System
# Использует Let's Encrypt для получения бесплатного SSL сертификата

set -e

echo "🔒 Настройка HTTPS для Agent System..."
echo "=================================="

# Проверяем, что скрипт запущен от root
if [ "$EUID" -ne 0 ]; then
    echo "❌ Запустите скрипт от root: sudo ./setup-https.sh"
    exit 1
fi

# Устанавливаем certbot
echo "📦 Устанавливаем certbot..."
apt update
apt install -y certbot python3-certbot-nginx

# Останавливаем nginx если запущен
echo "🛑 Останавливаем nginx..."
systemctl stop nginx 2>/dev/null || docker stop agent-nginx 2>/dev/null || true

# Получаем SSL сертификат для основного домена
echo "🔐 Получаем SSL сертификат для 152.53.227.37.nip.io..."
certbot certonly --standalone \
    --email admin@152.53.227.37.nip.io \
    --agree-tos \
    --no-eff-email \
    -d 152.53.227.37.nip.io \
    -d agent.152.53.227.37.nip.io \
    -d api.152.53.227.37.nip.io \
    -d llm.152.53.227.37.nip.io \
    -d tools.152.53.227.37.nip.io

# Проверяем, что сертификат создан
if [ ! -f "/etc/letsencrypt/live/152.53.227.37.nip.io/fullchain.pem" ]; then
    echo "❌ Ошибка: SSL сертификат не создан!"
    exit 1
fi

echo "✅ SSL сертификат успешно создан!"

# Копируем новую конфигурацию nginx
echo "📝 Обновляем конфигурацию nginx..."
cp nginx-https.conf nginx.conf

# Создаем директорию для SSL в контейнере
echo "📁 Настраиваем SSL директории..."
mkdir -p ./ssl
cp -r /etc/letsencrypt ./ssl/

# Обновляем docker-compose.yml для монтирования SSL
echo "🐳 Обновляем docker-compose для SSL..."
cat > docker-compose-https.yml << 'EOF'
version: '3.8'

services:
  # PostgreSQL база данных
  postgres:
    image: postgres:14-alpine
    container_name: agent-postgres
    environment:
      POSTGRES_DB: agent_memory
      POSTGRES_USER: agent_user
      POSTGRES_PASSWORD: agent_password
      POSTGRES_INITDB_ARGS: "--encoding=UTF-8 --lc-collate=ru_RU.UTF-8 --lc-ctype=ru_RU.UTF-8"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init_db.sql:/docker-entrypoint-initdb.d/init_db.sql
    ports:
      - "5435:5432"
    networks:
      - agent-network
    restart: unless-stopped
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U agent_user -d agent_memory"]
      interval: 10s
      timeout: 5s
      retries: 5

  # Агентская система
  agent-system:
    build: .
    container_name: agent-system
    environment:
      # PostgreSQL подключение
      POSTGRES_HOST: postgres
      POSTGRES_PORT: 5432
      POSTGRES_DB: agent_memory
      POSTGRES_USER: agent_user
      POSTGRES_PASSWORD: agent_password
      
      # Конфигурация агента
      CONSILIUM_MODE: STANDARD
      KB_TOP_K: 5
      KB_MAX_CHARS: 8000
      
      # Безопасность
      AGENT_ACCESS_LEVEL: 2
      
    ports:
      - "7865:7864"  # UI
      - "8002:8010"  # LLM API
      - "8003:8011"  # Tools API
    volumes:
      - agent_data:/app/data
      - agent_logs:/app/logs
      - agent_conversations:/app/.agent_conversations
    networks:
      - agent-network
    depends_on:
      postgres:
        condition: service_healthy
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8010/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s

  # Nginx reverse proxy с SSL
  nginx:
    image: nginx:alpine
    container_name: agent-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./ssl/letsencrypt:/etc/letsencrypt:ro
    networks:
      - agent-network
    depends_on:
      - agent-system
    restart: unless-stopped

volumes:
  postgres_data:
    driver: local
  agent_data:
    driver: local
  agent_logs:
    driver: local
  agent_conversations:
    driver: local

networks:
  agent-network:
    driver: bridge
EOF

# Перезапускаем с новой конфигурацией
echo "🚀 Перезапускаем сервисы с HTTPS..."
docker-compose -f docker-compose-https.yml down
docker-compose -f docker-compose-https.yml up -d

# Настраиваем автообновление сертификата
echo "🔄 Настраиваем автообновление SSL сертификата..."
(crontab -l 2>/dev/null; echo "0 12 * * * /usr/bin/certbot renew --quiet && docker-compose -f /root/docker-compose-https.yml restart nginx") | crontab -

echo ""
echo "🎉 HTTPS успешно настроен!"
echo "=========================="
echo ""
echo "🌐 Ваши HTTPS ссылки:"
echo "   • Agent UI:   https://agent.152.53.227.37.nip.io"
echo "   • LLM API:    https://api.152.53.227.37.nip.io"
echo "   • Tools API:  https://tools.152.53.227.37.nip.io"
echo ""
echo "🔒 SSL сертификат действителен 90 дней"
echo "🔄 Автообновление настроено через cron"
echo ""
echo "✅ Готово! Теперь можно использовать HTTPS"