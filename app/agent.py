"""
Tool-use agent for the ticketing system.

Reuses the exact same Anthropic client as ai.py, but this time gives Claude
a set of tools (backed by real DB queries and the existing embedding/
generation functions) and lets Claude decide which to call, in a loop,
based on a natural-language request.

This is the "agent" piece of the portfolio project: not a single hardcoded
call to Claude, but a model that reasons about which tool to use, sees the
result, and decides what to do next.
"""

import json
from sqlalchemy.orm import Session
from anthropic import Anthropic


from . import models, ai
from .config import settings
from .embeddings import embed_text

client = Anthropic(api_key=settings.anthropic_api_key)

MODEL = "claude-sonnet-4-5"

# ---------------------------------------------------------------------------
# Tool schemas — these are what Claude "sees." Keep descriptions specific;
# Claude picks tools based on these descriptions, not on your code.
# ---------------------------------------------------------------------------

TOOLS = [
    {
        "name": "get_ticket",
        "description": "Look up a single support ticket by its ID. Returns title, description, status, priority.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ID of the ticket to look up"}
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "find_similar_tickets",
        "description": "Find past tickets that are semantically similar to a given ticket, using vector similarity search. Useful for finding precedent on how similar issues were handled.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ID of the ticket to find similar tickets for"},
                "limit": {"type": "integer", "description": "How many similar tickets to return (default 3)"},
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "analyze_ticket",
        "description": "Classify a ticket's category (bug/feature-request/question) and urgency (low/medium/high), with a one-sentence summary.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ID of the ticket to analyze"}
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "suggest_resolution",
        "description": "Generate a suggested resolution for a ticket, grounded in similar past tickets. Use this when the user wants an actual recommended fix or next step, not just classification.",
        "input_schema": {
            "type": "object",
            "properties": {
                "ticket_id": {"type": "integer", "description": "The ID of the ticket to suggest a resolution for"}
            },
            "required": ["ticket_id"],
        },
    },
]


# ---------------------------------------------------------------------------
# Tool execution — the real DB-backed logic behind each tool name.
# These deliberately mirror the query patterns already used in tickets.py,
# so behavior stays consistent with the tested REST endpoints.
# ---------------------------------------------------------------------------

def _get_ticket_row(db: Session, ticket_id: int):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        return None
    return ticket


def execute_tool(tool_name: str, tool_input: dict, db: Session) -> dict:
    if tool_name == "get_ticket":
        ticket = _get_ticket_row(db, tool_input["ticket_id"])
        if not ticket:
            return {"error": f"No ticket with id {tool_input['ticket_id']}"}
        return {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "priority": ticket.priority,
        }

    elif tool_name == "find_similar_tickets":
        ticket = _get_ticket_row(db, tool_input["ticket_id"])
        if not ticket:
            return {"error": f"No ticket with id {tool_input['ticket_id']}"}
        if ticket.embedding is None:
            return {"error": "This ticket has no embedding yet — run the backfill script."}

        limit = tool_input.get("limit", 3)
        similar = (
            db.query(models.Ticket)
            .filter(models.Ticket.id != ticket.id)
            .order_by(models.Ticket.embedding.cosine_distance(ticket.embedding))
            .limit(limit)
            .all()
        )
        return {
            "similar_tickets": [
                {"id": t.id, "title": t.title, "description": t.description, "status": t.status}
                for t in similar
            ]
        }

    elif tool_name == "analyze_ticket":
        ticket = _get_ticket_row(db, tool_input["ticket_id"])
        if not ticket:
            return {"error": f"No ticket with id {tool_input['ticket_id']}"}
        return ai.analyze_ticket(ticket.title, ticket.description)

    elif tool_name == "suggest_resolution":
        ticket = _get_ticket_row(db, tool_input["ticket_id"])
        if not ticket:
            return {"error": f"No ticket with id {tool_input['ticket_id']}"}
        if ticket.embedding is None:
            return {"error": "This ticket has no embedding yet — run the backfill script."}

        similar = (
            db.query(models.Ticket)
            .filter(models.Ticket.id != ticket.id)
            .order_by(models.Ticket.embedding.cosine_distance(ticket.embedding))
            .limit(3)
            .all()
        )
        similar_tickets = [
            {"title": t.title, "description": t.description, "status": t.status}
            for t in similar
        ]
        return ai.suggest_resolution(ticket.title, ticket.description, similar_tickets)

    else:
        return {"error": f"Unknown tool: {tool_name}"}


# ---------------------------------------------------------------------------
# The agent loop
# ---------------------------------------------------------------------------

def run_agent(user_message: str, db: Session, max_turns: int = 5) -> dict:
    """
    Runs a tool-use loop: send the user's message to Claude with the tool
    definitions, execute whichever tool(s) Claude asks for, feed the
    results back, and repeat until Claude responds with plain text
    (stop_reason == "end_turn") or max_turns is hit.

    Returns a dict with the final text answer and a trace of which tools
    were called, for debugging/demo purposes.
    """
    messages = [{"role": "user", "content": user_message}]
    tool_calls_trace = []

    for _ in range(max_turns):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            final_text = "".join(
                block.text for block in response.content if block.type == "text"
            )
            return {"answer": final_text, "tool_calls": tool_calls_trace}

        # Claude wants to call one or more tools. Append its turn, then
        # append our tool results, then loop again.
        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = execute_tool(block.name, block.input, db)
                tool_calls_trace.append({"tool": block.name, "input": block.input, "result": result})
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

        messages.append({"role": "user", "content": tool_results})

    return {"answer": "Reached max turns without a final answer.", "tool_calls": tool_calls_trace}