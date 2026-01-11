# 🚀 Деплой агентской системы

## 📋 Быстрый старт

### 1. Подготовка сервера
```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Установка Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/download/v2.20.0/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Перезагрузка для применения изменений
sudo reboot
```

### 2. Деплой системы
```bash
# Клонирование репозитория
git clone <your-repo-url> agent-system
cd agent-system

# Запуск деплоя
chmod +x deploy.sh
./deploy.sh
```

### 3. Проверка работы
```bash
# Проверка статуса сервисов
docker-compose ps

# Просмотр логов
docker-compose logs -f

# Проверка здоровья
curl http://localhost:8000/health
```

## 🏗️ Архитектура деплоя

```
┌─────────────────┐
│     Nginx       │ ← Reverse Proxy (порт 80/443)
│   (Optional)    │
└─────────────────┘
         │
         ▼
┌─────────────────┐
│ Agent System    │ ← Основное приложение
│   Container     │   Порты: 7864, 8000, 8001
└─────────────────┘
         │
         ▼
┌─────────────────┐
│   PostgreSQL    │ ← База данных
│   Container     │   Порт: 5432
└─────────────────┘
```

## 🔧 Конфигурация

### Переменные окружения (.env)
```bash
# PostgreSQL
POSTGRES_DB=agent_memory
POSTGRES_USER=agent_user
POSTGRES_PASSWORD=your_secure_password

# Agent System
CONSILIUM_MODE=STANDARD          # FAST/STANDARD/CRITICAL
KB_TOP_K=5                       # Количество результатов из KB
KB_MAX_CHARS=8000               # Максимум символов из KB
AGENT_ACCESS_LEVEL=2            # Уровень доступа (0-4)

# Security
SECRET_KEY=your_secret_key
DOMAIN=your-domain.com          # Для SSL
```

### Порты
- **7864** - Web UI (Gradio интерфейс)
- **8000** - LLM API (OpenAI-совместимый)
- **8001** - Tools API (системные инструменты)
- **5432** - PostgreSQL (внутренний)
- **80/443** - Nginx (если используется)

## 📊 Мониторинг

### Проверка здоровья сервисов
```bash
# Статус контейнеров
docker-compose ps

# Использование ресурсов
docker stats

# Логи сервисов
docker-compose logs agent-system
docker-compose logs postgres
```

### Health Check эндпоинты
```bash
# Основное приложение
curl http://localhost:8000/health

# Система памяти
curl http://localhost:8001/tools/memory_status

# UI (должен вернуть HTML)
curl http://localhost:7864
```

## 🔒 Безопасность

### Рекомендации для продакшена
1. **Смените пароли** в .env файле
2. **Настройте SSL** через Let's Encrypt
3. **Ограничьте доступ** к портам через firewall
4. **Регулярно обновляйте** образы
5. **Настройте бэкапы** PostgreSQL

### Firewall настройки
```bash
# Разрешить только необходимые порты
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### SSL сертификат (Let's Encrypt)
```bash
# Установка Certbot
sudo apt install certbot

# Получение сертификата
sudo certbot certonly --standalone -d your-domain.com

# Копирование в проект
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/cert.pem
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/key.pem
sudo chown $USER:$USER ./ssl/*
```

## 📈 Масштабирование

### Горизонтальное масштабирование
```yaml
# docker-compose.yml
services:
  agent-system:
    deploy:
      replicas: 3
    # ... остальная конфигурация
```

### Вертикальное масштабирование
```yaml
# docker-compose.yml
services:
  agent-system:
    deploy:
      resources:
        limits:
          cpus: '2.0'
          memory: 4G
        reservations:
          cpus: '1.0'
          memory: 2G
```

## 🗄️ Бэкапы

### PostgreSQL бэкап
```bash
# Создание бэкапа
docker-compose exec postgres pg_dump -U agent_user agent_memory > backup_$(date +%Y%m%d_%H%M%S).sql

# Восстановление
docker-compose exec -T postgres psql -U agent_user agent_memory < backup_file.sql
```

### Автоматические бэкапы
```bash
# Добавить в crontab
0 2 * * * cd /path/to/agent-system && docker-compose exec postgres pg_dump -U agent_user agent_memory > backups/backup_$(date +\%Y\%m\%d_\%H\%M\%S).sql
```

## 🔄 Обновление

### Обновление системы
```bash
# Остановка сервисов
docker-compose down

# Обновление кода
git pull

# Пересборка и запуск
./deploy.sh update
```

### Откат к предыдущей версии
```bash
# Откат кода
git checkout previous-version

# Пересборка
docker-compose build --no-cache
docker-compose up -d
```

## 🐛 Troubleshooting

### Частые проблемы

#### Сервис не запускается
```bash
# Проверить логи
docker-compose logs service-name

# Проверить ресурсы
docker stats

# Перезапустить сервис
docker-compose restart service-name
```

#### База данных недоступна
```bash
# Проверить статус PostgreSQL
docker-compose exec postgres pg_isready -U agent_user

# Проверить подключение
docker-compose exec postgres psql -U agent_user -d agent_memory -c "SELECT 1;"
```

#### Порты заняты
```bash
# Найти процесс на порту
sudo netstat -tulpn | grep :8000

# Остановить конфликтующий сервис
sudo systemctl stop service-name
```

## 📞 Поддержка

При проблемах с деплоем:
1. Проверьте логи: `docker-compose logs -f`
2. Убедитесь в доступности ресурсов: `docker stats`
3. Проверьте конфигурацию: `.env` файл
4. Перезапустите сервисы: `docker-compose restart`

**Система готова к продакшен использованию!** 🎉