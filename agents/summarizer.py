import os
import json
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, HTTPException
from pydantic import BaseModel
import uvicorn
from dotenv import load_dotenv

from ironbook_sdk import (
    IronBookClient,
    RegisterAgentOptions,
    UploadPolicyOptions,
    GetAuthTokenOptions,
    PolicyInput,
)

from ironbook_a2a import (
    IronBookExtension,
    IRONBOOK_EXTENSION_URI,
    IRONBOOK_AGENT_DID_FIELD,
    IRONBOOK_AUTH_TOKEN_FIELD,
    IRONBOOK_CONTEXT_FIELD,
)

load_dotenv()

# Go to https://ironbook.identitymachines.com to create a free account; provision your API Key in Your Organization Name (Top right) => Settings
# The Iron Book Portal also allows you to view agents, their audit logs, create policies, and more.
IRONBOOK_API_KEY = os.getenv("IRONBOOK_API_KEY", "REPLACE_ME")
IRONBOOK_AUDIENCE = os.getenv("IRONBOOK_AUDIENCE", "https://api.identitymachines.com")

SUMM_AGENT_NAME = os.getenv("SUMM_AGENT_NAME", "a2asummarizer")
SUMM_CAPABILITIES = ["openai_infer"]  # Has the 'openai_infer' capability

SUMMARIZER_HOST = os.getenv("SUMMARIZER_HOST", "0.0.0.0")
SUMMARIZER_PORT = int(os.getenv("SUMMARIZER_PORT", "8001"))

POLICY_PATH = os.path.join(os.path.dirname(__file__), "..", "policies", "llm_guard.rego")

AGENT_CARD = {
    "name": SUMM_AGENT_NAME,
    "capabilities": {
        "extensions": [
            {
                "uri": IRONBOOK_EXTENSION_URI,
                "description": "Policy-gated LLM calls (one-shot token + decision)",
                "required": False,
                "params": { "policy": "llm_guard_v1", "audience": IRONBOOK_AUDIENCE }
            }
        ]
    }
}

BOOT: Dict[str, Any] = {}

async def bootstrap() -> None:
    print("\n📓 Initializing server-side Iron Book client...\n")
    client = IronBookClient(api_key=IRONBOOK_API_KEY)

    # Register the Summarizer agent (this is the agent that will performing the LLM inference action, delegated by the Triage agent)
    # Note that trying to re-register an agent with the same name will return an error
    try:
        agent = await client.register_agent(RegisterAgentOptions(
            agent_name=SUMM_AGENT_NAME,
            capabilities=SUMM_CAPABILITIES
        ))
        print(f"\n🤖✅ Summarizer agent registered with DID: {agent.did}\n")
    except Exception:
        # Fall back to getting an existing agent with that name if registration fails
        agent = await client.get_agent(f"did:web:agents.identitymachines.com:{SUMM_AGENT_NAME}")
        print(f"\n🤖✅ Summarizer agent found with DID: {agent.did}\n")

    with open(POLICY_PATH, "r", encoding="utf-8") as f:
        policy_content = f.read()

    # Reuploading the policy is OK, as this will simply override the previous version
    policy = await client.upload_policy(UploadPolicyOptions(
        config_type="opa",
        policy_content=policy_content,
        metadata={"name": "llm_guard_v1", "version": "1.0"}
    ))
    print(f"\n📄✅ Policy uploaded/updated with ID: {policy["policyId"]}\n")

    BOOT["client"] = client
    BOOT["summ_agent"] = agent
    BOOT["policy"] = policy

class A2AParams(BaseModel):
    message: Dict[str, Any]
    metadata: Dict[str, Any] = {}

class A2ARequest(BaseModel):
    jsonrpc: str
    id: str
    method: str
    params: A2AParams

print(f"\n✨ Building A2A API infrastructure...\n")

app = FastAPI()

@app.on_event("startup")
async def _startup():
    await bootstrap()

@app.get("/agent-card")
async def agent_card():
    return AGENT_CARD

@app.post("/agents/summarizer")
async def summarizer_entry(req: Request):
    # 1) Enforce A2A activation header
    requested_exts = req.headers.get("X-A2A-Extensions", "")
    if IRONBOOK_EXTENSION_URI not in [s.strip() for s in requested_exts.split(",") if s.strip()]:
        raise HTTPException(status_code=412, detail="Extension not activated")

    # 2) Parse A2A JSON-RPC
    body = await req.json()
    try:
        a2a = A2ARequest(**body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid A2A request: {e}")

    # 3) Extract namespaced metadata
    md = a2a.params.metadata

    context = md.get(IRONBOOK_CONTEXT_FIELD, {})
    triage_token = md.get(IRONBOOK_AUTH_TOKEN_FIELD)
    triage_did = md.get(IRONBOOK_AGENT_DID_FIELD)

    if not all([context, triage_token, triage_did]):
        raise HTTPException(status_code=400, detail="\n❌ Missing required Iron Book A2A extension metadata\n")

    print(f"\n🪙📝✅ Parsed A2A Triage agent request metadata for Summarizer\n")

    client: IronBookClient = BOOT["client"]
    policy_id = BOOT["policy"]["policyId"]

    # 4) Decision #1 — Requester (Triage agent) allowed to delegate? (role=requester)
    ctx_requester = dict(context)
    ctx_requester["role"] = "requester"

    triage_decision = await client.policy_decision(PolicyInput(
        agent_did=triage_did,
        policy_id=policy_id,
        token=triage_token,
        context=ctx_requester
    ))
    if not triage_decision.allow:
        return _a2a_error(a2a.id, "\n🪙❌Extension activation failed",
                          {"reason": triage_decision.reason | "Requester not allowed to perform this action"})

    print(f"\n🪙✅ Policy check passed with token: Requester agent allowed to delegate this action.\n")
    # 5) Decision #2 — Executor (Summarizer agent) allowed to execute? (role=executor)
    summ = BOOT["summ_agent"]
    token_data = await client.get_auth_token(GetAuthTokenOptions(
        agent_did=summ.did,
        vc=summ.vc,
        action="openai_infer",
        resource="llm://responses",
        audience=IRONBOOK_AUDIENCE
    ))
    access_token = token_data.get("access_token")
    if not access_token:
        return _a2a_error(a2a.id, "\n🪙❌ Extension activation failed", {"reason": "Failed to mint one-shot Iron Book token for the Executor/Summarizer agent"})

    print(f"\n🪙✅ One-shot Iron Book token minted for the Summarizer agent\n")
    ctx_executor = dict(context)
    ctx_executor["role"] = "executor"
    ctx_executor["requester_agent_did"] = triage_did # Audit log will record full context, including the Triage agent's DID for reference

    summ_decision = await client.policy_decision(PolicyInput(
        agent_did=summ.did,
        policy_id=policy_id,
        token=access_token,
        context=ctx_executor
    ))
    if not summ_decision.allow:
        return _a2a_error(a2a.id, "\n📄❌ Denied by policy",
                          {"reason": summ_decision.reason | "Summarizer not allowed to perform this action"})

    print(f"\n📄✅ Policy check passed with token: Summarizer agent allowed to perform this action.\n")
    print(f"\n💬✅ Proceeding with LLM inference (mocked in this demo)...\n")
    
    # 6) Demo result (no real LLM call)
    task = a2a.params.message.get("task", "summarize")
    input_ref = a2a.params.message.get("inputRef", "doc://unknown") # This is the sample input to the summarizer agent; NOT an actual document to summarize
    result = f"[Demo] {task} task succeeded OK for {input_ref}, ran by {summ.name} using model={context.get('model')}"

    res_obj = _a2a_result(a2a.id, {"result": result})
    return Response(
        content=json.dumps(res_obj),
        media_type="application/json",
        headers={"X-A2A-Extensions": IRONBOOK_EXTENSION_URI}
    )

def _a2a_result(id_: str, result_obj: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "result": result_obj}

def _a2a_error(id_: str, message: str, data: Dict[str, Any]) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": id_, "error": {"code": -32602, "message": message, "data": data}}

if __name__ == "__main__":
    uvicorn.run("agents.summarizer:app",
                host=SUMMARIZER_HOST,
                port=SUMMARIZER_PORT,
                reload=bool(os.getenv("UVICORN_RELOAD")))
