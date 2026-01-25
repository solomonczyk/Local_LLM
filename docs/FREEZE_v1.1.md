# FREEZE v1.1 — Hard Format Gate + Instruction Adherence

## Status
FROZEN

## Scope
- Hard Format Gate (post-processor, server-level)
- Instruction Adherence Eval (CI)
- Format contract:
  - Line 1: exactly "OK"
  - Lines 2–4: exactly 3 non-empty lines starting with "-"

## Guaranteed Properties
- Model output cannot bypass format constraints
- Any format violation causes CI FAIL
- No reliance on prompt persuasion
- No model fine-tuning required
- CI smoke does not require OPENAI_API_KEY (director smoke is key-tolerant via fallback_record_only)

## Locked Components
- gateway/server.py (format gate)
- tools/eval_instruction_adherence.py
- eval/instruction_adherence_cases.jsonl
- CI job: instruction-adherence-eval

## Allowed Changes (without unfreeze)
- Add new eval cases
- Improve logging/metrics
- Refactor code WITHOUT changing behavior

## Forbidden Changes (require unfreeze)
- Format contract changes
- Softening strictness (e.g. OK. allowed)
- Disabling eval or gate
- Moving gate to prompt-level

## Rollback Trigger Conditions
- instruction_adherence_eval == FAIL
- Format gate bypass detected
- Non-deterministic format behavior in prod

## Rollback Target
- Tag: freeze-v1.1

## Owner
System Architect

## Notes
This freeze establishes a non-negotiable output contract.
Any intelligence improvements happen strictly above this layer.
