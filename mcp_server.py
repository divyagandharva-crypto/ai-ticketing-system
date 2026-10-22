"""
MCP server exposing the ticketing system's tools over the Model Context
Protocol (MCP) -- so any MCP client (Claude Desktop, Claude Code, or a
different agent entirely) can call them directly, not just this app's own
agent loop.

This deliberately reuses the exact same DB queries and AI functions as
app/agent.py and app/routers/tickets.py, so tool BEHAVIOR stays identical
across all three ways these tools are now exposed:
  1. app/agent.py       -- native Claude tool-use loop (free-form ordering)
  2. app/agent_graph.py -- LangGraph, fixed step order + confidence routing
  3. mcp_server.py       -- MCP protocol, callable by any MCP client

That's the interview-ready point: the tool LAYER is portable. Only the
orchestration pattern around it changes.

Install:
    pip install mcp

Run:
    python mcp_server.py

This uses stdio transport (the standard for local MCP servers), so it's
meant to be launched BY an MCP client (like Claude Desktop), not run
standalone and left open -- see mcp_config_example.json for how Claude
Desktop is told to launch it.
"""

from mcp.server.fastmcp import FastMCP

from app.database import SessionLocal
from app import models, ai

mcp = FastMCP("ticketing-system")


def _get_ticket_row(db, ticket_id: int):
    return db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()


@mcp.tool()
def get_ticket(ticket_id: int) -> dict:
    """Look up a single support ticket by its ID. Returns title, description, status, priority."""
    db = SessionLocal()
    try:
        ticket = _get_ticket_row(db, ticket_id)
        if not ticket:
            return {"error": f"No ticket with id {ticket_id}"}
        return {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
            "priority": ticket.priority,
        }
    finally:
        db.close()


@mcp.tool()
def find_similar_tickets(ticket_id: int, limit: int = 3) -> dict:
    """Find past tickets semantically similar to a given ticket, using vector similarity search."""
    db = SessionLocal()
    try:
        ticket = _get_ticket_row(db, ticket_id)
        if not ticket:
            return {"error": f"No ticket with id {ticket_id}"}
        if ticket.embedding is None:
            return {"error": "This ticket has no embedding yet -- run the backfill script."}
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
    finally:
        db.close()


@mcp.tool()
def analyze_ticket(ticket_id: int) -> dict:
    """Classify a ticket's category (bug/feature-request/question) and urgency (low/medium/high), with a one-sentence summary."""
    db = SessionLocal()
    try:
        ticket = _get_ticket_row(db, ticket_id)
        if not ticket:
            return {"error": f"No ticket with id {ticket_id}"}
        return ai.analyze_ticket(ticket.title, ticket.description)
    finally:
        db.close()


@mcp.tool()
def suggest_resolution(ticket_id: int) -> dict:
    """Generate a suggested resolution for a ticket, grounded in similar past tickets."""
    db = SessionLocal()
    try:
        ticket = _get_ticket_row(db, ticket_id)
        if not ticket:
            return {"error": f"No ticket with id {ticket_id}"}
        if ticket.embedding is None:
            return {"error": "This ticket has no embedding yet -- run the backfill script."}
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
    finally:
        db.close()


if __name__ == "__main__":
    mcp.run()
