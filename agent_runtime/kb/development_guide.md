# Development guide (local)

## 1) Code quality principles
- Write clear, self-documenting code
- Follow language-specific conventions (PEP 8 for Python, etc.)
- Keep functions small and focused (single responsibility)
- Avoid premature optimization
- Comment why, not what

## 2) Implementation approach
- Start with the simplest solution that works
- Refactor incrementally
- Test as you go
- Handle errors gracefully
- Log important events

## 3) Common patterns
- Use type hints (Python 3.6+)
- Prefer composition over inheritance
- Use context managers for resources
- Validate inputs early
- Return early on error conditions

## 4) Performance considerations
- Profile before optimizing
- Cache expensive operations
- Use appropriate data structures
- Avoid N+1 queries
- Batch operations when possible

## 5) Code review checklist
- Does it solve the problem?
- Is it readable?
- Are edge cases handled?
- Are there tests?
- Is error handling appropriate?

## 6) Output rules for Dev agent
Always return:
- Implementation approach (high level)
- Key functions/classes needed
- Potential issues to watch for
- Testing recommendations
- Estimated complexity (simple/medium/complex)
