# Testing strategy guide (local)

## 1) Principles
- Prefer fast unit tests over slow integration tests
- Test behavior, not implementation details
- Include edge cases and failure modes
- Tests must be deterministic and runnable locally

## 2) Pyramid
- Unit: pure functions, validators, parsers
- Integration: tool server endpoints, gateway routing
- End-to-end (minimal): Continue->gateway->orchestrator->LLM mock

## 3) What to test in this project
- Tool server:
  - path sandboxing (no escape)
  - read_file limits and errors
  - list_dir sorting and limits
  - write_patch applies correctly
- Orchestrator:
  - snapshot cache behavior
  - READ_FILE detection
  - 2-pass only when needed
  - parallel consilium returns all results
- Gateway:
  - OpenAI-compatible response shape
  - timeout handling
  - error mapping

## 4) Checks to run
- Lint/format: ruff/black (or chosen stack)
- Type checks: mypy/pyright (optional)
- Unit tests: pytest -q
- Smoke: simple curl to /health and /v1/chat/completions

## 5) Output rules for QA agent
Always return:
- Test plan (bullets)
- Key edge cases
- Suggested test names
- Minimal commands to run
