# Portfly — Demo Walkthrough

**Duration:** 5–10 minutes

## 1. Introduction (30–60 seconds)

Portfly is an AI-assisted real estate portfolio analyst. It helps users explore property holdings, understand portfolio metrics, evaluate hypothetical scenarios, and manage property information through a conversational interface.

## 2. Application overview (1 minute)

Open the frontend and show the main dashboard.

Demonstrate:
- Portfolio value and rental-income summaries.
- Property distribution by type and city.
- Property-level information and occupancy status.

Explain that the dashboard is backed by portfolio data stored in the application database.

## 3. Conversational analysis (2 minutes)

Open the chat interface and demonstrate questions such as:

- "What is my total portfolio value?"
- "How much of my portfolio is retail?"
- "Which property generates the most rent?"
- "Show me my retail properties."

Explain how the agent uses portfolio tools to retrieve data and calculate metrics instead of relying only on free-form model responses.

**Note:** Demonstrate these interactions only when the application responds successfully. Disclose if the deterministic fallback is active.

## 4. Hypothetical scenarios (1 minute)

Ask:

"What if I exclude the Bandra property?"

Show the resulting portfolio comparison. Explain that hypothetical analysis should calculate an alternative outcome without saving changes to the underlying portfolio.

## 5. Property management and validation (1 minute)

Demonstrate a supported property update or addition using valid inputs.

Explain how the application handles missing information, ambiguous requests, invalid values, and unsuccessful operations. Verify the final database state before claiming that a change was saved.

## 6. Business interface (1 minute)

Open the business or operations view at `/desk`.

Show the available user, conversation, and tool-activity information. Explain how the interface helps inspect application activity and identify issues.

Only describe information and controls that are actually visible in the running application.

## 7. Architecture and engineering decisions (1 minute)

Describe the main components:

- React and Vite frontend.
- FastAPI backend.
- LangGraph-based agent and portfolio tools.
- SQLAlchemy persistence with PostgreSQL for the configured deployment and SQLite for local testing.
- OpenRouter-compatible model integration.

Refer to `ARCHITECTURE.md` for the architecture overview and `DECISIONS.md` for implementation trade-offs.

## 8. Testing, latency, and limitations (1 minute)

Report the verified automated test result: **53 tests passed**.

Explain that the real-model evaluation currently has 17 cases marked not evaluated because OpenRouter returned a `429 free-models-per-day` rate-limit error. Do not describe those cases as passed.

The documented 30–80 ms latency refers to deterministic fallback mode. Real-model latency measurements remain pending.

Mention any other known limitations documented in the repository.

## 9. Closing

Summarize the application's main capabilities, the validation completed, and the remaining work needed for reliable real-model benchmarking and deployment verification.

Before recording, verify that the demo URL, database connection, and all demonstrated features work in the intended environment.
