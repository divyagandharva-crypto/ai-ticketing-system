from sqlalchemy.orm import joinedload

def get_ticket_with_comments(db: Session, ticket_id: int):
    ticket = (
        db.query(Ticket)
        .options(joinedload(Ticket.comments))
        .filter(Ticket.id == ticket_id)
        .first()
    )
    return ticket