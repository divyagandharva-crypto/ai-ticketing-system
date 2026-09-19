"""
New router file: app/routers/agent.py
"""
from ..agent_graph import run_graph_agent
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from .. import oauth2, models
from ..agent import run_agent

router = APIRouter(
    prefix="/agent",
    tags=["Agent"]
)


class AgentRequest(BaseModel):
    message: str


@router.post("/chat")
def agent_chat(request: AgentRequest, db: Session = Depends(get_db),
               current_user: models.User = Depends(oauth2.get_current_user)):
    result = run_agent(request.message, db, current_user.clearance_level)
    return result


@router.post("/resolve-graph/{ticket_id}")
def agent_resolve_graph(ticket_id: int, db: Session = Depends(get_db),
                         current_user: models.User = Depends(oauth2.get_current_user)):
    result = run_graph_agent(ticket_id, db, current_user.clearance_level)
    return result