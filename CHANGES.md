# Changes and Implementation Notes

## 1. Agent and Portfolio Improvements

1. **Duplicate user-message handling:** Updated conversation history handling so the current user turn is not sent to the model twice.
2. **Tool telemetry:** Replaced placeholder telemetry with actual tool arguments, per-call duration, execution outcomes, model-call timing, LLM call counts, and token counts.
3. **City resolution:** Added a stored `city` column and city-resolution logic to improve handling of locations such as `Alibaug, Maharashtra` and `Indiranagar`.
4. **Follow-up context:** Added recently discussed property IDs and active hypothetical scenarios to conversation context.
5. **Attention flags:** Added structured flag handling for errors, handoffs, and clarification states, along with a conversation-resolution endpoint.
6. **Write validation:** Added domain-level validation, monetary parsing through `parse_inr`, and confirmation handling for supported write operations.
7. **Error handling:** Improved message persistence, rollback behavior, read-only fallback behavior, step-limit detection, and tool-exception handling.
8. **Hypothetical scenarios:** Added support for multiple re-valuations, exclusions by property ID, location, or type, hypothetical additions, and explicit portfolio deltas. Unknown property IDs are rejected.
9. **Fallback organization:** Moved fallback logic into `agent/fallback.py` and aligned supported fallback operations with the application's validation and tracing mechanisms.

## 2. Persistence and User Interface

- Added an additive database migration through `ensure_columns` to support existing database files.
- Improved conversation persistence so chat history can survive a page refresh.
- Added a New Chat control.
- Extended the Business Desk with operational metrics, latency percentiles, model-versus-tool timing, token information, user information, attention filtering, tool arguments, and a Resolve control.

## 3. Authentication and Security

- Added Bearer-token protection for designated Business Desk endpoints using `DESK_TOKEN`.
- Added per-conversation access keys, with SHA-256 hashes stored by the backend.
- Added conversation-key validation for existing conversation operations and message-history retrieval.
- Added generic rejection behavior for inaccessible conversations and `Cache-Control: no-store` for chat-history responses.

The user and property listing endpoints require separate review because not every listing route currently uses the same authentication dependency.

## 4. Automated Testing

The project has expanded its automated test coverage for domain validation, agent execution, and database migration behavior.

The latest previously reported full backend test run completed with **84 passed tests**, with 386 warnings. Rerun the suite before reporting a current result.

Earlier tooling notes recorded 53 unit tests and 17/17 fallback-mode evaluation scenarios. Those results belong to earlier stages and should not be confused with successful real-model evaluation.

## 5. Evaluation and Latency Tooling

The backend includes the following scripts under `backend/scripts/`:

### `eval_agent.py`

Runs 17 evaluation scenarios covering portfolio totals, exposure, isolation, prompt injection, property additions and updates, missing information, unit errors, hypothetical scenarios, multi-turn context, and other supported behaviors.

The script supports model selection, scenario filtering, verbose output, and configurable connection settings. Evaluation results must distinguish passing scenarios from provider errors and unevaluated cases.

### `measure_latency.py`

Runs an eight-turn workload over configurable repetitions and reports total latency percentiles, model/tool/other timing, model-call counts, and token usage. Optional input and output prices can be supplied for cost estimates.

### `harness.py`

Provides shared execution infrastructure for evaluation and benchmarking against the supported in-process or remote application interfaces.

## 6. Recorded Real-Model Latency Baseline

A preliminary local benchmark using a real OpenRouter model recorded:

- **Total requests:** 40
- **Successful requests:** 25
- **Errors:** 15
- **Successful-request p50 latency:** approximately 9.9 seconds
- **Successful-request p95 latency:** approximately 24.0 seconds

The errors were associated with OpenRouter free-model quota exhaustion. These figures are preliminary measurements, not a guaranteed production latency estimate.

See `docs/LATENCY.md` for the benchmark details and interpretation.

## 7. Deployment and Documentation

- Updated the backend Docker image to include `SOUL.md`.
- Added a regression test verifying that the system prompt loads the soul file.
- Updated the project README with setup instructions, architecture, configuration, security behavior, testing, and known limitations.
- Updated `ARCHITECTURE.md`, `DECISIONS.md`, and `docs/WALKTHROUGH.md` to document the system design, implementation choices, security boundaries, demonstration flow, and measured limitations.

The live application and API documentation are available at:

- https://portfly.onrender.com
- https://portfly.onrender.com/desk
- https://portfly.onrender.com/docs

A live URL alone does not establish that every endpoint, authentication path, database persistence behavior, or model-backed interaction has been independently verified.

## 8. Remaining Verification

Before treating the project as production-ready:

- Rerun the complete automated test suite and record the current result.
- Repeat real-model evaluation when provider access is available.
- Repeat latency benchmarking after rate limits reset.
- Verify authentication boundaries for all user, property, conversation, and administrative endpoints.
- Verify database persistence and migration behavior in the intended deployment environment.
- Confirm that the README, architecture, decisions, walkthrough, and latency report agree with the current implementation.
