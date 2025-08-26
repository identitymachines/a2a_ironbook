import os
import json
import asyncio
import httpx
from dotenv import load_dotenv

from ironbook_sdk import (
    IronBookClient,
    RegisterAgentOptions,
    GetAuthTokenOptions,
)

from ironbook_a2a import (
    IRONBOOK_EXTENSION_URI,
    IRONBOOK_AGENT_DID_FIELD,
    IRONBOOK_AUTH_TOKEN_FIELD,
    IRONBOOK_ACTION_FIELD,
    IRONBOOK_RESOURCE_FIELD,
    IRONBOOK_CONTEXT_FIELD
)

load_dotenv()

# Go to https://ironbook.identitymachines.com to create a free account; provision your API Key in Your Organization Name (Top right) => Settings
# The Iron Book Portal also allows you to view agents, their audit logs, create policies, and more.
IRONBOOK_API_KEY = os.getenv("IRONBOOK_API_KEY", "REPLACE_ME")
IRONBOOK_AUDIENCE = os.getenv("IRONBOOK_AUDIENCE", "https://api.identitymachines.com")

TRIAGE_AGENT_NAME = os.getenv("TRIAGE_AGENT_NAME", "a2atriage")
TRIAGE_CAPABILITIES = ["delegate"]  # Does not have the 'openai_infer' capability

SUMMARIZER_URL = os.getenv("SUMMARIZER_URL", "http://localhost:8001/agents/summarizer")

def build_metadata(triage_did: str, token: str):
    return {
        IRONBOOK_ACTION_FIELD: "infer",
        IRONBOOK_RESOURCE_FIELD: "llm://responses",
        IRONBOOK_CONTEXT_FIELD: {
            "purpose": "assistant",
            "data_classification": "internal",
            "region": "US",
            "model": "gemini-1.5-pro",
            "estimated_cost_cents": 15,
            "daily_budget_remaining_cents": 500,
            "pii_detected": False,
            "request_id": "rq_demo_001",
            "expires_at": "2025-12-31T00:00:00Z"
        },
        IRONBOOK_AUTH_TOKEN_FIELD: token,
        IRONBOOK_AGENT_DID_FIELD: triage_did
    }

async def main():
    client = IronBookClient(api_key=IRONBOOK_API_KEY)

    # Register the Triage agent (this is the agent that will be used to delegate the task to the summarizer agent
    # Note that trying to re-register an agent with the same name will return an error
    try:
        triage = await client.register_agent(RegisterAgentOptions(
            agent_name=TRIAGE_AGENT_NAME,
            capabilities=TRIAGE_CAPABILITIES
        ))
    except Exception:
        # Fall back to getting an existing agent with that name if registration fails
        triage = await client.get_agent(f"did:web:agents.identitymachines.com:{TRIAGE_AGENT_NAME}")

    token_data = await client.get_auth_token(GetAuthTokenOptions(
        agent_did=triage.did,
        vc=triage.vc,
        audience=IRONBOOK_AUDIENCE
    ))
    access_token = token_data.get("access_token")
    assert access_token, "Failed to mint one-shot Iron Book token for the Triage agent"

    body = {
        "jsonrpc": "2.0",
        "id": "1",
        "method": "task/execute",
        "params": {
            "message": { "task": "summarize", "inputRef": "doc://case-123" }, # This is the input to the summarizer agent; NOT an actual document to summarize
            "metadata": build_metadata(triage.did, access_token)
        }
    }
    headers = { "Content-Type": "application/json", "X-A2A-Extensions": IRONBOOK_EXTENSION_URI } # This is the header that tells the summarizer agent that the requester agent is using the Iron Book extension

    async with httpx.AsyncClient(timeout=30.0) as http:
        r = await http.post(SUMMARIZER_URL, headers=headers, content=json.dumps(body))
        print("Status:", r.status_code, "Activated:", r.headers.get("X-A2A-Extensions"))
        try:
            print(json.dumps(r.json(), indent=2))
        except Exception:
            print(r.text)

if __name__ == "__main__":
    asyncio.run(main())
