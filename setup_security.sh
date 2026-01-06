#!/bin/bash
# Скрипт настройки базовой безопасности для Agent System

echo "🔒 Setting up basic security..."

# Базовые правила iptables
echo "📋 Configuring firewall rules..."

# Разрешаем loopback
iptables -A INPUT -i lo -j ACCEPT
iptables -A OUTPUT -o lo -j ACCEPT

# Разрешаем установленные соединения
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

# Разрешаем SSH (порт 22)
iptables -A INPUT -p tcp --dport 22 -j ACCEPT

# Разрешаем HTTP/HTTPS (порты 80, 443)
iptables -A INPUT -p tcp --dport 80 -j ACCEPT
iptables -A INPUT -p tcp --dport 443 -j ACCEPT

# Разрешаем Agent System порты только с localhost (безопасность)
iptables -A INPUT -p tcp -s 127.0.0.1 --dport 7865 -j ACCEPT
iptables -A INPUT -p tcp -s 127.0.0.1 --dport 8002 -j ACCEPT
iptables -A INPUT -p tcp -s 127.0.0.1 --dport 8003 -j ACCEPT

# Блокируем прямой доступ к Agent System портам извне
iptables -A INPUT -p tcp --dport 7865 -j DROP
iptables -A INPUT -p tcp --dport 8002 -j DROP
iptables -A INPUT -p tcp --dport 8003 -j DROP

# Блокируем прямой доступ к PostgreSQL
iptables -A INPUT -p tcp --dport 5432 -j DROP
iptables -A INPUT -p tcp --dport 5435 -j DROP

# Устанавливаем политику по умолчанию
iptables -P INPUT DROP
iptables -P FORWARD DROP
iptables -P OUTPUT ACCEPT

echo "✅ Firewall rules configured"

# Сохраняем правила
if command -v iptables-save >/dev/null 2>&1; then
    iptables-save > /etc/iptables/rules.v4 2>/dev/null || echo "⚠️  Could not save iptables rules"
fi

# Создаем базовую аутентификацию для API
echo "🔑 Setting up API authentication..."

# Генерируем API ключ
API_KEY=$(openssl rand -hex 32)
echo "Generated API Key: $API_KEY"

# Создаем конфигурационный файл
cat > /opt/agent-system/security_config.json << EOF
{
    "api_key": "$API_KEY",
    "rate_limits": {
        "requests_per_minute": 60,
        "requests_per_hour": 1000
    },
    "allowed_origins": [
        "https://152.53.227.37.nip.io",
        "https://agent.152.53.227.37.nip.io",
        "https://api.152.53.227.37.nip.io",
        "https://tools.152.53.227.37.nip.io"
    ],
    "security_headers": {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains"
    }
}
EOF

echo "✅ Security config created at /opt/agent-system/security_config.json"

# Создаем backup скрипт
echo "💾 Setting up backup script..."

cat > /opt/agent-system/backup_db.sh << 'EOF'
#!/bin/bash
# Автоматический backup PostgreSQL

BACKUP_DIR="/opt/agent-system/backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/agent_memory_$DATE.sql"

# Создаем директорию для backup'ов
mkdir -p $BACKUP_DIR

# Создаем backup
docker exec agent-postgres pg_dump -U agent_user agent_memory > $BACKUP_FILE

if [ $? -eq 0 ]; then
    echo "✅ Backup created: $BACKUP_FILE"
    
    # Сжимаем backup
    gzip $BACKUP_FILE
    echo "✅ Backup compressed: $BACKUP_FILE.gz"
    
    # Удаляем старые backup'ы (старше 7 дней)
    find $BACKUP_DIR -name "*.gz" -mtime +7 -delete
    echo "🧹 Old backups cleaned up"
else
    echo "❌ Backup failed"
    exit 1
fi
EOF

chmod +x /opt/agent-system/backup_db.sh

# Добавляем в crontab
(crontab -l 2>/dev/null; echo "0 2 * * * /opt/agent-system/backup_db.sh >> /var/log/backup.log 2>&1") | crontab -

echo "✅ Daily backup scheduled at 2:00 AM"

# Создаем скрипт мониторинга
echo "📊 Setting up monitoring..."

cat > /opt/agent-system/health_check.sh << 'EOF'
#!/bin/bash
# Проверка здоровья системы

echo "=== Agent System Health Check ==="
echo "Date: $(date)"
echo ""

# Проверяем контейнеры
echo "🐳 Docker Containers:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
echo ""

# Проверяем порты
echo "🌐 Port Status:"
for port in 80 443 7865 8002 8003; do
    if netstat -tuln | grep -q ":$port "; then
        echo "  ✅ Port $port: LISTENING"
    else
        echo "  ❌ Port $port: NOT LISTENING"
    fi
done
echo ""

# Проверяем дисковое пространство
echo "💾 Disk Usage:"
df -h | grep -E "(/$|/opt)"
echo ""

# Проверяем память
echo "🧠 Memory Usage:"
free -h
echo ""

# Проверяем логи на ошибки
echo "📋 Recent Errors:"
docker logs agent-system 2>&1 | tail -10 | grep -i error || echo "  No recent errors found"
echo ""

echo "=== Health Check Complete ==="
EOF

chmod +x /opt/agent-system/health_check.sh

echo "✅ Health check script created"

# Создаем простой мониторинг endpoint
echo "📡 Setting up monitoring endpoint..."

cat > /opt/agent-system/monitor.py << 'EOF'
#!/usr/bin/env python3
"""
Простой HTTP сервер для мониторинга системы
"""
import json
import subprocess
import psutil
from http.server import HTTPServer, BaseHTTPRequestHandler
from datetime import datetime

class MonitorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            # Собираем информацию о системе
            health_data = {
                'timestamp': datetime.now().isoformat(),
                'status': 'healthy',
                'services': self.check_services(),
                'system': {
                    'cpu_percent': psutil.cpu_percent(),
                    'memory_percent': psutil.virtual_memory().percent,
                    'disk_percent': psutil.disk_usage('/').percent
                }
            }
            
            self.wfile.write(json.dumps(health_data, indent=2).encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def check_services(self):
        services = {}
        
        # Проверяем Docker контейнеры
        try:
            result = subprocess.run(['docker', 'ps', '--format', '{{.Names}}:{{.Status}}'], 
                                  capture_output=True, text=True)
            for line in result.stdout.strip().split('\n'):
                if ':' in line:
                    name, status = line.split(':', 1)
                    services[name] = 'running' if 'Up' in status else 'stopped'
        except:
            services['docker'] = 'error'
        
        return services

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 9999), MonitorHandler)
    print("🔍 Monitor server running on http://127.0.0.1:9999/health")
    server.serve_forever()
EOF

chmod +x /opt/agent-system/monitor.py

echo ""
echo "🎉 Security setup complete!"
echo ""
echo "📋 Summary:"
echo "  ✅ Firewall configured (only SSH, HTTP, HTTPS allowed)"
echo "  ✅ API key generated: $API_KEY"
echo "  ✅ Daily backups scheduled"
echo "  ✅ Health monitoring available"
echo ""
echo "🔧 Next steps:"
echo "  1. Save the API key securely"
echo "  2. Test backup: /opt/agent-system/backup_db.sh"
echo "  3. Check health: /opt/agent-system/health_check.sh"
echo "  4. Start monitor: python3 /opt/agent-system/monitor.py &"
echo ""
echo "⚠️  IMPORTANT: Save this API key: $API_KEY"