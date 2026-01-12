# Documentation

## Docker Quick Start
- Start core services: `docker compose up --build -d postgres agent-system nginx`
- UI: `http://localhost:8080` (via nginx) or `http://localhost:7865` (direct)
- LLM API: `http://localhost:8002/health`
- Tools API: `http://localhost:8003/health`
- Optional HTTPS: `docker compose --profile https up -d nginx-https` -> `https://localhost:8443` (self-signed)
- If HTTPS is enabled and `ssl/` is empty, run `generate_ssl.sh` first.

## Usage
- docs/usage/UI_USAGE.md

## Operations
- docs/ops/DEPLOYMENT.md
- docs/ops/HTTPS_SETUP.md

## Data
- docs/data/POSTGRESQL_INTEGRATION.md
- POSTGRES_MEMORY_SETUP.md

## Capabilities
- AGENT_CAPABILITIES.md

## Component Docs
- agent_system/README.md
