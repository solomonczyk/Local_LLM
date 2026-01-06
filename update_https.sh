#!/bin/bash
# Скрипт для обновления HTTPS конфигурации на продакшене

SERVER="root@152.53.227.37"
REMOTE_DIR="/opt/agent-system"

echo "🔒 Updating HTTPS configuration on production server..."

# Цвета для вывода
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

log() {
    echo -e "${GREEN}[$(date +'%H:%M:%S')] $1${NC}"
}

warn() {
    echo -e "${YELLOW}[$(date +'%H:%M:%S')] $1${NC}"
}

error() {
    echo -e "${RED}[$(date +'%H:%M:%S')] $1${NC}"
}

# Проверяем подключение к серверу
log "Testing connection to server..."
if ! ssh -o ConnectTimeout=10 $SERVER "echo 'Connection OK'"; then
    error "Cannot connect to server $SERVER"
    exit 1
fi

# Загружаем обновленные файлы
log "Uploading updated configuration files..."
scp docker-compose.yml $SERVER:$REMOTE_DIR/
scp nginx-https.conf $SERVER:$REMOTE_DIR/
scp HTTPS_STATUS.md $SERVER:$REMOTE_DIR/

# Перезапускаем nginx с новой конфигурацией
log "Restarting nginx with HTTPS configuration..."
ssh $SERVER "cd $REMOTE_DIR && docker-compose restart nginx"

# Проверяем статус сервисов
log "Checking services status..."
ssh $SERVER "cd $REMOTE_DIR && docker-compose ps"

log "✅ HTTPS configuration updated!"
log "🌐 Test HTTPS endpoints:"
log "   - https://152.53.227.37.nip.io"
log "   - https://agent.152.53.227.37.nip.io"
log "   - https://api.152.53.227.37.nip.io"
log "   - https://tools.152.53.227.37.nip.io"

echo ""
echo "🔍 To check nginx logs:"
echo "ssh $SERVER 'cd $REMOTE_DIR && docker-compose logs nginx'"