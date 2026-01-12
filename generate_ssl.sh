#!/bin/bash
# Генерация самоподписанных SSL сертификатов для agent-system

echo "🔐 Generating SSL certificates for agent-system..."

# Создаем директорию для SSL
mkdir -p ssl

# Генерируем приватный ключ
openssl genrsa -out ssl/agent.key 2048

# Создаем конфигурационный файл для сертификата
cat > ssl/agent.conf << EOF
[req]
distinguished_name = req_distinguished_name
req_extensions = v3_req
prompt = no

[req_distinguished_name]
C = RU
ST = Moscow
L = Moscow
O = Agent System
OU = Development
CN = agent.152.53.227.37.nip.io

[v3_req]
keyUsage = keyEncipherment, dataEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names

[alt_names]
DNS.1 = agent.152.53.227.37.nip.io
DNS.2 = api.152.53.227.37.nip.io
DNS.3 = tools.152.53.227.37.nip.io
DNS.4 = 152.53.227.37.nip.io
DNS.5 = localhost
IP.1 = 152.53.227.37
IP.2 = 127.0.0.1
EOF

# Генерируем сертификат
openssl req -new -x509 -key ssl/agent.key -out ssl/agent.crt -days 365 -config ssl/agent.conf -extensions v3_req

# Устанавливаем правильные права
chmod 600 ssl/agent.key
chmod 644 ssl/agent.crt

echo "✅ SSL certificates generated:"
echo "   Private key: ssl/agent.key"
echo "   Certificate: ssl/agent.crt"
echo ""
echo "🌐 HTTPS endpoints will be available on:"
echo "   UI:    https://agent.152.53.227.37.nip.io:8443"
echo "   API:   https://api.152.53.227.37.nip.io:8443"
echo "   Tools: https://tools.152.53.227.37.nip.io:8443"
echo ""
echo "⚠️  Note: These are self-signed certificates."
echo "   Browsers will show security warnings."
echo "   For production, use Let's Encrypt certificates."
