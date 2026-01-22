# Documentation

## Docker Quick Start
- Download the local GGUF model (once): `python tools/download_models.py`
  - Expected output file: `models/qwen2.5-coder-1.5b-instruct-q4_k_m.gguf`
- Start core services: `docker compose up --build -d postgres llm agent-system nginx`
- Windows one-command helper (recommended): `tools\\up.ps1` (runs `tools\\doctor.ps1` first)
- UI: `http://localhost:8080` (via nginx) or `http://localhost:7865` (direct)
- LLM API: `http://localhost:8002/health`
- LLM API via nginx: `http://localhost:8080/v1/models` (note: `/api/*` is reserved for Gradio UI internals)
- Tools API: `http://localhost:8003/health`
- Tools API via nginx: `http://localhost:8080/tools/health`
- Optional HTTPS: `docker compose --profile https up -d nginx-https` -> `https://localhost:8443` (self-signed)
- If HTTPS is enabled and `ssl/` is empty, run `generate_ssl.sh` first.

## Audit
- Run the Consilium audit with host ports: `tools\\audit.ps1`
- Optional: `tools\\audit.ps1 -ConsiliumMode STANDARD`
- The report is saved in `reports/consilium_audit_*.json`

## Host CLI
- For running CLI from the host (not inside Docker), set:
  - `AGENT_LLM_URL=http://localhost:8002/v1`
  - `TOOL_SERVER_URL=http://localhost:8003`

## Search Limits
- Search tool limits are configurable via env:
  - `SEARCH_MAX_HITS` (default 200)
  - `SEARCH_MAX_FILES` (default 5000)
  - `SEARCH_MAX_SECONDS` (default 10)
  - `SEARCH_EXCLUDE_DIRS` (comma-separated)

## Tool Enforcement
- For tasks that mention files/configs/search, the tool-enabled path requires `search` (when no explicit path)
  and `read_file` before answering.
- When both are required, the agent is forced to pick a `read_file` path from `search` results.

## Nginx DNS
- Nginx uses Docker DNS (`127.0.0.11`) with variable `proxy_pass` to avoid stale upstream IPs after container restarts.

## ML / LoRA (Optional)
- Docker runtime uses `llama.cpp + GGUF`; HF/LoRA training deps are not installed in the container.
- For training on the host: `pip install -r requirements-ml.txt`

## Workspace
- The host repo is mounted into the container at `/workspace` and tools are restricted to that root (`AGENT_WORKSPACE=/workspace`).
- Destructive actions are always gated via the UI "Pending Actions" approval button.

## Usage
- docs/usage/UI_USAGE.md

## Operations
- docs/ops/DEPLOYMENT.md
- docs/ops/HTTPS_SETUP.md
- docs/ops/GITHUB_PAT.md

## Data
- docs/data/POSTGRESQL_INTEGRATION.md
- POSTGRES_MEMORY_SETUP.md

## Capabilities
- AGENT_CAPABILITIES.md

## Architecture
- consilium.md
- docs/ROADMAP_RESTORE_RU.md
- docs/EVAL_SUITE_RU.md

## Component Docs
- agent_system/README.md
