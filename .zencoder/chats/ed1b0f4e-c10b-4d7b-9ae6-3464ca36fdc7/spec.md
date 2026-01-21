# Technical Specification: 27D.1 — Signal enrichment

## Technical Context
- **Language**: Python
- **Components**: `Consilium` orchestrator, `DirectorRequest` payload
- **Target**: Enriching data sent to the Director to include override reasoning.

## Implementation Approach
The goal is to provide `override_context` to the Director so it understands the reason for an override. We will implement this by:
1.  Defining the `override_context` structure in the `_build_director_request` method of the `Consilium` class.
2.  Injecting this context into the `facts` list of the `DirectorRequest` object.
3.  Ensuring the context is passed as a structured string (e.g., JSON or formatted string) to maintain visibility in the Director's prompt.

We will add the following block:
```python
override_context = {
    "present": True,
    "source": "human",
    "reason": "temporal_hard_gate_bypassed",
    "temporal_state": "HARD",
    "escalation_window_hours": 72,
    "override_decision": "allow"
}
```
And append it to facts:
`facts.append(f"override_context={json.dumps(override_context)}")`

## Source Code Structure Changes
- `agent_runtime/orchestrator/consilium.py`: Modify `_build_director_request` to include the new signal.

## Data Model / API / Interface Changes
- No changes to the `DirectorRequest` dataclass itself to avoid breaking compatibility.
- The `facts` field (List[str]) will now contain an additional entry for `override_context`.

## Verification Approach
- **Unit Tests**: Verify that `_build_director_request` correctly includes the `override_context` in the `facts` list.
- **Integration Test**: Check that `DirectorRequest.validate()` still passes (length of facts <= 10).
- **Manual Check**: Inspect the generated prompt to ensure the new context is visible.
