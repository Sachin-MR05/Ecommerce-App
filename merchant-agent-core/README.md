# Merchant Agent Core

Merchant Agent Core is the Python **agent intelligence / orchestration layer**
for the Agentic E-Commerce application. It understands a user's
natural-language commerce request, reasons about what to do next with an
LLM, and drives a think -> act -> observe loop until the request is
satisfied - but it never touches a merchant API, a database, or any
commerce business logic itself.

All actual commerce execution - product search, pricing, inventory, cart,
orders, payment verification - stays in the existing Java backend, behind
`AgentToolRegistry`. This service only *calls* that layer over HTTP.

## Why a separate Python service?

The Java backend already has a clean, tested execution surface
(`MerchantCommerceAdapter` -> `AgentTool` -> `AgentToolRegistry`). Agent
*reasoning* - prompting, planning, an LLM provider integration, an agent
loop - is a different concern with a different (and faster-moving)
ecosystem. Keeping it in a separate service means:

- The Java backend stays the single source of truth for commerce logic,
  validation, and data access - nothing here duplicates it.
- The LLM/agent implementation can evolve (or be swapped) without touching
  the commerce backend.
- Each service can be deployed, scaled, and tested independently.

## Responsibilities

**Python (this service):**
- Understanding the user's request and maintaining conversation/agent state
- Prompting the LLM and parsing its structured decision
- Deciding *which* tool to call next (planning)
- Calling the Java Tool Layer over HTTP (execution)
- Enforcing agent-level safety (max iterations, tool validation, honest
  failure handling)
- Returning a final structured response to the caller

**Java (existing backend):**
- Tool definitions, validation, and execution (`AgentTool`,
  `AbstractAgentTool`)
- Tool discovery/registry (`AgentToolRegistry`)
- All commerce logic via `MerchantCommerceAdapter` (products, cart, orders,
  payments)
- Integration with real merchant/commerce APIs (Razorpay, the database, etc.)

This service **never** duplicates `AgentTool`, `AbstractAgentTool`,
`AgentToolRegistry`, or `MerchantCommerceAdapter` in Python, and never calls
a merchant API directly.

## Architecture

```
User / Client
      |
      v
Python Merchant Agent Core
      |
      +--> LLM               (app/llm)
      |
      +--> Agent State        (app/agent/agent_state.py)
      |
      +--> Planning/Decision  (app/planning)
      |
      v
Java Tool Layer HTTP API      (GET /tools, POST /tools/{name}/execute)
      |
      v
AgentToolRegistry
      |
      v
AgentTool
      |
      v
MerchantCommerceAdapter
      |
      v
Merchant / Commerce APIs
```

## Folder structure

```
merchant-agent-core/
├── app/
│   ├── agent/           # AgentState, AgentLoop, MerchantAgent (composition root)
│   ├── llm/              # LLMClient abstraction + prompt manager
│   ├── planning/         # Decision model + Planner (state -> LLM -> Decision)
│   ├── tools/             # ToolDefinition/ToolCallResult models + ToolClient (HTTP to Java)
│   ├── execution/        # Executor (runs a validated tool Decision via ToolClient)
│   └── config/            # Settings (env-driven configuration)
├── api/
│   └── routes.py         # FastAPI routes: POST /agent/run, GET /health
├── tests/                 # Unit tests, no real LLM or merchant API calls
├── main.py                # FastAPI app entry point
├── requirements.txt
├── .env.example
└── .gitignore
```

## Environment variables

| Variable                 | Description                                              | Example                 |
|---------------------------|-----------------------------------------------------------|--------------------------|
| `LLM_PROVIDER`            | Which `LLMClient` implementation to use                   | `huggingface`           |
| `LLM_MODEL`               | Model name for the configured provider                    | `HuggingFaceH4/zephyr-7b-beta` |
| `LLM_API_KEY`             | API key for OpenAI/HuggingFace provider (HF optional)     |                          |
| `GEMINI_API_KEY`          | Optional Gemini key (used for `LLM_PROVIDER=gemini` or HF fallback) |                          |
| `GEMINI_BASE_URL`         | Gemini generateContent endpoint                            | `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent` |
| `GEMINI_FALLBACK_BASE_URL`| Optional backup Gemini endpoint when primary returns `503`  |                          |
| `LLM_MAX_OUTPUT_TOKENS`   | Output-token cap per model call (lower = cheaper/faster)  | `64`                    |
| `TOOL_SERVICE_URL`         | Base URL of the Java Tool Layer                            | `http://localhost:8080` |
| `AGENT_MAX_ITERATIONS`      | Max think/act loop iterations before failing safely        | `10`                    |
| `TOOL_TIMEOUT_SECONDS`      | HTTP timeout (seconds) for calls to the Java Tool Layer     | `30`                    |
| `LOG_LEVEL`                 | Python logging level                                        | `INFO`                  |

Copy `.env.example` to `.env` for local development and fill in your own
values. **Never commit `.env`.**

If `LLM_API_KEY` is left empty, the service falls back to a deterministic,
network-free `EchoLLMClient` so it still starts and runs locally/in CI -
it just can't actually reason about requests. Set a real key + provider for
real usage.

## How to run

```bash
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then fill in TOOL_SERVICE_URL / LLM_API_KEY

uvicorn main:app --reload
```

The service starts on `http://localhost:8000` by default.

## API examples

### `POST /agent/run`

Request:

```json
{
  "sessionId": "session-123",
  "message": "Find wireless headphones under ₹5000"
}
```

Response:

```json
{
  "sessionId": "session-123",
  "status": "COMPLETED",
  "response": "I found three matching headphones."
}
```

`status` is one of `COMPLETED`, `WAITING_FOR_USER`, or `FAILED`. No internal
implementation details (tool names, raw tool payloads, prompts) are exposed
in the response - only what the caller needs.

### `GET /health`

```json
{ "status": "ok" }
```

## Java Tool Layer dependency

This service depends on the Java backend exposing `AgentToolRegistry` over
HTTP. As of this writing, the Java project had `AgentTool` /
`AbstractAgentTool` / `AgentToolRegistry` as in-process classes only, with
**no HTTP endpoint** - so a minimal `AgentToolController` was added on the
Java side (not duplicated here) to expose exactly this contract:

**`GET /tools`**

```json
{
  "tools": [
    {
      "name": "search_products",
      "description": "Search the merchant's product catalog by keyword.",
      "inputSchema": { "type": "object", "properties": { "keyword": { "type": "string" } } },
      "outputSchema": { "...": "..." }
    }
  ]
}
```

**`POST /tools/{toolName}/execute`**

Request:

```json
{
  "userId": 123,
  "arguments": { "keyword": "wireless headphones" }
}
```

`userId` is optional and only required by user-scoped tools (cart/order/
payment). It must come from an authenticated session, never be invented by
the LLM.

Response (mirrors `com.ecommerce.tools.model.ToolResponse` exactly):

```json
{
  "success": true,
  "data": { "...": "..." },
  "errorCode": null,
  "errorMessage": null
}
```

`ToolClient` (`app/tools/tool_client.py`) is the *only* place in this
service that speaks this contract - see it for the exact request/response
handling, including how HTTP errors, timeouts, and malformed responses are
each turned into a distinct, typed exception.

## Example agent execution flow

```
User: "Find me Nike running shoes under ₹5000 and order the best one."

Iteration 1: LLM -> TOOL_CALL search_products         -> Java -> [products]
Iteration 2: LLM -> TOOL_CALL get_product              -> Java -> product details
Iteration 3: LLM -> TOOL_CALL check_inventory          -> Java -> available
Iteration 4: LLM -> TOOL_CALL get_price                -> Java -> current price
Iteration 5: LLM -> TOOL_CALL add_to_cart              -> Java -> cart updated
Iteration 6: LLM -> TOOL_CALL create_order             -> Java -> order created
Iteration 7: LLM -> FINAL_RESPONSE                     -> "Order placed - ..."
```

The loop (`app/agent/agent_loop.py`) never assumes this sequence - the LLM
decides the next action from the current state and tool results each
iteration. If any tool call fails (`success: false`), the agent observes
that failure as real information on the next iteration rather than
assuming success or fabricating a result.

## Testing

```bash
pytest
```

No test makes a real LLM or merchant API call:

- `test_agent_state.py` - state initialization, transitions, iteration
  count, completion, using no external dependencies.
- `test_planner.py` - a stub `LLMClient` returning scripted JSON, asserting
  tool-call / final-response / clarification / invalid-decision parsing.
- `test_tool_client.py` - `httpx.MockTransport`, asserting discovery,
  execution, HTTP failure, timeout, and malformed-response handling.
- `test_agent.py` - a stub `LLMClient` + stub `ToolClient`, exercising a
  full tool-call -> observation -> final-response run, plus max
  iterations, tool failure, unknown tool, and tool-service-unavailable
  cases.
