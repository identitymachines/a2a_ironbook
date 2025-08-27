# A2A x Iron Book — Least-Privilege Agent Task Handoff (Extension Demo)

> Iron Book SDK target: `ironbook-sdk >= 0.3.1`.  
> Docs (Iron Book SDK): https://pypi.org/project/ironbook-sdk — Quick Start, methods, calls, data types.  
> Iron Book comprehensive solution overview: https://docs.identitymachines.com.  
> Docs (Extension): Iron Book A2A Extension page https://pypi.org/project/ironbook-a2a-extension.  
> This demo is governance-focused; no real LLM call is made (document for the Summarizer agent action is simulated).

This repository demonstrates a **profile/data A2A extension** (`x-ironbook`) that adds **zero-trust, policy-gated handoffs** between agents:

- **Least-privilege delegation:** a **Triage** agent (requester) can only **delegate**; a **Summarizer** (executor) agent is the only one allowed to **infer**. Capabilities are enforced by policy, not hope. 
GitHub.
- **Two-decision guardrail:** we separately verify that the requester is **allowed to ask** and the executor is **allowed to act**, solving the classic confused-deputy problem. 
GitHub.
- **Enterprise guardrails in Rego:** model allow-list, region & data-class, PII=no, budget caps, etc.; all evaluated server-side with an injected behavioral 0–100 trust score.

If you operate AI agents, this pattern is a fast path to governed, auditable agent-to-agent workflows. PRs & feedback welcome!

### Demo Rego Policy (Rego v1) Included
`policies/llm_guard.rego` enforces:
- Requester must have the **`delegate`** capability and sufficient trust.
- Executor must have **`openai_infer`**, allowed **model/region/data_classification**, **no PII**, and **budget** within limits.

### What Happens on Run
1. **Triage agent** (requester) registers in Iron Book's secure agent registry with `delegate` capability only
2. **Summarizer agent** (executor) registers in Iron Book's secure agent registry with `openai_infer` capability
3. Triage sends an inference (mocked) action delegation request to Summarizer with the Iron Book extension activated using a secure one-shot Iron Book token
4. **Two policy decisions** are made:
   - Requester check: Triage has a valid one-shot token, `delegate` + sufficient trust (all Iron Book agents have a 0-100 trust score)
   - Executor check: Summarizer has has a valid one-shot token, `openai_infer` + meets guardrails (defined in the provided policy)
5. If all checks pass, the handoff succeeds (demo result returned)

### Two-Decision Pattern
1) **Requester decision:** Summarizer calls Iron Book's `policy_decision()` with **Triage DID** + **Triage one-shot token** and `context.role="requester"`.  
2) **Executor decision:** Summarizer calls Iron Book's `policy_decision()` with **Summarizer DID** + **Summarizer one-shot token** and `context.role="executor"`.

### Notes On A2A Compliance
- **Declaration:** Summarizer advertises the extension in its AgentCard (`/agent-card`) under `capabilities.extensions[]` with a **versioned URI**.
- **Activation:** Triage sets `X-A2A-Extensions: <URI>` on the request. Summarizer echoes the header on success.
- **Data placement:** All extension data are placed under `params.metadata["<URI>/…"]` (namespaced keys). No core schema changes.

### Troubleshooting
- **Module errors**: Use `python -m agents.summarizer` instead of `python agents/summarizer.py`, and `python -m agents.requester` instead of `python agents/requester.py`
- **API key issues**: Get your Iron Book API key at https://ironbook.identitymachines.com
- **Agent Not Found**: Your agent's DID is be stripped of all non-alphanumeric characters (if you name your Iron Book agent "a2a-summarizer", your DID will be 'did:web:agents.identitymachines.com:a2asummarizer')
- **Port conflicts**: Change `SUMMARIZER_PORT` in `.env`
- **Terminals**: Remember, you need to run Summarizer (server-side; run this first) and Triage in separate terminal windows

### Customization & Improvements
- **Real LLM Inference**: Add real LLM inference and agents (e.g., using ADK)
- **Customize Policy**: Add more Trust Score gates, prompt secrets detection, etc.
- **Expand Use Cases**: Don't limit yourself to LLM calls - use MCP to gatekeep tool access, and more
