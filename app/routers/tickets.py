from typing import List, Optional
from fastapi import APIRouter, Response, status, HTTPException, Depends
from sqlalchemy.orm import Session, joinedload
from .. import models, schemas, oauth2
from ..database import get_db
from .. import ai
from ..embeddings import embed_text


router = APIRouter(
    prefix="/tickets",
    tags=["Tickets"]
)


@router.get("/", response_model=List[schemas.Ticket])
def get_tickets(db: Session = Depends(get_db), limit: int = 10, skip: int = 0, search: Optional[str] = ""):
    tickets = db.query(models.Ticket).filter(
        models.Ticket.title.contains(search)
    ).limit(limit).offset(skip).all()
    return tickets


@router.get("/{ticket_id}", response_model=schemas.TicketWithCommentsOut)
def read_ticket(ticket_id: int, db: Session = Depends(get_db)):
    ticket = (
        db.query(models.Ticket)
        .options(
            joinedload(models.Ticket.comments).joinedload(models.Comment.author)
        )
        .filter(models.Ticket.id == ticket_id)
        .first()
    )
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {ticket_id} was not found")
    return ticket


@router.post("/", status_code=status.HTTP_201_CREATED, response_model=schemas.Ticket)
def create_ticket(ticket: schemas.TicketCreate, db: Session = Depends(get_db),
                   current_user: models.User = Depends(oauth2.get_current_user)):
    embedding = embed_text(f"{ticket.title} {ticket.description}")
    new_ticket = models.Ticket(created_by=current_user.id, embedding=embedding, **ticket.dict())
    db.add(new_ticket)
    db.commit()
    db.refresh(new_ticket)
    return new_ticket


@router.put("/{id}", response_model=schemas.Ticket)
def update_ticket(id: int, ticket: schemas.TicketCreate, db: Session = Depends(get_db),
                   current_user: models.User = Depends(oauth2.get_current_user)):
    ticket_query = db.query(models.Ticket).filter(models.Ticket.id == id)
    existing_ticket = ticket_query.first()
    if existing_ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {id} was not found")
    ticket_query.update(ticket.dict(), synchronize_session=False)
    db.commit()
    return ticket_query.first()


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ticket(id: int, db: Session = Depends(get_db),
                   current_user: models.User = Depends(oauth2.get_current_user)):
    ticket_query = db.query(models.Ticket).filter(models.Ticket.id == id)
    ticket = ticket_query.first()
    if ticket is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {id} was not found")
    ticket_query.delete(synchronize_session=False)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{ticket_id}/comments", status_code=status.HTTP_201_CREATED, response_model=schemas.Comment)
def create_comment(ticket_id: int, comment: schemas.CommentCreate, db: Session = Depends(get_db),
                    current_user: models.User = Depends(oauth2.get_current_user)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {ticket_id} was not found")
    new_comment = models.Comment(ticket_id=ticket_id, user_id=current_user.id, **comment.dict())
    db.add(new_comment)
    db.commit()
    db.refresh(new_comment)
    return new_comment


@router.get("/{ticket_id}/comments", response_model=List[schemas.Comment])
def get_comments(ticket_id: int, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == ticket_id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {ticket_id} was not found")
    comments = db.query(models.Comment).filter(models.Comment.ticket_id == ticket_id).all()
    return comments


@router.post("/{id}/analyze")
def analyze_ticket(id: int, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {id} was not found")

    analysis = ai.analyze_ticket(ticket.title, ticket.description)
    return {"data": analysis}


@router.get("/{id}/similar", response_model=List[schemas.Ticket])
def get_similar_tickets(id: int, limit: int = 5, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {id} was not found")
    if ticket.embedding is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This ticket has no embedding yet — run the backfill script.")

    similar = (
        db.query(models.Ticket)
        .filter(models.Ticket.id != id)
        .order_by(models.Ticket.embedding.cosine_distance(ticket.embedding))
        .limit(limit)
        .all()
    )
    return similar


@router.get("/{id}/suggest-resolution")
def suggest_resolution(id: int, limit: int = 3, db: Session = Depends(get_db)):
    ticket = db.query(models.Ticket).filter(models.Ticket.id == id).first()
    if not ticket:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"ticket with id: {id} was not found")
    if ticket.embedding is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="This ticket has no embedding yet — run the backfill script.")

    similar = (
        db.query(models.Ticket)
        .filter(models.Ticket.id != id)
        .order_by(models.Ticket.embedding.cosine_distance(ticket.embedding))
        .limit(limit)
        .all()
    )

    similar_tickets = [
        {"title": t.title, "description": t.description, "status": t.status}
        for t in similar
    ]

    suggestion = ai.suggest_resolution(ticket.title, ticket.description, similar_tickets)
    return {"data": suggestion}