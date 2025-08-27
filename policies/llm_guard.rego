package policies.llm_guard

default allow := false

# Use https://play.openpolicyagent.org to validate syntax, or create all kinds of crazy, much more granular policies

# Scope: action delegation for this resource
can_delegate if {
  input.action == "delegate"
  input.resource == "llm://responses"
}

# Scope: LLM inference for this resource
can_infer if {
  input.action == "openai_infer"
  input.resource == "llm://responses"
}

allowed_models := {"gemini-1.5-pro", "gpt-4o-mini", "o4-mini"}
allowed_classifications := {"public", "internal", "deidentified"}
allowed_regions := {"US", "EU"}

# Requester (Triage): must have 'delegate'; trust >= 45
allow if {
  can_delegate
  input.context.role == "requester"
  input.capabilities[_] == "delegate"
  input.trust >= 45
}

# Executor (Summarizer): must have 'openai_infer' and satisfy guardrails
allow if {
  can_infer
  input.context.role == "executor"
  input.capabilities[_] == "openai_infer"
  input.trust >= 55
  allowed_models[input.context.model]
  allowed_classifications[input.context.data_classification]
  allowed_regions[input.context.region]
  not input.context.pii_detected
  to_number(input.context.estimated_cost_cents) <= to_number(input.context.daily_budget_remaining_cents)
}
