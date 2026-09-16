"""
One-off script to backfill embeddings for tickets created before the
`embedding` column existed (or that otherwise have a NULL embedding).

Run from the project root, with the venv activated:
    python backfill_embeddings.py
"""

from app.database import SessionLocal
from app.models import Ticket
from app.embeddings import embed_text


def backfill():
    db = SessionLocal()
    try:
        tickets = db.query(Ticket).filter(Ticket.embedding.is_(None)).all()

        if not tickets:
            print("No tickets need backfilling — every ticket already has an embedding.")
            return

        print(f"Found {len(tickets)} ticket(s) missing an embedding. Backfilling...")

        for ticket in tickets:
            text = f"{ticket.title} {ticket.description}"
            ticket.embedding = embed_text(text)
            print(f"  - Embedded ticket {ticket.id}: {ticket.title!r}")

        db.commit()
        print(f"Done. Backfilled {len(tickets)} ticket(s).")

    finally:
        db.close()


if __name__ == "__main__":
    backfill()