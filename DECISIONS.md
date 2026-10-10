# Decision Log

## Core Decisions

### D-1: LangGraph + OpenRouter, single model

The application uses a LangGraph ReAct agent with a configurable OpenRouter model. No model router is introduced until measured latency and quality data demonstrate a need.

### D-2: Deterministic portfolio analytics

Portfolio calculations are implemented in `analytics.py` rather than delegated to the language model. Rental yield is calculated as annual rent divided by current estimated property value. Purchase price is not used because it is unavailable in the current data.

### D-3: Office property grouping

`Office` and `Commercial Office` map to the `Office` type group. Original property-type labels are retained for display.

### D-4: What-if operations are read-only

`evaluate_hypothetical_scenario` evaluates a scenario using in-memory data. `update_property` is the persistence path for property edits. Hypothetical changes must not be treated as committed property updates.

### D-5: Ambiguous writes fail closed

When multiple properties match a write request, the application returns candidates for clarification rather than modifying an uncertain record. Relevant outcomes may create an attention flag for the Business Desk.

### D-6: SQLite locally, PostgreSQL in Docker Compose

SQLite reduces setup friction during local development and testing on Windows. Docker Compose provides the PostgreSQL configuration. Deployment and database persistence must be verified in the target environment before making production-readiness claims.

### D-7: Deterministic fallback when the model is unavailable

The application can handle supported requests through its fallback path when the API key is missing or model requests fail. The dashboard records whether fallback was used. Fallback results are distinct from successful real-model responses.

### D-8: WhatsApp-inspired interface without WhatsApp integration

The frontend uses a WhatsApp-inspired chat interface, including its header, green message bubbles, and composer. It does not connect to the WhatsApp API.

### D-9: SQL instead of a vector store

The current dataset contains structured relational data. SQL queries and typed tools are more appropriate than embeddings or retrieval-augmented generation for the application's current requirements.

### D-10: Attention flags instead of a full human-queue product

The application flags relevant conditions such as errors, empty model replies, and unclear property matches. The Business Desk provides visibility into these conditions without implementing a full case-management workflow.

## Hardening Decisions — October 2026

### D-11: Validation belongs in the domain layer

Range checks, unit-slip detection (for example, entering `12` instead of `12 Cr`), duplicate detection, tenanted-with-zero-rent conflicts, and unknown property IDs are enforced in `portfolio.py`.

A blocked write returns `needs_clarification` and may include `can_confirm`. The agent should request clarification or confirmation as appropriate, then retry with `confirmed=true` when supported. Domain-level checks must apply independently of the model's instructions.

### D-12: Monetary amounts are parsed server-side

The model passes monetary amounts in the form supplied by the user, such as `14 Cr`. The server-side `parse_inr` function converts the amount into the application's numeric representation. This reduces arithmetic and unit-conversion errors.

### D-13: City is stored separately

Parsing city information directly from locality strings caused problems for locations such as `Alibaug, Maharashtra` and localities supplied without a city.

City is stored separately and may be derived from an explicit argument, state-aware parsing, the user's existing properties in the locality, or the user's home city. Inferred assumptions should be communicated to the user. NCR users are asked for clarification because `Delhi NCR` does not identify a single city.

### D-14: Telemetry is measured, not estimated

Tool calls run through `trace()`, which records arguments, duration, and outcome. A LangChain callback measures model-call timing and token usage. Model time is tracked separately from tool execution time.

Real-model latency measurements must be distinguished from deterministic fallback measurements. Benchmark results should include the model configuration, sample size, errors, and provider limitations.

### D-15: Attention flags come from structured outcomes

Attention flags are derived from structured application outcomes rather than relying solely on model-generated text.

- Tool failures and agent errors create sticky flags.
- Human handoff requests create sticky flags.
- Pending clarification flags clear automatically when the clarification is resolved.
- Sticky flags persist until a human resolves them.

### D-16: What-if state is stored per conversation

The latest hypothetical scenario is stored with the conversation so a follow-up such as "How would that change my portfolio?" can refer to the previous scenario. A real property write invalidates the previous scenario state because its assumptions may no longer be current.

### D-17: Fallback after model failure is read-only

When a model request fails, the fallback can answer supported questions using deterministic tools but must not perform writes. This reduces the risk of applying a change twice when the model fails after a write-related operation.

## Security Decisions

### D-18: Business Desk access uses a separate Bearer token

Protected Business Desk endpoints validate the `Authorization: Bearer <DESK_TOKEN>` header. If `DESK_TOKEN` is not configured, protected endpoints fail closed rather than becoming accessible without authentication.

Missing or invalid credentials are rejected. The desk token is separate from individual conversation access keys.

### D-19: Each conversation has its own access key

A new conversation receives a cryptographically random access key. The backend stores its SHA-256 hash and returns the plaintext key only when the conversation is created.

Clients send the key using the `X-Conversation-Key` header when accessing an existing conversation or retrieving its history. Authorization is checked on the backend, and inaccessible conversations receive generic rejection responses.

Conversation keys and the Business Desk token have separate authorization scopes. Possessing one does not grant the other.

### D-20: Portfolio access must be scoped in backend queries

Portfolio tools are intended to constrain property reads and writes to the current user's context. User scoping is enforced in backend tool logic rather than relying only on model instructions.

Conversation authorization and property-level data isolation are separate controls and must be tested independently.

The user and property listing endpoints must also be reviewed for appropriate authentication before sensitive production data is exposed.

## Known Trade-offs and Remaining Work

- Real-model quality and latency depend on the configured model and provider availability.
- Deterministic fallback responses do not demonstrate successful real-model reasoning.
- OpenRouter free-model quotas and rate limits can affect evaluation and latency measurements.
- SQLite is convenient for local development; deployed multi-user applications need an appropriately managed persistent database.
- Real-model evaluation and latency benchmarking should be repeated when model access is available.
- The backend Docker image, database persistence, authentication boundaries, and public deployment must be verified before claiming production readiness.
- Public user and property listing routes need appropriate access controls before sensitive production data is used.
