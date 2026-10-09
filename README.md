# Portfly — AI Real Estate Portfolio Analyst

**Live Application:** https://portfly.onrender.com  
**Business Desk:** https://portfly.onrender.com/desk  
**API Documentation:** https://portfly.onrender.com/docs  
**GitHub Repository:** https://github.com/Bhaveshcpp/Portfly

Portfly is an AI-powered real estate portfolio analyst that helps property owners understand their holdings, analyze rental performance, compare properties, and explore hypothetical portfolio scenarios through a conversational interface.

The application combines a conversational agent with deterministic backend tools and persistent PostgreSQL storage to provide portfolio insights grounded in property data.

## Features

- **Portfolio analysis:** Calculate total portfolio value, annual rental income, gross rental yield, occupancy, and property-type exposure.
- **Property search:** Retrieve and filter properties using available portfolio information.
- **Conversational interface:** Ask natural-language questions about a real estate portfolio and its properties.
- **Property management:** Add or update properties through validated backend operations.
- **Hypothetical scenarios:** Explore portfolio changes without saving them to the database.
- **Conversation context:** Support follow-up questions using the properties discussed earlier.
- **Business desk:** View users, conversations, execution metrics, and items requiring attention.
- **Persistent storage:** Store portfolio and application data in PostgreSQL.
- **Fallback handling:** Handle model availability issues through the application's fallback behavior.

## Application Links

| Resource | URL |
|---|---|
| Main application | https://portfly.onrender.com |
| Business desk | https://portfly.onrender.com/desk |
| Health endpoint | https://portfly.onrender.com/api/health |
| Dashboard API | https://portfly.onrender.com/api/dashboard |
| API documentation | https://portfly.onrender.com/docs |
| Source code | https://github.com/Bhaveshcpp/Portfly |

## Architecture

```mermaid
flowchart TD
    A[User] --> B[React Frontend]
    B --> C[FastAPI Backend]
    C --> D[Conversational Agent]
    D --> E[OpenRouter Model]
    D --> F[Portfolio Tools]
    F --> G[(PostgreSQL)]
    C --> H[Business Desk]
    H --> C
```

### Request Flow

1. The user submits a portfolio question through the frontend.
2. The FastAPI backend processes the request.
3. When available, the configured language model interprets the request and selects appropriate tools.
4. Backend tools retrieve property records and calculate portfolio metrics.
5. The application returns a response based on the available data.
6. Conversation records and portfolio changes are stored through the database layer.

Portfolio arithmetic is delegated to deterministic backend functions rather than relying on the language model to calculate financial figures itself.

## Technology Stack

**Frontend**
- React
- Vite
- Tailwind CSS
- JavaScript

**Backend**
- Python
- FastAPI
- LangChain / LangGraph agent tooling
- REST APIs

**Database**
- PostgreSQL
- SQLAlchemy

**AI Integration**
- OpenRouter API
- Configurable language model
- Deterministic tool execution and fallback handling

**Deployment and Development**
- Docker
- Docker Compose
- Render
- Git and GitHub

## Local Setup

### Prerequisites

- Git
- Docker Desktop and Docker Compose
- Node.js and npm, if running the frontend separately
- Python, if running the backend separately
- An OpenRouter API key for real-model inference

### 1. Clone the repository

```bash
git clone https://github.com/Bhaveshcpp/Portfly.git
cd Portfly
```

### 2. Configure environment variables

Create the required environment configuration using the provided example file, if available. Configure the database connection and AI provider settings according to the application's configuration.

Typical settings include:

```env
DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE
OPENROUTER_API_KEY=your_api_key
OPENROUTER_MODEL=your_configured_model
OPENROUTER_BASE_URL=https://openrouter.ai/api/v1
MAX_HISTORY_MESSAGES=16
```

Replace the database placeholders with your own database credentials. Never commit `.env` files, API keys, passwords, or other secrets to GitHub.

Check the repository's configuration files for any additional required variables.

### 3. Run with Docker Compose

From the project root:

```bash
docker compose up --build -d
```

Inspect the running services:

```bash
docker compose ps
```

View backend logs:

```bash
docker compose logs -f backend
```

Stop the services:

```bash
docker compose down
```

To remove the database volume as well, use `docker compose down -v` only when you intentionally want to delete the local database data.

### 4. Open the application

- Frontend: http://localhost:8000
- Business desk: http://localhost:8000/desk
- Health check: http://localhost:8000/api/health
- API documentation: http://localhost:8000/docs

The Docker deployment serves the built frontend through the FastAPI application.

For separate frontend development, use the frontend's configured Vite development server and API proxy.

## API Endpoints

The application exposes REST endpoints for health checks, user data, portfolio information, dashboard metrics, and conversations.

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Check backend availability |
| `GET /api/users` | Retrieve available user records |
| `GET /api/dashboard` | Retrieve business dashboard metrics |
| `/api/conversations` | Conversation-related operations |
| `/docs` | Explore the API through Swagger UI |

Refer to the live API documentation for the exact methods, parameters, request schemas, and response formats supported by the deployed version.

## Data and Assumptions

- Portfolio insights are based on property records available to the application.
- Gross rental yield is calculated as annual rental income divided by current property value, multiplied by 100.
- Missing rental income is not treated as evidence of a property's market value or appreciation.
- Hypothetical scenarios should not modify saved portfolio records.
- Financial calculations are analytical estimates based on stored inputs, not professional investment, legal, or tax advice.
- User-scoped operations are intended to prevent access to another user's portfolio through the current user's context.

## Testing and Evaluation

### Automated Tests

The local backend test suite completed with:

- **53 tests passed**
- **0 test failures**

The test suite was run locally using pytest. Deprecation warnings were present for some existing dependencies and APIs.

### Deployment Checks

The following public endpoints were checked after deployment:

- Main application
- Business desk
- Health endpoint
- API documentation

The dashboard API returned structured data, including user, property, conversation, and execution metrics. Dashboard counts remained consistent after a page refresh.

A page refresh is only an initial consistency check; persistence across a server restart should be verified separately.

### AI Evaluation Status

Real-model evaluation was blocked during testing by an OpenRouter HTTP 429 error indicating that the configured free-model daily quota had been exhausted.

The application recorded fallback behavior for at least one failed model run. Therefore, successful real-model reasoning, tool selection, and model latency should not be considered fully validated by the fallback results.

## Known Limitations

- Real-model responses depend on the availability and rate limits of the configured OpenRouter model.
- Fallback responses may not support the same reasoning and conversational behavior as the language model.
- Real-model evaluation and successful model latency measurements remain to be verified when inference is available.
- Portfolio analysis depends on the completeness and accuracy of stored property information.
- Production persistence, access controls, and write operations should be tested against the deployed database before relying on the application for real financial decisions.
- Some installed dependencies or agent APIs may emit deprecation warnings and require future upgrades.

## Documentation

The repository includes project documentation covering architecture, design decisions, agent behavior, and the application walkthrough.

- `SOUL.md` — Agent role, behavior, tools, uncertainty, and boundaries.
- `ARCHITECTURE.md` — System architecture and data flow.
- `DECISIONS.md` — Implementation decisions and trade-offs.
- `docs/WALKTHROUGH.md` — Demonstration guide.

See the repository for the latest versions of these documents.

## Future Improvements

- Validate successful real-model inference and end-to-end conversational flows.
- Improve responses to property-specific comparison and hypothetical scenario questions.
- Add stronger integration tests for deployed database persistence and write operations.
- Upgrade deprecated agent APIs and address dependency warnings.
- Expand observability for model latency, tool execution, errors, and fallback frequency.

## License

No license is specified unless a license file is included in the repository. Contact the repository owner for reuse permissions.
