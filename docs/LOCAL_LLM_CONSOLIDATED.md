# Local LLM System - Consolidated Technical Notes

## Summary
This document consolidates the Local_LLM materials into one technical source of truth. The system is a local-first, multi-agent "vibe-coding" assistant with a Consilium (agents) and a Director (GPT-5.2) that delivers the final expert decision.

## Core Goal
Build a local system that improves coding productivity:
- Multiple agents debate tasks and produce a single best answer.
- Director (GPT-5.2) reviews and provides expert conclusion.
- Tools comparable to Codex/Cursor/Kiro with explicit user approval.
- Local LLM is the primary engine; cloud is limited to the Director.

## Architecture (Target)
- UI (Gradio) -> Orchestrator -> Consilium (multi-agent) -> Director (GPT-5.2).
- Tool server for CRUD, search, shell, git, DB, system info (approval gated).
- RAG/KB per agent with shared standards for data hygiene and versioning.

## Agent Roles
Expected agents and roles:
- dev: implementation perspective
- security: risk and safety review
- qa: testing strategy
- architect: structure and scalability
- ux: user experience and interface quality
- seo: discoverability and content strategy
- director: final decision (GPT-5.2)

## LLM Strategy
- Primary local model: Qwen2.5-Coder-1.5B
- Fine-tuning: LoRA (project weights)
- Rationale: 1.5B is the correct initial size for latency, iteration speed, and multi-agent load.
- Upgrade path: 7-8B after pipeline stability and evaluation.

## Data Pipelines
Two distinct pipelines are required:
1) RAG/KB pipeline (fast value, low cost)
2) SFT/LoRA pipeline (only after stable recurring patterns)
Mixing them directly is discouraged due to data leakage and brittleness.

## Knowledge Base (KB)
KB must be split by agent domain with explicit mapping:
- security_checklist.md
- architecture_review.md
- testing_strategy.md
Each agent owns its KB. Shared rules govern quality, metadata, and versioning.

## LoRA Training Notes
Training script references:
- train_lora.py
- base model: Qwen/Qwen2.5-Coder-1.5B
- output path: lora_qwen2_5_coder_1_5b_python

LoRA artifacts:
- adapter_model.safetensors (project weights)
- adapter_config.json

Base model weights:
- stored in HuggingFace cache (sharded model.safetensors)
- Windows symlink warning indicates HF cache uses non-symlink mode

## Deployment/Infra Notes
Observed architecture includes:
- Docker services for UI, LLM API, Tools API, Postgres
- Reverse proxy via nginx
- Prior hybrid experiment used ngrok for local LLM exposure
- Port ownership conflicts should be solved via a shared edge proxy

## Known Issues (from notes)
- LLM server can fall back to mock responses if real model is not loaded.
- Docker container can start but internal services may not bind (stale image or code errors).
- Ports 80/443 conflicts with other projects if no shared edge proxy.
- Smart routing misses non-English triggers (Russian tasks under-route).

## Risks
- If LoRA weights are missing, system degenerates to template outputs.
- Keeping weights in git is not sustainable (size, reproducibility).
- Hybrid ngrok flow adds external dependency and reliability risk.

## Required Artifacts (Out-of-Repo)
- LoRA adapter weights for Qwen2.5-Coder-1.5B:
  - adapter_model.safetensors
  - adapter_config.json
- Base model in HF cache (sharded model.safetensors)

## Next Steps (Operational)
1) Locate and restore LoRA adapter weights.
2) Switch LLM server to real inference (serve_lora.py or local GGUF).
3) Re-run Consilium audit with real tasks.
4) Expand smart routing triggers for Russian queries.
5) Document bootstrap steps for model assets and environment.

## Source Notes
The consolidation is based on the Local_LLM documents:
- dok1.docx: datasets for code LLMs
- dok2.docx: LoRA training logs and HF cache warnings
- dok3.docx: KB setup per agent
- dok4.docx: RAG vs SFT separation and pipeline design
- dok5.docx: rationale for 1.5B model
- dok6.docx: hybrid/ngrok deployment issues
- dok7.docx: edge proxy strategy for port sharing
- dok8.docx: docker-compose editing guidance
- dok9.docx: docker-compose build/image troubleshooting
