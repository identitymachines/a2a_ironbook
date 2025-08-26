# x-ironbook (A2A Extension Spec)

**URI:** `https://w3id.org/identitymachines/ironbook/a2a/v1`  
**Type:** Profile/Data extension (no core schema changes)

## Declaration (AgentCard)
Agents advertise support using `capabilities.extensions[]`:

```json
{
  "uri": "https://w3id.org/identitymachines/ironbook/a2a/v1",
  "description": "Policy-gated A2A handoffs with one-shot tokens",
  "required": false,
  "params": { "policy": "llm_guard_v1", "audience": "https://api.identitymachines.com" }
}
```

## Activation

Client sends:

```
X-A2A-Extensions: https://w3id.org/identitymachines/ironbook/a2a/v1
```

Server echoes the same header on success.

## Data Placement

All extension data MUST be under `params.metadata["<URI>/…"]`. Namespaced keys:

* `<URI>/action` — e.g., `"infer"`.
* `<URI>/resource` — e.g., `"llm://responses"`.
* `<URI>/context` — object (purpose, data\_classification, model, region, budget, pii\_detected, etc.); the callee sets `role` to `"requester"` or `"executor"` prior to calling `policy_decision`.
* `<URI>/token` — one-shot Iron Book token for the **subject** of the decision.
* `<URI>/requester_agent_did` — DID of the requester agent (for the executor decision).

## Server Behavior (Two Decisions)

1. Validate activation header and parse namespaced metadata.
2. **Requester check:** `policy_decision(agent_did=<TRIAGE_DID>, policy_id=<POLICY_ID>, token=<TRIAGE_TOKEN>, ...)` with `context.role="requester"`.
3. **Executor check:** Mint executor (Summarizer) one-shot token and call `policy_decision(agent_did=<SUMM_DID>, policy_id=<POLICY_ID>, token=<SUMM_TOKEN>, ...)` with `context.role="executor"`.
4. ALLOW+ALLOW → execute; otherwise return JSON-RPC error and do not echo activation header.

> The SDK calls and shapes used here follow `ironbook-sdk` **0.3.0** documentation for `register_agent`, `get_auth_token`, `upload_policy`, and `policy_decision`. ([PyPI][1])
