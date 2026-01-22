# Local Consilium System - Task Definition

## Goal
Build a local-first, multi-agent system that acts as a high-productivity "vibe-coding" assistant. Agents debate a task, produce a consolidated solution, and a Director (GPT-5.2) provides the final expert decision. All actions require explicit confirmation.

## Functional Requirements
- Multi-agent consilium with defined roles (dev, security, qa, architect, ux, seo, director).
- Agents perform a "brainstorm" and merge into one best answer.
- Director reviews consilium output and produces an expert conclusion.
- Tools comparable to Codex/Cursor/Kiro: file CRUD, code search, shell, git, DB ops, system info.
- UI must support approvals for tool actions.
- Local-first by default; cloud only for Director (GPT-5.2).

## Non-Functional Requirements
- Deterministic approvals: no tool execution without user confirmation.
- Scale to multiple tasks and sessions without state bleed.
- Maintainable configuration for LLM endpoints and models.
- Clear bootstrapping for required local models.

## Target Architecture (High Level)
- UI (Gradio) -> Orchestrator -> Consilium (multi-agent) -> Director (GPT-5.2).
- LLM backend must be real (no mock) and local (model assets external to git).
- Tool server exposes safe operations with audit logging.

## Current Gaps
- Tool-use reliability: the LLM can still output invalid/partial `TOOL_CALLS` JSON; needs hardening for Cursor-like UX.
- LoRA training pipeline is not integrated yet (model personalization pending).
- Director must be gated + sanitized to minimize cloud data exposure (optional).

## Risks
- Quality risk: mock LLM yields non-actionable results.
- Reliability risk: missing model assets break the main workflow.
- Maintainability risk: model weights inside git are not viable long-term.

## Required Artifacts (Out-of-Repo)
- Local model weights (base + LoRA) OR a GGUF model for llama.cpp.
- A documented bootstrap step to fetch or link these assets.
- Fail-fast check when model assets are missing.

## Success Criteria
- Consilium produces relevant, multi-angle responses for real tasks.
- Director summarizes and improves the consilium result.
- Tool approvals function reliably with no unintended execution.
- Local-first LLM works without external endpoints (except Director).

## Next Steps (Planned)
- Harden tool-call parsing and the “tool -> result -> final” loop.
- Integrate a measurable eval loop for Consilium/tool-use.
- Add LoRA training pipeline (per `Local_LLM` notes) after baseline stability.
