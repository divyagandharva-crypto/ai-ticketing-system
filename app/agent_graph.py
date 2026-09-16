"""
LangGraph version of the ticket-resolution agent.

Where the Day 13 agent (app/agent.py) let Claude freely choose which tool
to call and in what order, this version defines an explicit graph of
fixed steps with a conditional branch: fetch ticket -> find similar
tickets -> generate a suggestion -> route based on confidence.

This is the pattern to use when you want predictable, auditable behavior
(e.g. "low-confidence suggestions must always go to a human, no
exceptions") rather than leaving that decision up to the model each time.
That's the concrete answer to "why LangGraph over plain tool-use" in an
interview: control over the control flow itself, not just the tool calls.
"""

from typing import TypedDict, Optional
from sqlalchemy.orm import Session
from langgraph.graph import StateGraph, END

from . import models, ai


class AgentState(TypedDict):
    ticket_id: int
    ticket: Optional[dict]
    similar_tickets: Optional[list]
    suggestion: Optional[dict]
    final_answer: Optional[str]
    needs_human_review: bool
    error: Optional[str]


def build_graph(db: Session):
    """
    Builds and compiles the graph. Takes a db session so each node can
    query the database directly (nodes are plain functions, not FastAPI
    route handlers, so there's no Depends() injection here — the session
    is just captured in a closure).
    """

    def fetch_ticket(state: AgentState) -> AgentState:
        ticket = db.query(models.Ticket).filter(models.Ticket.id == state["ticket_id"]).first()
        if not ticket:
            state["error"] = f"No ticket with id {state['ticket_id']}"
            return state
        state["ticket"] = {
            "id": ticket.id,
            "title": ticket.title,
            "description": ticket.description,
            "status": ticket.status,
        }
        return state

    def find_similar(state: AgentState) -> AgentState:
        if state.get("error"):
            return state
        ticket = db.query(models.Ticket).filter(models.Ticket.id == state["ticket_id"]).first()
        if ticket.embedding is None:
            state["error"] = "This ticket has no embedding yet — run the backfill script."
            return state
        similar = (
            db.query(models.Ticket)
            .filter(models.Ticket.id != ticket.id)
            .order_by(models.Ticket.embedding.cosine_distance(ticket.embedding))
            .limit(3)
            .all()
        )
        state["similar_tickets"] = [
            {"title": t.title, "description": t.description, "status": t.status}
            for t in similar
        ]
        return state

    def generate_suggestion(state: AgentState) -> AgentState:
        if state.get("error"):
            return state
        suggestion = ai.suggest_resolution(
            state["ticket"]["title"],
            state["ticket"]["description"],
            state["similar_tickets"],
        )
        state["suggestion"] = suggestion
        state["needs_human_review"] = suggestion.get("confidence") == "low"
        return state

    def finalize(state: AgentState) -> AgentState:
        if state.get("error"):
            state["final_answer"] = f"Could not process ticket: {state['error']}"
            return state
        state["final_answer"] = (
            f"Suggested resolution: {state['suggestion']['suggested_resolution']} "
            f"(confidence: {state['suggestion']['confidence']})"
        )
        return state

    def human_review(state: AgentState) -> AgentState:
        state["final_answer"] = (
            "This suggestion has low confidence and needs human review before acting on it. "
            f"Model's draft suggestion for reference: {state['suggestion']['suggested_resolution']}"
        )
        return state

    def route_after_suggestion(state: AgentState) -> str:
        if state.get("error"):
            return "finalize"
        return "human_review" if state["needs_human_review"] else "finalize"

    graph = StateGraph(AgentState)
    graph.add_node("fetch_ticket", fetch_ticket)
    graph.add_node("find_similar", find_similar)
    graph.add_node("generate_suggestion", generate_suggestion)
    graph.add_node("finalize", finalize)
    graph.add_node("human_review", human_review)

    graph.set_entry_point("fetch_ticket")
    graph.add_edge("fetch_ticket", "find_similar")
    graph.add_edge("find_similar", "generate_suggestion")
    graph.add_conditional_edges(
        "generate_suggestion",
        route_after_suggestion,
        {"finalize": "finalize", "human_review": "human_review"},
    )
    graph.add_edge("finalize", END)
    graph.add_edge("human_review", END)

    return graph.compile()


def run_graph_agent(ticket_id: int, db: Session) -> dict:
    compiled = build_graph(db)
    initial_state: AgentState = {
        "ticket_id": ticket_id,
        "ticket": None,
        "similar_tickets": None,
        "suggestion": None,
        "final_answer": None,
        "needs_human_review": False,
        "error": None,
    }
    result = compiled.invoke(initial_state)
    return result