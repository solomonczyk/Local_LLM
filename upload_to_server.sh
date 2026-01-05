#!/bin/bash
# Скрипт для загрузки агентской системы на сервер

SERVER="root@152.53.227.37"
REMOTE_DIR="/opt/agent-system"

echo "🚀 Uploading Agent System to server..."

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

# Создаем директорию на сервере
log "Creating directory on server..."
ssh $SERVER "mkdir -p $REMOTE_DIR"

# Создаем архив с исключением ненужных файлов
log "Creating deployment archive..."
tar --exclude='.git' \
    --exclude='__pycache__' \
    --exclude='*.pyc' \
    --exclude='.venv*' \
    --exclude='test_*' \
    --exclude='codesearchnet_*' \
    --exclude='lora_*' \
    --exclude='*.backup' \
    --exclude='*.deleted_backup' \
    --exclude='.agent_*' \
    --exclude='logs' \
    --exclude='data' \
    -czf agent-system.tar.gz .

# Загружаем архив на сервер
log "Uploading files to server..."
scp agent-system.tar.gz $SERVER:$REMOTE_DIR/

# Распаковываем на сервере
log "Extracting files on server..."
ssh $SERVER "cd $REMOTE_DIR && tar -xzf agent-system.tar.gz && rm agent-system.tar.gz"

# Делаем скрипты исполняемыми
log "Setting permissions..."
ssh $SERVER "cd $REMOTE_DIR && chmod +x deploy.sh docker_entrypoint.py"

# Удаляем локальный архив
rm agent-system.tar.gz

log "✅ Files uploaded successfully!"
log "📁 Remote directory: $REMOTE_DIR"

# Предлагаем запустить деплой
echo ""
echo "🎯 Next steps:"
echo "1. Connect to server: ssh $SERVER"
echo "2. Go to directory: cd $REMOTE_DIR"
echo "3. Run deployment: ./deploy.sh"
echo ""
echo "Or run deployment remotely:"
echo "ssh $SERVER 'cd $REMOTE_DIR && ./deploy.sh'"