# A2A x Iron Book — Least-Privilege LLM Handoff (Extension Demo)

This repository demonstrates a **profile/data A2A extension** (`x-ironbook`) that adds **zero-trust, policy-gated handoffs** between agents:

- **Triage** agent (requester) has **no LLM inference capability**; it has the capability to **`delegate`** only.
- **Summarizer** agent (executor) has **`openai_infer`** capability and performs the LLM action *only if* policy allows.

### Notes On A2A Compliance
- **Declaration:** Summarizer advertises the extension in its AgentCard (`/agent-card`) under `capabilities.extensions[]` with a **versioned URI**.
- **Activation:** Triage sets `X-A2A-Extensions: <URI>` on the request. Summarizer echoes the header on success.
- **Data placement:** All extension data are placed under `params.metadata["<URI>/…"]` (namespaced keys). No core schema changes.

### Two-Decision Pattern
1) **Requester decision:** Summarizer calls `policy_decision()` with **Triage DID** + **Triage one-shot token** and `context.role="requester"`.  
2) **Executor decision:** Summarizer calls `policy_decision()` with **Summarizer DID** + **Summarizer one-shot token** and `context.role="executor"`.

Both must **ALLOW** to proceed.

### Rego Policy (Rego v1)
`policies/llm_guard.rego` enforces:
- Requester must have **`delegate`** and sufficient trust.
- Executor must have **`openai_infer`**, allowed **model/region/data_classification**, **no PII**, and **budget** within limits.

> SDK target: `ironbook-sdk >= 0.3.0`. Refer to the package's Quick Start and methods (register agent, get auth token, upload policy, policy decision).  
> Docs (SDK): Iron Book Python SDK page (https://pypi.org/project/ironbook-sdk) — methods, calls, data types.
> Docs (Extension): Iron Book A2A Extension page (https://pypi.org/project/ironbook-a2a-extension).
> This demo is governance-focused; no real LLM call is made (document for the Summarizer agent action is simulated).
