# Portfly — Demo Walkthrough

**Duration:** 5–10 minutes

## 1. Introduction (30–60 seconds)

Portfly is an AI-assisted real estate portfolio analyst. It helps users explore property holdings, understand portfolio metrics, evaluate hypothetical scenarios, and manage property information through a conversational interface.

## 2. Application Overview (1 minute)

Open the deployed application or the local frontend and show the main interface.

Demonstrate the available portfolio summaries, property information, occupancy status, and any distribution charts visible in the running application.

Explain that portfolio information is backed by the application's database.

## 3. Conversational Analysis (2 minutes)

Open the chat interface and demonstrate questions such as:

- "What is my total portfolio value?"
- "How much of my portfolio is retail?"
- "Which property generates the most rent?"
- "Show me my retail properties."

Explain that the agent uses portfolio tools and backend calculations to answer questions about stored property data.

**Important:** Demonstrate these interactions only when the application responds successfully. If deterministic fallback mode is active, disclose that fact and do not present the result as evidence of successful real-model reasoning.

## 4. Hypothetical Scenarios (1 minute)

Ask:

> What if I exclude the Bandra property?

Show the resulting portfolio comparison if this scenario is supported by the running application.

Explain that hypothetical analysis should calculate an alternative outcome without persisting changes to the underlying portfolio. Verify that the database remains unchanged before claiming that the operation was read-only.

## 5. Property Management and Validation (1 minute)

Demonstrate a supported property addition or update using valid inputs.

Explain how the application handles missing information, ambiguous property matches, invalid values, and unsuccessful operations.

Verify the final database state before claiming that a change was saved. If the request requires clarification, demonstrate that the application asks for it rather than modifying an uncertain property.

## 6. Business Desk (1 minute)

Open the Business Desk at `/desk`.

Show the available dashboard information, conversation details, agent or tool activity, and attention flags that are actually visible in the running application.

Explain that protected administrative endpoints require the configured `DESK_TOKEN`. Conversation access uses a separate conversation key.

Do not expose credentials during the demonstration. Describe only the information and controls verified in the current deployment.

## 7. Architecture and Engineering Decisions (1 minute)

Describe the main components:

- **Frontend:** React and Vite.
- **Backend:** FastAPI.
- **Agent:** LangGraph ReAct agent.
- **Model integration:** OpenRouter.
- **Portfolio operations:** Backend tools and deterministic analytics.
- **Persistence:** SQLAlchemy with SQLite for local development and PostgreSQL in Docker Compose.
- **Observability:** Agent-run records, tool-call traces, execution timings, and attention flags.

Refer to `ARCHITECTURE.md` for the system design and `DECISIONS.md` for the rationale behind the main implementation choices.

## 8. Testing, Evaluation, and Latency (1 minute)

### Automated tests

The latest previously reported full backend test run completed with **84 passed tests**, with 386 warnings. Rerun the test suite before the demonstration and report the actual current result.

### Real-model evaluation

OpenRouter free-model rate limits have affected real-model evaluation. Earlier runs reported incomplete evaluation, and later latency benchmarking encountered HTTP 429 quota errors.

Do not describe failed or unevaluated cases as passing. Report the latest evaluation results and distinguish provider errors from application or agent failures.

### Latency

The documented real-model benchmark recorded:

- 40 total requests across five repetitions.
- 25 successful requests and 15 errors.
- Overall successful-request p50 latency of approximately 9.9 seconds.
- Overall successful-request p95 latency of approximately 24.0 seconds.

The errors were associated with OpenRouter free-model quota exhaustion. These results are a preliminary local benchmark, not a guaranteed production latency figure.

Fallback-mode latency is a separate measurement and must not be presented as real-model latency.

## 9. Limitations and Closing

Summarize the application's capabilities, the automated testing performed, and the current limitations.

Mention that real-model quality and latency depend on provider availability and rate limits. Also disclose any outstanding authentication, persistence, or deployment checks relevant to the environment being demonstrated.

Before recording, verify the application URL, database connection, model configuration, authentication settings, and every feature you intend to demonstrate.

## Demo Checklist

- [ ] Application loads successfully.
- [ ] Database connection is working.
- [ ] Portfolio questions return expected results.
- [ ] Hypothetical analysis does not persist changes.
- [ ] Property updates are validated and persisted correctly.
- [ ] Business Desk authentication and controls work.
- [ ] Real-model versus fallback behavior is identified accurately.
- [ ] Current test and evaluation results are recorded.
- [ ] No API keys, conversation keys, or other credentials are exposed.
