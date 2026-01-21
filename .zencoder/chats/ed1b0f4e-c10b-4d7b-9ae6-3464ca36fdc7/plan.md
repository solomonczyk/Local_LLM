# Spec and build

## Agent Instructions

Ask the user questions when anything is unclear or needs their input. This includes:

- Ambiguous or incomplete requirements
- Technical decisions that affect architecture or user experience
- Trade-offs that require business context

Do not make assumptions on important decisions — get clarification first.

---

## Workflow Steps

### [x] Step: Project Audit

Research and analyze the existing codebase structure, dependencies, and architecture.

- [x] Analyze file structure and core components.
- [x] Review dependencies in `requirements.txt` and `pyproject.toml`.
- [x] Identify key frameworks (FastAPI, Gradio, SQLAlchemy).

### [x] Step: Technical Specification

Assess the task's difficulty and create a specification.

- [x] Assess difficulty: easy
- [x] Create `spec.md` with implementation details.

### [ ] Step: Implementation: 27D.1 — Signal enrichment

Implement the changes in `agent_runtime/orchestrator/consilium.py`.

- [ ] Add `override_context` dictionary to `_build_director_request`.
- [ ] Append `override_context` to `facts` list.
- [ ] Verify the changes.
- [ ] Write `report.md`.

### [ ] Step: Final Report
