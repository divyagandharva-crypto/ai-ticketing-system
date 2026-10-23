from .database import Base
from sqlalchemy import Column, Integer, String, TIMESTAMP, ForeignKey, Text, Index, func
from sqlalchemy.sql.expression import text
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, nullable=False)
    title = Column(String, nullable=False)
    description = Column(String, nullable=False)
    status = Column(String, nullable=False, server_default='open')
    priority = Column(String, nullable=False, server_default='medium')
    access_level = Column(String, nullable=False, server_default='standard')   # NEW
    created_by = Column(Integer, ForeignKey("users.id"))
    assigned_to = Column(Integer, ForeignKey("users.id"))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    embedding = Column(Vector(384))

    creator = relationship("User", foreign_keys=[created_by])
    assignee = relationship("User", foreign_keys=[assigned_to])
    comments = relationship("Comment", back_populates="ticket")


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, nullable=False)
    email = Column(String, nullable=False, unique=True)
    password = Column(String, nullable=False)
    clearance_level = Column(String, nullable=False, server_default='standard')   # NEW
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))


class Comment(Base):
    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(String, nullable=False)
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))

    ticket = relationship("Ticket", back_populates="comments")
    author = relationship("User")

class Job(Base):
    """Background job queue row. See app/jobs.py for how it is used."""
    __tablename__ = "jobs"
    __table_args__ = (Index("ix_jobs_status_run_at", "status", "run_at"),)

    id = Column(Integer, primary_key=True, nullable=False)
    ticket_id = Column(Integer, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False, index=True)
    job_type = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pending", server_default="pending")   # pending | running | succeeded | failed
    attempts = Column(Integer, nullable=False, default=0, server_default="0")
    max_attempts = Column(Integer, nullable=False, default=5, server_default="5")
    last_error = Column(Text)
    result = Column(Text)
    run_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text('now()'), onupdate=func.now())
