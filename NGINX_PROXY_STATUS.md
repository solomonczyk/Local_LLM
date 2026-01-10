# Nginx Proxy Configuration Status Report

**Date**: 2026-01-09  
**Server**: 152.53.227.37  
**Project**: Agent System (Hybrid Architecture)

---

## Problem Summary

Agent System UI недоступен извне из-за firewall ограничений облачного провайдера. Только порты 22, 80, 443 открыты. Необходимо использовать nginx reverse proxy для доступа к UI и API через HTTPS.

---

## Current Infrastructure

### Cloud Firewall
- **Open ports**: 22 (SSH), 80 (HTTP), 443 (HTTPS)
- **Blocked**: All other ports (7865, 8002, 8012, 8013, etc.)
- **Impact**: Direct access to container ports impossible

### Existing Nginx Setup (izborator_nginx)
- **Container**: `izborator_nginx`
- **Config location**: `/root/Izborator/nginx/nginx.conf` (source)
- **Build method**: Docker image built from `/root/Izborator/nginx/Dockerfile`
- **Ports**: 80:80, 443:443
- **SSL**: Let's Encrypt certificates for `152.53.227.37.nip.io`

### Agent System Container (agent-system)
**Container ID**: 6528edb2c1c9

**Port Mappings**:
```
0.0.0.0:8002 → 7861 (UI - Gradio)
0.0.0.0:8012 → 8010 (LLM Gateway)
0.0.0.0:8013 → 8011 (Tools API)
```

**Internal Services**:
- UI listens on `0.0.0.0:7861` inside container
- LLM Gateway on `0.0.0.0:8010`
- Tools API on `0.0.0.0:8011`

---

## Nginx Configuration Analysis

### Existing Agent Subdomains (Already Configured!)

Nginx уже имеет конфигурацию для Agent System с тремя поддоменами:

#### 1. Agent UI
```nginx
server_name: agent.152.53.227.37.nip.io
proxy_pass: http://172.17.0.1:8002
```
**Status**: ✅ Correct (maps to host port 8002 → container 7861)

#### 2. Agent LLM API
```nginx
server_name: api.152.53.227.37.nip.io
proxy_pass: http://172.17.0.1:8012
```
**Status**: ✅ Correct (maps to host port 8012 → container 8010)

#### 3. Agent Tools API
```nginx
server_name: tools.152.53.227.37.nip.io
proxy_pass: http://172.17.0.1:8013
```
**Status**: ✅ Correct (maps to host port 8013 → container 8011)

### Configuration File Status

**Source file**: `/root/Izborator/nginx/nginx.conf`
- All three proxy_pass directives updated to correct ports ✅
- SSL certificates configured ✅
- WebSocket support (Upgrade headers) configured ✅
- Rate limiting configured ✅

**Running container**: `izborator_nginx`
- Still using OLD configuration (7865, 8002, 8003)
- Needs rebuild to apply changes ❌

---

## Root Cause

Nginx container был построен с устаревшими портами и не был пересобран после обновления конфигурации. Контейнер agent-system использует порты 8002/8012/8013, но nginx проксирует на старые порты 7865/8002/8003.

---

## Solution

### Step 1: Rebuild Nginx Container
```bash
cd /root/Izborator
docker-compose build nginx
docker-compose up -d nginx
```

**Impact**: 
- Minimal downtime (~5-10 seconds)
- Izborator project unaffected (separate server blocks)
- Agent System becomes accessible via HTTPS

### Step 2: Verify Access
After rebuild, test endpoints:

```bash
# UI
curl -I https://agent.152.53.227.37.nip.io/

# LLM API health
curl https://api.152.53.227.37.nip.io/health

# Tools API health  
curl https://tools.152.53.227.37.nip.io/health
```

### Step 3: Update Agent System Environment (if needed)
If external access URLs needed in config:
```bash
AGENT_UI_URL=https://agent.152.53.227.37.nip.io
AGENT_API_URL=https://api.152.53.227.37.nip.io
AGENT_TOOLS_URL=https://tools.152.53.227.37.nip.io
```

---

## Architecture Diagram

```
Internet (HTTPS/443)
    ↓
izborator_nginx (80/443)
    ├─→ 152.53.227.37.nip.io → Izborator Frontend/Backend
    ├─→ agent.152.53.227.37.nip.io → 172.17.0.1:8002 → agent-system:7861 (UI)
    ├─→ api.152.53.227.37.nip.io → 172.17.0.1:8012 → agent-system:8010 (LLM)
    └─→ tools.152.53.227.37.nip.io → 172.17.0.1:8013 → agent-system:8011 (Tools)

agent-system container
    ├─→ 7861: Gradio UI
    ├─→ 8010: LLM Gateway (routes to ngrok/OpenAI)
    └─→ 8011: Tools API

External LLM Services
    ├─→ https://5e963ab1e6f1.ngrok-free.app → Qwen 2.5 LoRA (Windows)
    └─→ OpenAI API → GPT-5.2 (Director only)
```

---

## Risks & Mitigations

### Risk 1: Nginx Rebuild Breaks Izborator
**Probability**: Low  
**Mitigation**: Agent config в отдельных server blocks, не пересекается с Izborator  
**Rollback**: `docker-compose restart nginx` восстановит из образа

### Risk 2: SSL Certificate Issues
**Probability**: Low  
**Mitigation**: Certificates уже существуют для wildcard `*.152.53.227.37.nip.io`  
**Verification**: Проверено в текущей конфигурации

### Risk 3: WebSocket Connection Issues
**Probability**: Medium  
**Mitigation**: Upgrade headers уже настроены в конфиге  
**Fallback**: Gradio поддерживает HTTP polling если WebSocket fails

---

## Next Actions

1. **Immediate**: Rebuild nginx container (команда выше)
2. **Verify**: Test all three endpoints
3. **Monitor**: Check nginx logs for errors
4. **Document**: Update deployment docs with correct URLs

---

## Technical Details

### Nginx Config Sections Modified
- Lines 92-122: Agent UI server block
- Lines 124-147: Agent LLM API server block  
- Lines 149-174: Agent Tools API server block

### Docker Network
- Network: `root_agent-network`
- Bridge IP: `172.17.0.1` (Docker host from container perspective)
- Containers: `izborator_nginx`, `agent-system`, `agent-postgres`

### SSL Configuration
- Protocol: TLSv1.2, TLSv1.3
- Certificates: Let's Encrypt
- HSTS: Enabled (31536000s)
- Security headers: X-Frame-Options, X-Content-Type-Options, X-XSS-Protection

---

## Status: READY FOR DEPLOYMENT

Configuration файл обновлен и проверен. Требуется только rebuild nginx контейнера для применения изменений.
