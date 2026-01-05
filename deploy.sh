#!/bin/bash
# Скрипт деплоя агентской системы

set -e

echo "🚀 Deploying Agent System..."

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Функция для логирования
log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%Y-%m-%d %H:%M:%S')] WARNING: $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%Y-%m-%d %H:%M:%S')] ERROR: $1${NC}"
}

# Проверка зависимостей
check_dependencies() {
    log "Checking dependencies..."
    
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    if ! command -v docker-compose &> /dev/null; then
        error "Docker Compose is not installed"
        exit 1
    fi
    
    log "Dependencies OK"
}

# Создание .env файла
create_env_file() {
    if [ ! -f .env ]; then
        log "Creating .env file..."
        cat > .env << EOF
# PostgreSQL Configuration
POSTGRES_DB=agent_memory
POSTGRES_USER=agent_user
POSTGRES_PASSWORD=$(openssl rand -base64 32)

# Agent Configuration
CONSILIUM_MODE=STANDARD
KB_TOP_K=5
KB_MAX_CHARS=8000
AGENT_ACCESS_LEVEL=2

# Security
SECRET_KEY=$(openssl rand -base64 32)

# Domain (for SSL)
DOMAIN=localhost
EOF
        log ".env file created"
    else
        log ".env file already exists"
    fi
}

# Сборка образа
build_image() {
    log "Building Docker image..."
    docker-compose build --no-cache
    log "Image built successfully"
}

# Запуск сервисов
start_services() {
    log "Starting services..."
    docker-compose up -d
    
    # Ждем готовности сервисов
    log "Waiting for services to be ready..."
    sleep 30
    
    # Проверяем статус
    if docker-compose ps | grep -q "Up"; then
        log "Services started successfully"
    else
        error "Some services failed to start"
        docker-compose logs
        exit 1
    fi
}

# Инициализация базы данных
init_database() {
    log "Initializing database..."
    
    # Ждем готовности PostgreSQL
    docker-compose exec -T postgres pg_isready -U agent_user -d agent_memory
    
    # Инициализируем схему памяти агента
    log "Setting up agent memory schema..."
    sleep 10
    
    # Проверяем доступность API
    if curl -f http://localhost:8001/tools/memory_status > /dev/null 2>&1; then
        log "Agent API is ready"
        
        # Инициализируем память (если подключение к БД настроено)
        curl -X POST http://localhost:8001/tools/memory_init \
             -H "Content-Type: application/json" \
             -d '{"connection_name": "agent_memory"}' || warn "Memory initialization skipped (DB connection needed)"
    else
        warn "Agent API not ready yet"
    fi
}

# Проверка здоровья системы
health_check() {
    log "Performing health check..."
    
    services=("http://localhost:7864" "http://localhost:8000/health" "http://localhost:8001/tools/memory_status")
    
    for service in "${services[@]}"; do
        if curl -f "$service" > /dev/null 2>&1; then
            log "✅ $service is healthy"
        else
            warn "❌ $service is not responding"
        fi
    done
}

# Показ информации о деплое
show_info() {
    log "🎉 Agent System deployed successfully!"
    echo ""
    echo "📊 Service URLs:"
    echo "   🌐 UI:        http://localhost:7864"
    echo "   🤖 LLM API:   http://localhost:8000"
    echo "   🔧 Tools API: http://localhost:8001"
    echo ""
    echo "📋 Management commands:"
    echo "   View logs:    docker-compose logs -f"
    echo "   Stop:         docker-compose down"
    echo "   Restart:      docker-compose restart"
    echo "   Update:       ./deploy.sh"
    echo ""
    echo "🗄️ Database:"
    echo "   Host:         localhost:5432"
    echo "   Database:     agent_memory"
    echo "   User:         agent_user"
    echo ""
}

# Основная функция
main() {
    log "Starting Agent System deployment..."
    
    check_dependencies
    create_env_file
    build_image
    start_services
    init_database
    health_check
    show_info
    
    log "Deployment completed!"
}

# Обработка аргументов
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "stop")
        log "Stopping services..."
        docker-compose down
        ;;
    "restart")
        log "Restarting services..."
        docker-compose restart
        ;;
    "logs")
        docker-compose logs -f
        ;;
    "update")
        log "Updating system..."
        docker-compose down
        main
        ;;
    *)
        echo "Usage: $0 {deploy|stop|restart|logs|update}"
        exit 1
        ;;
esac