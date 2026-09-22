# Ticketing Project — Debugging Log

A running record of every real bug and environment issue hit while building the FastAPI ticketing system, and how each was diagnosed and fixed. Kept for interview stories ("tell me about a hard bug you debugged") and so the same problem never gets re-solved twice.

---

## Backend / API build

### 1. Postgres foreign keys not saving via pgAdmin GUI
- **Symptom:** Foreign key relationships set up through pgAdmin's table editor weren't persisting.
- **Cause:** GUI-based constraint creation wasn't applying correctly.
- **Fix:** Added the foreign keys directly via SQL (`ALTER TABLE ... ADD CONSTRAINT ... FOREIGN KEY ...`) instead of the GUI.

### 2. Missing auto-increment on `id` columns
- **Symptom:** New rows failed or required manually specifying `id`.
- **Cause:** `id` columns weren't set up as identity/auto-increment columns.
- **Fix:** `ALTER TABLE ... ALTER COLUMN id ADD GENERATED ALWAYS AS IDENTITY`.

### 3. bcrypt / passlib version incompatibility
- **Symptom:** Password hashing broke after installing `passlib`.
- **Cause:** Newer `bcrypt` versions aren't compatible with the `passlib` release being used.
- **Fix:** Pinned `bcrypt==4.0.1`.

### 4. DB password with special characters breaking connection string
- **Symptom:** SQLAlchemy connection failed to parse the DB URL.
- **Cause:** Special characters in the Postgres password weren't URL-encoded.
- **Fix:** URL-encoded the password when building the connection string.

### 5. `schemas.py` class ordering
- **Symptom:** `NameError` referencing `CommentBase`.
- **Cause:** `CommentBase` was referenced before it was defined further down the file.
- **Fix:** Reordered class definitions so base schemas are defined before anything that references them.

### 6. Missing/typo'd `__init__.py` files
- **Symptom:** Import errors across `app/` and `app/routers/`.
- **Cause:** Typos in `__init__.py` filenames (package not recognized).
- **Fix:** Corrected filenames so `app/` and `app/routers/` were proper Python packages.

### 7. Repeated accidental code deletion during edits
- **Symptom:** Endpoints silently disappearing after edits.
- **Cause:** Manual edits occasionally overwrote existing code.
- **Fix:** Adopted a standard 7-step Postman CRUD test sequence run after every change, to catch regressions immediately.

---

## Docker / WSL2 / pgvector setup (Sept 2026)

### 8. `CREATE EXTENSION vector` â†’ "extension is not available"
- **Symptom:** `ERROR: extension "vector" is not available` on local Postgres install.
- **Cause:** pgvector was never compiled/installed at the OS level on the local (non-Docker) Postgres.
- **Fix:** Moved to a `pgvector/pgvector:pg16` Docker image, which ships the extension precompiled, instead of building it from source on Windows.

### 9. `docker ps` â†’ 500 Internal Server Error (Docker engine unreachable)
- **Symptom:** `request returned 500 Internal Server Error ... dockerDesktopLinuxEngine`.
- **Cause:** WSL2 wasn't installed at all — Docker Desktop's Linux engine had nothing to run on.
- **Fix:** `wsl --install`, restart machine.

### 10. `wsl --status` â†’ "WSL1 is not supported with your current machine configuration"
- **Symptom:** Confusing warning after enabling WSL2 as default.
- **Cause:** Red herring — WSL1 unavailability is unrelated and doesn't block WSL2/Docker.
- **Fix:** Ignored; confirmed via `wsl -l -v` that no distro was installed yet, then ran `wsl --install -d Ubuntu`.

### 11. Docker Desktop â†’ "Virtualization support not detected"
- **Symptom:** Docker Desktop failed to start; Task Manager showed CPU Virtualization: **Disabled**.
- **Cause:** Hardware virtualization (Intel VT-x) was turned off in BIOS/UEFI — a firmware setting, not a Windows toggle. (Windows' own "Virtual Machine Platform" feature was already On, which masked the real cause initially.)
- **Fix:** Entered Lenovo BIOS (Settings â†’ System â†’ Recovery â†’ Advanced startup â†’ Restart now â†’ Troubleshoot â†’ Advanced options â†’ UEFI Firmware Settings) â†’ Security tab â†’ enabled Intel Virtualization Technology â†’ saved (F10) â†’ confirmed "Enabled" in Task Manager afterward.

### 12. Pydantic `Settings` â†’ `extra_forbidden` on `database_url`
- **Symptom:** `ValidationError: 1 validation error for Settings / database_url / Extra inputs are not permitted`.
- **Cause:** `.env` had a leftover `DATABASE_URL=...` combined-string line, but the `Settings` class only declares individual fields (`database_hostname`, `database_port`, etc.) — pydantic-settings rejects unrecognized keys by default.
- **Fix:** Removed the `DATABASE_URL` line entirely; kept only the individual fields matching `Settings`' declared attributes exactly.

### 13. `password authentication failed for user "postgres"` (Docker container)
- **Symptom:** Both pgAdmin and the app failed to authenticate against the new container on port 5433.
- **Cause:** The original `docker run` command set `POSTGRES_PASSWORD=SAIram143$` directly in PowerShell — PowerShell treats `$` as its variable sigil, so the password was mangled before Docker ever received it. The container's real password didn't match what was typed everywhere else.
- **Fix:** Reset the password **from inside the container**, bypassing PowerShell's interpolation entirely:
  ```
  docker exec -it ticketing-pg psql -U postgres -d ticketing_db -c "ALTER USER postgres WITH PASSWORD 'SAIram143dollar';"
  ```
  Switched to a password with no shell-special characters going forward to avoid the whole class of bug.

### 14. pgAdmin running commands against the wrong server
- **Symptom:** `ALTER USER` appeared to succeed but the container password still didn't work; `CREATE EXTENSION` kept failing even after Docker was healthy.
- **Cause:** pgAdmin had multiple registered servers (original local Postgres on 5432, a second auto-named "PostgreSQL 18" also on 5432, and eventually the real Docker container on 5433). Query Tool tabs stay bound to whichever server they were opened from — commands were being run against the wrong (local) server without it being obvious from the UI.
- **Fix:** Registered a clearly-named server (`ticketing-docker`, host `localhost`, port `5433`), and made a habit of checking the query tab's header (`...@ticketing-docker`) before running anything, rather than trusting the SQL content alone.

### 15. `pip install pgvector` â†’ "'pip' is not recognized"
- **Symptom:** `pip` not found as a command.
- **Cause:** Running the command from `C:\WINDOWS\system32` in a fresh terminal with the project's virtual environment not activated — `pip` only resolves on PATH inside the activated venv.
- **Fix:** `cd` into the project folder, then `venv\Scripts\Activate.ps1` (confirm prompt shows `(venv)`) before running any `pip` command.

---

## Recurring lessons (good interview talking points)

- **PowerShell vs. cmd.exe matter** — `Get-Content` (PowerShell) vs `type` (cmd) aren't interchangeable; always confirm which shell you're in.
- **`$` in PowerShell strings gets interpreted** — avoid shell-special characters in passwords passed via CLI flags, or wrap/escape them properly.
- **A UI showing "connected" doesn't mean it's connected to the right thing** — always verify pgAdmin's active tab/server before trusting query results.
- **A working local dev environment often means several layers stacked correctly**: BIOS virtualization â†’ WSL2 â†’ Docker Desktop â†’ container â†’ app config all have to agree, and an error from the top of that stack can actually originate at the bottom.

### 16. Duplicate `class Ticket(Base):` definition â†’ "could not assemble any primary key columns"
- **Symptom:** `sqlalchemy.exc.ArgumentError: Mapper Mapper[Ticket(tickets)] could not assemble any primary key columns for mapped table 'tickets'`.
- **Cause:** An example snippet showing how to add the `embedding` column was pasted in as a second, separate `class Ticket(Base):` block instead of being merged into the existing one — the first (incomplete) class had no `id` column, and SQLAlchemy choked on the duplicate class definition.
- **Fix:** Removed the incomplete duplicate class; added `embedding = Column(Vector(384))` as a single line inside the real, complete `Ticket` class.

### 17. `ModuleNotFoundError: No module named 'app.embeddings'`
- **Symptom:** Import error on startup after updating `tickets.py` to import from `..embeddings`.
- **Cause:** The new `embeddings.py` helper file hadn't actually been saved into the `app/` folder yet — only `tickets.py` (which imports from it) had been updated.
- **Fix:** Saved `embeddings.py` alongside `models.py`/`database.py`/`config.py` in `app/`.

### 18. Apparent hang on `uvicorn` startup after adding embeddings
- **Symptom:** Terminal appeared frozen with no output for an extended period; interrupted with Ctrl+C, which then printed a scary-looking but irrelevant asyncio/tempfile traceback ending in `KeyboardInterrupt`.
- **Cause:** Not a real error — `sentence-transformers` downloads/loads the `all-MiniLM-L6-v2` model (~90MB) on first import, which can take a minute or two and produces no console output while it happens, easily mistaken for a hang.
- **Fix:** Re-ran and waited without interrupting; startup completed normally once the model finished loading.

## RAG Pipeline — Day 10-11: CONFIRMED COMPLETE

Full retrieval-to-generation loop tested and working end-to-end via Postman:
1. `POST /tickets/` auto-embeds new tickets on creation (all-MiniLM-L6-v2, 384-dim)
2. `GET /tickets/{id}/similar` retrieves nearest tickets via pgvector cosine distance — correctly ranked a semantically similar login ticket above an unrelated invoice ticket
3. `GET /tickets/{id}/suggest-resolution` combines the similarity lookup with a Claude generation call — returned a grounded suggestion (`based_on_similar_tickets: true`) referencing the actual similar ticket's context, not a generic answer

### 19. New endpoint pasted at top of file instead of bottom â†’ NameError: name 'router' is not defined
- **Symptom:** `uvicorn` crashed on import with `NameError: name 'router' is not defined` pointing at the new `@router.get(...)` decorator.
- **Cause:** The new function was pasted at the very top of `tickets.py`, above the line that actually defines `router = APIRouter(...)`.
- **Fix:** Moved the function to the bottom of the file, after all existing route definitions. Lesson: when adding a route to an existing router file, always paste at the end, never at the top.

## Day 13 — Tool-use agent: CONFIRMED WORKING

Built `app/agent.py` (tool schemas + execution + tool-use loop) and a new
`POST /agent/chat` endpoint. Tested with "Help me resolve ticket 1" —
Claude autonomously called `get_ticket` first, then decided on its own to
call `suggest_resolution`, and returned a formatted answer with next steps.
No hardcoded call sequence — genuinely agentic tool selection, confirmed
via the `tool_calls` trace in the response.

Second test confirmed correct tool selection based on intent, not a fixed
sequence: "Is ticket 3 urgent? What category is it?" â†’ agent called only
`analyze_ticket` (not `get_ticket` or `suggest_resolution`), correctly
matching the classification-style question. Day 13 tool-use agent fully
validated with two distinct request types choosing two distinct tools.

## Day 14 — LangGraph agent: CONFIRMED WORKING

Built `app/agent_graph.py`: a fixed graph (fetch_ticket -> find_similar ->
generate_suggestion -> conditional route on confidence -> finalize or
human_review). Wired to `POST /agent/resolve-graph/{ticket_id}`. Tested
against ticket 1 — full state returned correctly at each step, medium
confidence correctly routed to `finalize` (`needs_human_review: false`).

### 20. New endpoint pasted with wrong import target, then endpoint body omitted entirely
- **Symptom 1:** `ImportError: attempted relative import beyond top-level package` on startup.
- **Cause 1:** `from ..agent_graph import run_graph_agent` was pasted into `app/agent.py` (one directory shallower than routers) instead of `app/routers/agent.py`, so `..` resolved one level too high.
- **Fix 1:** Removed the line from `agent.py`; confirmed it only belongs in `routers/agent.py`.
- **Symptom 2:** After fixing the import, `POST /agent/resolve-graph/1` returned 404 Not Found.
- **Cause 2:** Only the import line had been added to `routers/agent.py` — the actual `@router.post("/resolve-graph/{ticket_id}")` endpoint function was never pasted in.
- **Fix 2:** Added the missing endpoint function to the bottom of the file.
- **Lesson reinforced:** when an addition has multiple parts (import + function body), verify both landed in the right file before restarting — a clean startup after fixing the import masked the fact that the endpoint itself was still missing.

Confirmed the human_review branch with a deliberately vague test ticket
("Something's wrong" / "It doesn't work right", id 4). Result: confidence
low, needs_human_review true, final_answer correctly switched to the
escalation message. Model also correctly flagged based_on_similar_tickets
as false despite similar tickets being retrieved — didn't force a match.
Both branches of the Day 14 graph are now confirmed working.

## Days 13-14: FULLY COMPLETE
Two working agent patterns on the same project: native tool-use (Day 13,
model freely selects tools per request) and LangGraph (Day 14, fixed
graph with a tested conditional branch to human review). Both tested
against multiple ticket types with correct, distinct behavior in each
case.

### 21. Zombie uvicorn process silently serving stale code after key rotation
- **Symptom:** After rotating the Anthropic API key, `/agent/chat` returned 500 errors with zero output in the visible uvicorn terminal — looked like the server wasn't receiving requests at all, despite curl/Postman showing real response times.
- **Cause:** An old uvicorn process (bound to port 8000) from earlier in the session had never been properly terminated. It kept LISTENING on port 8000 and silently absorbed every new request, running old code with the old (pre-rotation) API key — while a *second*, newer uvicorn instance sat in a different terminal tab doing nothing, since the OS was routing traffic to whichever process grabbed the port first.
- **Diagnosis path:** `netstat -ano | findstr :8000` revealed a listening PID that didn't match the most recently started `uvicorn` process's printed PID — the smoking gun. Confirmed further by adding a global FastAPI exception handler to force the real traceback into the response body (`traceback.print_exc()` + returning `{"error": str(exc)}`), which finally surfaced the real underlying error: `anthropic.AuthenticationError: API key is invalid` — i.e., the zombie process really was using the stale key.
- **Fix:** `taskkill /PID <pid> /F` to kill the zombie, confirmed the port was clear, started a single fresh `uvicorn` instance, then retested — worked immediately.
- **Side lesson:** verified the new key was valid independently first via a standalone Python script (bypassing curl/PowerShell quoting issues entirely, which cost significant time via mangled `-d` JSON and BOM-prefixed files from `Out-File -Encoding utf8`). For any future "is this credential actually valid" question, prefer a small `.py` script using the app's own `Settings`/client setup over shell one-liners on Windows — far fewer moving parts to go wrong.

## Days 13-14 agent: reconfirmed working end-to-end after key rotation
`/agent/chat` on "help me to resolve ticket 1" chained four tools autonomously (get_ticket, analyze_ticket, find_similar_tickets, suggest_resolution) into one coherent answer — strongest demo of multi-step autonomous tool use yet.

## Week 3 — Eval harness: BUILT AND RUN

Built `eval_harness.py` covering 4 categories: retrieval quality, generation
grounding (confidence calibration), tool-selection correctness, and
prompt-injection resistance. Seeded 15 additional test tickets across
login/auth, billing, urgent, cosmetic, and vague clusters via
`seed_test_tickets.py`.

First run: 9/10 passed.

### Finding: confidence scoring can be inflated by a near-duplicate vague ticket
- **Test:** ticket 17 ("Something's wrong" / "It doesn't work right") was
  expected to get low confidence, since it has almost no actionable
  information — same as the earlier ticket 4, which correctly got low
  confidence in Day 14 testing.
- **Actual:** ticket 17 got HIGH confidence instead.
- **Root cause:** ticket 4 (created earlier, nearly identical wording) was
  retrieved as a very close embedding match. The model interpreted having
  a strong precedent match as grounds for higher confidence — but the
  "precedent" was itself just as vague and uninformative. Precedent
  matching and information-sufficiency are being conflated.
- **Disposition:** kept as a documented finding rather than "fixed" — this
  is a legitimate discovered failure mode, not a test bug. Worth citing in
  a case study writeup as: confidence heuristics based on retrieval
  similarity alone can be fooled when two low-information items are
  similar to each other, independent of whether either one is actually
  actionable. A more robust design would score confidence based on the
  ticket's own information density, not just similarity to precedent.

## Week 4 prep — RAG "known correct answer" eval: BUILT AND RUN

Built a second, more rigorous eval layer on top of the Week 3 eval_harness.py:
a 50-question set (`rag_eval_qa_full.py`) with known expected answers across
10 categories (factual lookup, classification, retrieval, generation quality,
near-duplicate awareness, multi-ticket comparison, ambiguous/underspecified
questions, out-of-scope guardrails, prompt-injection variants, format/
robustness), graded automatically by a Claude-as-judge script
(`rag_eval_grader.py`) against the live `/agent/chat` endpoint.

Where eval_harness.py checks structural correctness (right tool called,
right IDs retrieved), this checks answer QUALITY — is the actual generated
text correct, well-reasoned, and safe.

**First run: false failure due to expired JWT (401s on most calls) —
re-ran with a fresh token immediately before running.**

**Second (clean) run: 48/50 correct.**

### Finding 1: retrieval degrades in underrepresented clusters (q15)
- Ticket 16 ("typo in welcome email," cosmetic cluster) failed to retrieve
  ticket 15 (the only other cosmetic ticket) as most similar — it matched
  login-cluster tickets instead.
- Root cause: with only 2 tickets in the cosmetic cluster vs. 6+ in login,
  there's far less embedding signal to anchor to, so a sparse cluster
  loses out to a denser one during nearest-neighbor search.
- Disposition: kept as a documented finding. Same underlying class of
  issue as the ticket-17 confidence-inflation finding from Week 3 —
  retrieval-based behavior is sensitive to how much data exists per
  category, which matters for real deployments with imbalanced ticket
  volume across issue types.

### Finding 2 (partially a test-design flaw, partially a real question) (q44)
- Prompt-injection test cases (q41-q45) embedded a fake ticket description
  directly in the chat message text, but the grader script never actually
  called POST /tickets/ to create a real ticket first — so there was no
  real ticket behind the question.
- Result: the agent picked an arbitrary existing ticket (ticket 1) and
  answered about that instead of asking for clarification.
- This is a bug in the eval script's design, not necessarily the agent —
  but it surfaces a real, worth-investigating inconsistency: the agent
  correctly asks for clarification on genuinely ambiguous questions with
  no ticket reference at all (ambiguous category: 5/5), but here, given a
  vague, unanchored "this ticket" reference with descriptive text but no
  ID, it guessed instead of asking. Worth a follow-up eval case with a
  *real* injected ticket to isolate whether this is really inconsistent
  behavior or just an artifact of the malformed test.
- Note for future eval design: any test case that references "the ticket
  just created" must actually create it via the real API first, not just
  describe it in the question text.

Files pushed to GitHub: rag_eval_qa_full.py, rag_eval_grader.py,
rag_eval_results.json.
## Week 4 — RAG eval fix, re-run, and production infra finding

### Fixed the eval script's prompt-injection test design
The original `rag_eval_grader.py` (q41â€“q45, prompt-injection category) embedded
the malicious ticket description as literal text inside the chat *message*
sent to `/agent/chat`, without ever calling `POST /tickets/` to create a real
ticket first. This meant there was no actual ticket behind the question — the
agent had to guess which numbered ticket "this ticket" referred to, which
produced a misleading INCORRECT result on q44 in the first run (48/50).

**Fix:** `rag_eval_qa_full.py` now carries the injection payload as
`inject_title` / `inject_description` data fields. `rag_eval_grader.py`
creates a real ticket from those fields via `POST /tickets/` before asking
the agent about it, so the agent is tested against genuinely stored,
untrusted content — the same threat model the `SYSTEM_PROMPT` boundary in
`agent.py` is meant to hold against, rather than text typed into the chat
message itself.

### Local re-run: 47/50 correct (0 partial â†’ 2 partial, 1 incorrect, 0 errors)
With the fix in place, all five prompt-injection cases (q41â€“q45) passed —
confirming q44's earlier failure was a test-script bug, not an agent bug.

- **q15 (retrieval, INCORRECT)** — reproduced from the first run: ticket 16
  ("typo in welcome email," cosmetic cluster) matches login-cluster tickets
  instead of ticket 15 (the only other cosmetic ticket). Reproduced across
  two independent runs, so this is a real, citable finding: retrieval
  quality degrades in underrepresented clusters when embedding signal is
  sparse (2 cosmetic tickets vs. 6+ login tickets).
- **q12 (retrieval, PARTIAL, new)** — similarity search for the double-charge
  ticket returned two correct billing tickets plus one login ticket; the
  agent itself flagged the login ticket as irrelevant in its answer. Minor
  retrieval noise, self-corrected at the generation step.
- **q20 (generation, PARTIAL, new)** — 2FA resolution suggestion covered
  SMS/backup-code troubleshooting but missed the specific "check time-sync"
  detail called out in the grading notes. Borderline — a strict grading
  note more than a real gap.

### Production run: blocked by Cloudflare bot protection, not an app bug
Two separate issues surfaced when pointing the eval at the live Render app:

1. **Missing seed data.** Production's ticket table only ever had tickets 1
   and 2 natively, plus a restricted test ticket (id 3) added during the
   earlier security verification session — not the full 19-ticket cluster
   set the eval script assumes. Wrote `seed_production_tickets.py` to check
   existing tickets via `GET /tickets/` and seed the matching set, with a
   confirmation step before creating anything.
2. **Cloudflare challenge, not simple rate limiting.** Running the seeder
   against production triggered Cloudflare's bot-protection layer in front
   of the Render app: after the first couple of 502/503s, every subsequent
   `POST /tickets/` request came back with an interactive JS challenge page
   ("Just a moment...") instead of a normal HTTP error. This is a different
   failure mode than the earlier plain 429 rate-limiting — client-side
   retry-with-backoff (added to `rag_eval_grader.py`) can recover from
   429/502/503, but cannot pass a Cloudflare interactive challenge, which
   requires a real browser.

**Disposition:** zero tickets were created (the script aborted cleanly on
first confirmation, no partial/corrupted state left behind). Chose not to
keep retrying against production — repeated scripted requests risk
extending how long Cloudflare flags the traffic, for a problem no amount of
client-side retry logic can solve. **The local 47/50 result stands as the
RAG groundedness number for the case study; production RAG re-verification
is a known open item**, separate from the production *security* fix
verification (agent RBAC + prompt-injection), which already passed 6/6 live
against production in an earlier session — that verification used far fewer,
more spaced-out requests and never triggered Cloudflare.

Worth a line in the case study either way: correctly distinguishing "the
eval script has a bug" (q44, fixed) from "this is real agent behavior worth
citing" (q15) from "this is infrastructure, not application, and no amount
of code-level retry logic fixes it" (the Cloudflare block) is itself a
demonstration of the kind of triage a forward-deployed engineer needs to do
in production incidents.

Files updated/added: `rag_eval_qa_full.py`, `rag_eval_grader.py` (both
fixed), `seed_production_tickets.py` (new).

