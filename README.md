# Company Lens — AI-Powered Client Acquisition Intelligence Platform

A full-stack corporate-banking intelligence platform that helps Relationship Managers research, score, and compare potential corporate clients through automated AI research pipelines, relationship graph visualization, and portfolio analysis.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (async), Python 3.11+ |
| Frontend | Next.js 14+ (App Router), TypeScript strict |
| Database | PostgreSQL 16 + pgvector |
| Cache/Queue | Redis 7, ARQ (background jobs) |
| AI | OpenAI GPT-4o-mini, text-embedding-ada-002, Tavily API |
| UI | Tailwind CSS, DaisyUI, Recharts, React Flow |

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Docker & Docker Compose (for PostgreSQL and Redis)
- OpenAI API key
- Tavily API key

---

## Project Structure

```
company-checker/
├── backend/                  # FastAPI backend (API-only, no HTML)
│   ├── app/
│   │   ├── main.py          # FastAPI app factory
│   │   ├── config.py        # pydantic-settings (env vars)
│   │   ├── database.py      # Async SQLAlchemy engine
│   │   ├── dependencies.py  # Shared FastAPI dependencies
│   │   ├── auth/            # JWT auth, registration, login
│   │   ├── companies/       # Company search, profiles
│   │   ├── research/        # AI research pipeline, crawler
│   │   ├── workspaces/      # Workspace CRUD, company management
│   │   ├── comparison/      # LLM-powered comparisons
│   │   ├── chatbot/         # RAG chatbot, embeddings
│   │   ├── documents/       # PDF upload & processing
│   │   ├── portfolio/       # Bank portfolio import
│   │   ├── graph/           # Relationship graph, BFS, warm path
│   │   ├── charts/          # Analytics data endpoints
│   │   ├── notifications/   # WebSocket per-user channels
│   │   ├── llm/             # OpenAI client, prompt templates
│   │   ├── middleware/      # HTML sanitizer
│   │   └── jobs/            # ARQ worker settings, job registry
│   ├── migrations/          # Alembic database migrations
│   ├── tests/               # pytest + Hypothesis property tests
│   ├── alembic.ini
│   └── pyproject.toml
├── frontend/                 # Next.js TypeScript frontend
│   ├── src/
│   │   ├── app/             # App Router pages
│   │   │   ├── (auth)/      # Login, Register
│   │   │   └── (dashboard)/ # Workspaces, Companies, Chat, Compare
│   │   ├── components/      # UI components (charts, dossier, graph)
│   │   ├── hooks/           # useAuth, useSearch, useWebSocket, useWorkspaces
│   │   └── lib/             # API client, WebSocket manager
│   ├── package.json
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── docker-compose.yml        # PostgreSQL + Redis (you create this)
└── README.md
```

---

## Step 1: Set Up Infrastructure (Docker)

Create a `docker-compose.yml` in the project root:

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: company_lens
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

volumes:
  postgres_data:
```

Start the services:

```bash
docker compose up -d
```

Verify they're running:

```bash
docker compose ps
# Both db and redis should show "healthy"
```

---

## Step 2: Configure Environment Variables

Create a `.env` file inside the `backend/` directory:

```bash
# backend/.env

# === REQUIRED SECRETS (app won't start without these) ===
SECRET_KEY=your-super-secret-jwt-key-at-least-32-chars-long
OPENAI_API_KEY=sk-your-openai-api-key-here
TAVILY_API_KEY=tvly-your-tavily-api-key-here
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/company_lens
REDIS_URL=redis://localhost:6379/0

# === OPTIONAL SETTINGS ===
ENVIRONMENT=development
DEBUG=true
APP_NAME=Company Lens
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=7
WORKSPACE_COMPANY_LIMIT=3
```

**Where to get the API keys:**
- **OpenAI**: https://platform.openai.com/api-keys
- **Tavily**: https://tavily.com (sign up for free tier)

Create a `.env.local` file for the frontend:

```bash
# frontend/.env.local
NEXT_PUBLIC_API_URL=http://localhost:8000/api
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

---

## Step 3: Set Up the Backend

```bash
cd backend

# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On macOS/Linux
# .venv\Scripts\activate   # On Windows

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
alembic upgrade head

# Verify the setup
python -c "from app.config import get_settings; print('Config OK:', get_settings().APP_NAME)"
```

### Enable PostgreSQL Extensions

Connect to the database and enable required extensions:

```bash
psql postgresql://postgres:postgres@localhost:5432/company_lens -c "
  CREATE EXTENSION IF NOT EXISTS vector;
  CREATE EXTENSION IF NOT EXISTS pg_trgm;
"
```

---

## Step 4: Set Up the Frontend

```bash
cd frontend

# Install dependencies
npm install

# Verify TypeScript compiles
npx tsc --noEmit
```

---

## Step 5: Run the Application

You need **3 terminal windows** (or use a process manager):

### Terminal 1 — Backend API Server

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at: **http://localhost:8000**
- OpenAPI docs: http://localhost:8000/api/docs
- ReDoc: http://localhost:8000/api/redoc

### Terminal 2 — ARQ Background Worker

```bash
cd backend
source .venv/bin/activate
arq app.jobs.settings.WorkerSettings
```

This processes background jobs: research pipeline, comparisons, document processing, embeddings.

### Terminal 3 — Frontend Dev Server

```bash
cd frontend
npm run dev
```

The frontend will be available at: **http://localhost:3000**

---

## Step 6: Generate Frontend API Types (Optional)

After the backend is running, generate TypeScript types from the OpenAPI schema:

```bash
cd frontend
npm run generate-types
```

This runs `openapi-typescript` against `http://localhost:8000/openapi.json` and outputs types to `src/lib/types.ts`.

---

## Running Tests

### Backend Tests

```bash
cd backend
source .venv/bin/activate

# Run all tests (425 tests, including property-based tests)
pytest

# Run with verbose output
pytest -v

# Run only property-based tests
pytest tests/properties/

# Run a specific test file
pytest tests/test_auth_router.py

# Run with coverage
pytest --cov=app --cov-report=term-missing
```

### Frontend Type Check

```bash
cd frontend
npx tsc --noEmit
```

---

## API Endpoints Summary

| Module | Method | Endpoint | Description |
|--------|--------|----------|-------------|
| **Auth** | POST | `/api/auth/register` | Create account |
| | POST | `/api/auth/login` | Get JWT tokens |
| | POST | `/api/auth/refresh` | Refresh access token |
| | POST | `/api/auth/logout` | Invalidate refresh token |
| **Search** | GET | `/api/companies/search?q=` | Fuzzy company search |
| **Companies** | GET | `/api/companies/{id}` | Get company detail |
| | POST | `/api/companies/research` | Start AI research |
| | POST | `/api/companies/{id}/refresh` | Re-run research |
| **Workspaces** | GET | `/api/workspaces` | List workspaces |
| | POST | `/api/workspaces` | Create workspace |
| | GET | `/api/workspaces/{id}` | Workspace detail |
| | PUT | `/api/workspaces/{id}` | Update name |
| | DELETE | `/api/workspaces/{id}` | Delete (cascade) |
| | POST | `/api/workspaces/{id}/companies` | Add company |
| | DELETE | `/api/workspaces/{id}/companies/{cid}` | Remove company |
| **Compare** | POST | `/api/workspaces/{id}/compare` | Start comparison |
| | GET | `/api/workspaces/{id}/reports/{rid}` | Get report |
| **Chat** | POST | `/api/workspaces/{id}/chat` | Send message |
| | GET | `/api/workspaces/{id}/chat/history` | Get history |
| **Documents** | POST | `/api/companies/{id}/documents` | Upload PDF |
| | GET | `/api/companies/{id}/documents` | List documents |
| **Portfolio** | POST | `/api/portfolio/import` | Import CSV/TSV |
| | GET | `/api/portfolio/queue` | Unmatched names |
| | GET | `/api/companies/{id}/portfolio` | Get portfolio |
| **Graph** | GET | `/api/companies/{id}/graph?depth=1` | Relationship graph |
| | POST | `/api/companies/{id}/graph/edges` | Add edge |
| | GET | `/api/companies/{id}/warm-path` | Find warm path |
| **Charts** | GET | `/api/companies/{id}/scores/history` | Score history |
| | GET | `/api/workspaces/{id}/analytics` | Workspace analytics |
| **WebSocket** | WS | `/api/ws?token={jwt}` | Real-time events |

---

## How It Works (User Flow)

1. **Register/Login** → Get JWT tokens
2. **Search** a company name → If found, view dossier; if not, click "Research"
3. **Research pipeline** runs automatically:
   - Tavily web search → URL crawling → LLM profile generation → Scoring → Relationship extraction
   - Progress streams via WebSocket in real-time
4. **View dossier** with 5 tabs: Profile, Financials, Scores, Portfolio, Connections
5. **Add to workspace** (target list) for comparison and chat
6. **Compare** 2-3 companies side-by-side (LLM-generated HTML report)
7. **Chat** with the RAG chatbot about workspace companies
8. **Upload documents** (PDFs) to enrich company knowledge
9. **Import portfolio** (CSV/TSV) for existing client analysis

---

## Troubleshooting

### "Required configuration 'X' is missing or empty"
→ Make sure your `backend/.env` file has all required variables filled in.

### Database connection refused
→ Make sure Docker is running: `docker compose up -d`

### "pg_trgm" or "vector" extension not found
→ Run the extension creation commands in Step 3.

### Frontend can't reach backend API
→ Check `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000/api`

### ARQ worker won't start
→ Make sure Redis is running: `docker compose ps` should show redis as healthy.

### Tests fail with "connection refused"
→ Tests mock the database, so PostgreSQL doesn't need to be running for tests. If you see import errors, make sure you installed dev dependencies: `pip install -e ".[dev]"`

---

## Production Deployment Notes

For production, update the `.env`:

```bash
ENVIRONMENT=production
DEBUG=false
SECRET_KEY=<generate-a-strong-random-key>
DATABASE_URL=postgresql://user:pass@your-db-host:5432/company_lens
REDIS_URL=redis://your-redis-host:6379/0
```

In production:
- OpenAPI docs are disabled automatically
- Debug mode is off
- Use `gunicorn` with `uvicorn` workers: `gunicorn app.main:app -k uvicorn.workers.UvicornWorker`
- Run the frontend with `npm run build && npm start`
- Use a reverse proxy (nginx/Caddy) to serve both on the same domain
