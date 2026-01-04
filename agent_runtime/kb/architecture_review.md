# Architecture review guide (local)

## 1) Goals
- Clarity: obvious flow of data and control
- Boundaries: clear separation of concerns
- Evolvability: easy to add new tools/agents/models
- Reliability: timeouts, retries, logging, observability
- Security: least privilege for tools

## 2) Recommended structure
- gateway/: API surface for IDE clients (OpenAI-compatible)
- orchestrator/: policies, agent coordination, consensus logic
- tools/: isolated tool server with strict sandbox
- kb/: knowledge packs (security/arch/testing)
- configs/: environment-based configuration
- logs/: audit trails, metrics

## 3) Interfaces (contracts)
- LLM contract: /v1/chat/completions (+ optional /v1/models)
- Tool contract: read_file, list_dir, write_patch, git, shell
- Orchestrator contract: run_task(task)-> plan/actions/result

## 4) Common pitfalls
- "God prompt": mixing policy and task instructions in one blob
- Unbounded context: sending too much repo content to LLM
- No caching: repeated reads and list_dir on every call
- Unsafe tools: raw shell execution without allowlist
- No rollback: patch applies with no backup

## 5) Performance levers
- Cache repo snapshot
- Cache frequently-read files with TTL
- Parallelize independent agents
- Use hierarchical consensus (2-3 specialists + critic)
- Reduce 2-pass: only when file content is required

## 6) Output rules for Architect agent
Always return:
- Current state (what you infer)
- Risks (ranked)
- Target architecture (high level)
- Concrete refactors (small steps)
- "Next 3 actions" checklist
