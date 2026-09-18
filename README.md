# AI Ticketing System

A customer support ticketing API built with FastAPI, demonstrating a full RAG (retrieval-augmented generation) pipeline and two distinct AI agent patterns on top of a real relational database.

See [ARCHITECTURE.md](./ARCHITECTURE.md) for the full system diagram and a component-by-component breakdown.

Built as a hands-on portfolio project for AI/Forward Deployed Engineer roles — every piece here was built and tested end-to-end, not scaffolded from a tutorial.

## Live demo

Deployed and running: **https://ai-ticketing-system-omfc.onrender.com**

Interactive API docs (Swagger UI): **https://ai-ticketing-system-omfc.onrender.com/docs**

> Hosted on Render's free tier, so the first request after a period of inactivity can take 30–60 seconds to wake up. Every request after that is fast.

### Try it yourself (no local setup required)

1. Open the [Swagger UI](https://ai-ticketing-system-omfc.onrender.com/docs).
2. **Create a test user** — expand `POST /users/`, click "Try it out", and submit:
   ```json
   { "email": "yourname@example.com", "password": "yourpassword" }
   ```
3. **Log in** — expand `POST /login`, click "Try it out", enter the same email/password, and submit. Copy the `access_token` from the response.
4. **Authorize** — click the "Authorize" button near the top of the page, paste the token in, and click Authorize. This attaches it to every request below.
5. **Create a ticket** — `POST /tickets/` with a `title` and `description`.
6. **See the AI features in action:**
   - `POST /tickets/{id}/analyze` — Claude classifies category/urgency and summarizes the ticket
   - `GET /tickets/{id}/similar` — pgvector cosine-similarity search against past tickets
   - `GET /tickets/{id}/suggest-resolution` — retrieves similar tickets and asks Claude for a grounded resolution
   - `POST /agent/chat` with `{ "message": "help me resolve ticket <id>" }` — the free-form tool-use agent picks which tools to call on its own
   - `POST /agent/resolve-graph/{id}` — the LangGraph pipeline, with a confidence-based branch to a "needs human review" step

Every endpoint is documented and runnable directly from Swagger — no Postman or local setup needed to see it work.

## What it does

- Standard ticketing CRUD: create, read, update, delete tickets; comments on tickets; JWT-based auth
- **Semantic search over tickets** — every ticket is embedded on creation (`all-MiniLM-L6-v2`, via `sentence-transformers`) and stored as a vector directly in Postgres using `pgvector`
- **RAG-based resolution suggestions** — given a ticket, retrieves the most similar past tickets by cosine similarity, then asks Claude to draft a grounded suggested resolution
- **Two agent patterns**, both built on the same underlying tools:
  - **Native tool-use agent** (`/agent/chat`) — Claude freely decides which tool to call (look up a ticket, find similar tickets, classify it, or suggest a resolution) based on a natural-language request
  - **LangGraph agent** (`/agent/resolve-graph/{id}`) — a fixed graph with an explicit conditional branch: low-confidence suggestions are routed to a "needs human review" step instead of being returned directly

## Architecture

```
Ticket created
      │
      ▼
Auto-embedded (sentence-transformers) ──▶ stored as vector in Postgres (pgvector)
      │
      ▼
GET /tickets/{id}/similar ──▶ pgvector cosine similarity search
      │
      ▼
GET /tickets/{id}/suggest-resolution ──▶ retrieved context + Claude ──▶ grounded suggestion

Two agent entry points on top of the same tools:
  POST /agent/chat              → Claude chooses tools freely (tool-use loop)
  POST /agent/resolve-graph/{id} → fixed LangGraph pipeline with a confidence-based branch
```

## Stack

- **API:** FastAPI, Pydantic, SQLAlchemy
- **Database:** PostgreSQL + `pgvector` (running in Docker)
- **Embeddings:** `sentence-transformers` (`all-MiniLM-L6-v2`, 384-dim)
- **LLM:** Anthropic Claude (`claude-sonnet-4-5`) — used for classification, resolution generation, and as the reasoning engine behind both agents
- **Agent orchestration:** native Claude tool-use, and LangGraph for the graph-based variant
- **Auth:** JWT (OAuth2 password flow)

## Running it locally

1. **Start Postgres with pgvector** (Docker):
   ```
   docker run -d --name ticketing-pg -e POSTGRES_PASSWORD=<your-password> -e POSTGRES_DB=ticketing_db -p 5433:5432 pgvector/pgvector:pg16
   ```

2. **Set up your environment:**
   ```
   python -m venv venv
   venv\Scripts\Activate.ps1   # Windows
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** in the project root (not committed — see `.gitignore`) with:
   ```
   DATABASE_HOSTNAME=localhost
   DATABASE_PORT=5433
   DATABASE_PASSWORD=<your-password>
   DATABASE_NAME=ticketing_db
   DATABASE_USERNAME=postgres
   SECRET_KEY=<your-jwt-secret>
   ALGORITHM=HS256
   ACCESS_TOKEN_EXPIRE_MINUTES=30
   ANTHROPIC_API_KEY=<your-anthropic-key>
   ```

4. **Enable the pgvector extension** (one-time, via psql or pgAdmin):
   ```sql
   CREATE EXTENSION IF NOT EXISTS vector;
   ```

5. **Run the app:**
   ```
   uvicorn app.main:app --reload
   ```

6. **Backfill embeddings** for any tickets created before the embedding column existed:
   ```
   python backfill_embeddings.py
   ```

A Postman collection is included under `postman/` with working example requests for every endpoint, including auth.

## Example: the agent in action

Request:
```json
POST /agent/chat
{ "message": "Help me resolve ticket 1" }
```

The agent autonomously calls `get_ticket`, then decides on its own to call `suggest_resolution`, and returns a formatted answer — no hardcoded call sequence. The full tool-call trace is included in the response for transparency.

## What this project demonstrates

- Building a real vector search pipeline on top of a relational database (not a bolted-on separate vector store)
- The practical difference between an LLM feature (one hardcoded prompt) and an actual agent (model-driven tool selection)
- When to use free-form tool-use versus a governed, auditable graph with explicit safety branches
- End-to-end debugging of a real local dev environment (Docker, WSL2, pgvector) — see `Debugging_Log.md` for the full trail of issues hit and how each was resolved
