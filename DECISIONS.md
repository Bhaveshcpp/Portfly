# Decision Log

## Core Decisions

1. **LangGraph + OpenRouter, single model.** Matches the assignment brief. No model router is introduced until measured latency and quality data demonstrate a need.

2. **Deterministic `analytics.py`.** The model does not perform portfolio arithmetic. Rental yield is calculated as annual rent divided by current estimated property value. Purchase price is not used because it is unavailable in the current data.

3. **Office grouping.** `Office` and `Commercial Office` map to the `Office` type group. Original property-type labels are retained for display.

4. **What-if tool is read-only.** `evaluate_hypothetical_scenario` evaluates a scenario using in-memory data. `update_property` is the persistence path for property edits.

5. **Ambiguous writes fail closed.** When multiple properties match a request, the application returns candidates for clarification instead of modifying an uncertain record. The business dashboard can display an attention flag.

6. **SQLite for local development and pytest; PostgreSQL via Docker Compose.** SQLite reduces setup friction on Windows, while Docker Compose provides a PostgreSQL configuration. Successful backend container deployment still needs to be verified.

7. **Deterministic fallback when the model is unavailable.** The application can handle supported requests through its fallback path when the API key is missing or model requests fail. The dashboard records whether fallback was used.

8. **No WhatsApp API integration.** The frontend uses a WhatsApp-inspired chat interface, including its header, green message bubbles, and composer. It does not connect to WhatsApp.

9. **No vector store.** The current dataset is structured relational data, so SQL queries and typed tools are more appropriate than embeddings or retrieval-augmented generation.

10. **Attention flags instead of a full human-queue product.** The application flags relevant conditions such as errors, empty model replies, and unclear property matches.

## Hardening Decisions — October 2026

### D-11: Validation lives in the domain layer, not the prompt

Range checks, unit-slip detection (for example, entering `12` instead of `12 Cr`), duplicate detection, tenanted-with-zero-rent conflicts, and unknown property IDs are enforced in `portfolio.py`.

A blocked write returns `needs_clarification` and may include `can_confirm`. The agent should request clarification or confirmation as appropriate, then retry with `confirmed=true` when supported. These domain-level checks apply independently of the model's instructions.

### D-12: Money is parsed server-side

The model passes monetary amounts in the form supplied by the user, such as `14 Cr`. The server-side `parse_inr` function converts the amount into the application's numeric representation. This reduces arithmetic and unit-conversion errors.

### D-13: City is a stored column

Parsing city information directly from locality strings caused problems for locations such as `Alibaug, Maharashtra` and localities supplied without a city.

City is stored separately and may be derived from an explicit argument, state-aware parsing, the user's existing properties in the locality, or the user's home city. Any inferred assumption should be communicated to the user. NCR users are asked for clarification because `Delhi NCR` does not identify a single city.

### D-14: Telemetry is measured, not estimated

Tool calls run through `trace()`, which records arguments, duration, and outcome. A LangChain callback measures model-call timing and token usage. Model time is tracked separately from tool execution time.

Real-model latency measurements must be distinguished from deterministic fallback measurements.

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

## Known Trade-offs

- Real-model quality and latency depend on the configured model and provider availability.
- Deterministic fallback responses do not demonstrate successful real-model reasoning.
- SQLite is convenient for local development; a deployed multi-user application should use an appropriately managed persistent database.
- Real-model evaluation and latency benchmarking must be completed when model access is available.
- The backend Docker image and public deployment must be verified before claiming production deployment readiness.
