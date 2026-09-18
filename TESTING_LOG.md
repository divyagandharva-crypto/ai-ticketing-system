# Live Deployment — Testing Log

*Date: 2026-09-18*

End-to-end verification of the AI Ticketing System deployed at [ai-ticketing-system-omfc.onrender.com](https://ai-ticketing-system-omfc.onrender.com), run directly against the live Swagger UI ([/docs](https://ai-ticketing-system-omfc.onrender.com/docs)) rather than locally.

## Setup

Authenticated through Swagger's built-in OAuth2 password flow (`POST /login`), which auto-attaches the resulting bearer token to every subsequent request made from the docs UI.

## Test 1 — User creation and login

| Step | Result |
| --- | --- |
| `POST /users/` | `201` — user created (`id: 1`, `email: test@example.com`) |
| `POST /login` | `200` — real JWT `access_token` returned |

Confirms the app reaches the live Postgres database (not just that the container booted) and can write and read back through it.

## Test 2 — Native tool-use agent (`/agent/chat`)

Created ticket 1 ("Cannot reset password" / Gmail reset-email issue), then sent:

```json
{ "message": "help me resolve ticket 1" }
```

The agent decided on its own — no hardcoded call order — to run:

1. `get_ticket` — fetched the ticket
2. `analyze_ticket` — classified it `bug`, `high` urgency
3. `suggest_resolution` — returned a grounded suggested fix, `confidence: medium`

Returned a formatted answer plus the full tool-call trace. Confirms the free-form tool-use loop is working live, with Claude choosing its own tool sequence rather than following a fixed script.

## Test 3 — LangGraph agent (`/agent/resolve-graph/{id}`), first run

Ran against the same ticket 1, which at this point was the only ticket in the database.

- `similar_tickets`: `[]` — expected, nothing else to find yet
- `suggestion.confidence`: `medium`, `based_on_similar_tickets: false`
- `needs_human_review`: `false` — above the confidence threshold, so it finalized rather than flagging for a human

Confirms the fixed pipeline (fetch → find similar → generate suggestion → route on confidence) runs correctly end-to-end, including the empty-retrieval path.

## Test 4 — RAG retrieval confirmed with a second, similar ticket

Created ticket 2, deliberately similar to ticket 1: "Not receiving password reset email" / another Gmail case. Re-ran `/agent/resolve-graph/2`.

- `similar_tickets`: now returned ticket 1 — pgvector's cosine-similarity search actually matched it, not the empty-fallback path
- `suggestion.based_on_similar_tickets`: `true`
- The suggested resolution changed qualitatively — it now names *"a pattern of Gmail users not receiving these emails"*, a claim only possible because the agent retrieved and reasoned over the related ticket

This is the clearest confirmation that the embeddings → pgvector similarity search → retrieval-augmented suggestion pipeline is genuinely working on the live deployment, not just returning a canned response.

## Summary

Every layer of the deployed system was exercised against the live URL, not locally:

| Layer | Verified by |
| --- | --- |
| Auth (JWT) | Test 1 |
| Database (Postgres) | Test 1 |
| Direct Claude API calls | Test 2 (`analyze_ticket`, `suggest_resolution`) |
| Free-form tool-use agent | Test 2 |
| Fixed LangGraph pipeline | Test 3, Test 4 |
| Embeddings + pgvector retrieval | Test 4 |

Nothing here was mocked or run against a local dev environment — every request hit [ai-ticketing-system-omfc.onrender.com](https://ai-ticketing-system-omfc.onrender.com) directly. This is the walkthrough to use if an interviewer asks to see the system live.
