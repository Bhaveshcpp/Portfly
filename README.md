\# Portfly



Two-way AI real-estate portfolio analyst. Users chat in a WhatsApp-style screen; a business desk watches threads, tools, flags, and latency. There is no WhatsApp API.



\## Stack



React (Vite) · FastAPI · SQLAlchemy · SQLite or PostgreSQL · LangGraph · OpenRouter



\## Quick start (Windows)



From the project root, open PowerShell and run:



```powershell

cd backend

.\\.venv\\Scripts\\Activate.ps1

pip install -r requirements.txt

$env:DATABASE\_URL = "postgresql+psycopg://portfly:portfly@localhost:5432/portfly"

uvicorn app.main:app --reload --port 8000

```



If PostgreSQL is not running, start it from a separate terminal at the project root:



```powershell

docker compose up -d db

```



In another terminal, start the frontend:



```powershell

cd frontend

npm install

npm run dev

```



Open \[http://localhost:5173](http://localhost:5173) for chat and \[http://localhost:5173/desk](http://localhost:5173/desk) for the business view. API documentation is available at \[http://localhost:8000/docs](http://localhost:8000/docs).



\## Configuration



Create a `.env` file from `.env.example` in the project root if needed. Set `OPENROUTER\_API\_KEY` to enable live LLM requests.\&#x20;



Without a usable OpenRouter response, chat may use the deterministic fallback. A configured API key does not guarantee that the provider or model is available.



\## PostgreSQL



The database runs in Docker, exposed on port 5432. The local FastAPI backend connects using:



```powershell

$env:DATABASE\_URL = "postgresql+psycopg://portfly:portfly@localhost:5432/portfly"

```



\## Tests



From the project root:



```powershell

cd backend

.\\.venv\\Scripts\\Activate.ps1

pytest -q

```



\## Docs



\- `SOUL.md` — agent behaviour

\- `ARCHITECTURE.md` — end-to-end diagram

\- `DECISIONS.md` — trade-offs

\- `docs/LATENCY.md` — timing notes



\## External dependencies



OpenRouter (optional for LLM). No private property APIs.



\## Known limits



Purchase prices and dates are absent in the seed set. Portfly will not invent appreciation or historical returns. Property type labels are normalized only for exposure math.



