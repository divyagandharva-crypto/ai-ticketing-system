"""
Background jobs: a small Postgres-backed work queue with retries.

Why this exists
---------------
Calling an LLM inside a request is slow and can fail (rate limits, timeouts,
network blips). Instead, create_ticket writes a row to the `jobs` table in the
SAME transaction as the ticket, and returns immediately. A worker picks the job
up later, calls Claude, and records the result. If the call fails with a
transient error, the job is rescheduled with exponential backoff and jitter.

Design notes (the interview-ready parts)
----------------------------------------
* Transactional enqueue: the ticket and its job commit together, so a ticket can
  never exist without its job and a job can never point at a rolled-back ticket.
* Safe with several workers: jobs are claimed with SELECT ... FOR UPDATE SKIP
  LOCKED, so two workers never take the same job.
* Retry policy: transient errors (rate limit, connection, 5xx, bad JSON from the
  model) retry with backoff up to max_attempts. Permanent errors (bad API key,
  invalid request, ticket deleted) fail immediately, because retrying cannot help.
* Crash recovery: a job stuck in "running" (worker died mid-call) is returned to
  the queue by reclaim_stale_jobs.
* At-least-once delivery: a job can run twice in rare crash cases. analyze_ticket
  is read-only against the ticket, so repeating it is harmless (idempotent).
* Upgrade path: for higher volume, swap this module for Celery + Redis. The
  enqueue/handler shape stays the same.
"""

import json
import logging
import random
import threading
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Optional

import anthropic
from sqlalchemy import func
from sqlalchemy.orm import Session

from . import ai, models
from .database import SessionLocal

logger = logging.getLogger("jobs")

DEFAULT_MAX_ATTEMPTS = 5
# The Anthropic SDK's own request timeout is long, so a "running" job is only
# treated as abandoned after this much silence.
STALE_AFTER = timedelta(minutes=15)


class PermanentJobError(Exception):
    """Raised by a handler when retrying cannot help (bad input, missing row)."""


PERMANENT_ERRORS = (
    PermanentJobError,
    anthropic.AuthenticationError,
    anthropic.PermissionDeniedError,
    anthropic.BadRequestError,
    anthropic.NotFoundError,
)


def backoff_seconds(attempts: int, base: float = 5.0, cap: float = 300.0, jitter: bool = True) -> float:
    """Delay before the next try: base * 2^(attempts-1), capped, plus up to 25% jitter."""
    delay = min(cap, base * (2 ** max(0, attempts - 1)))
    if jitter:
        delay += random.uniform(0, delay * 0.25)
    return delay


# ---------------------------------------------------------------- handlers

def _handle_analyze_ticket(db: Session, job: models.Job) -> dict:
    ticket = db.get(models.Ticket, job.ticket_id)
    if ticket is None:
        raise PermanentJobError(f"ticket {job.ticket_id} no longer exists")
    return ai.analyze_ticket(ticket.title, ticket.description)


HANDLERS: Dict[str, Callable[[Session, models.Job], dict]] = {
    "analyze_ticket": _handle_analyze_ticket,
}


# ------------------------------------------------------------------- queue

def enqueue(db: Session, ticket_id: int, job_type: str = "analyze_ticket",
            max_attempts: int = DEFAULT_MAX_ATTEMPTS) -> models.Job:
    """Add a job to the session. The CALLER commits, so the job shares the caller's transaction."""
    job = models.Job(ticket_id=ticket_id, job_type=job_type, max_attempts=max_attempts)
    db.add(job)
    return job


def claim_next_job(db: Session, job_id: Optional[int] = None) -> Optional[models.Job]:
    """Atomically take the next due job and mark it running (attempts + 1)."""
    query = db.query(models.Job).filter(
        models.Job.status == "pending",
        models.Job.run_at <= func.now(),
    )
    if job_id is not None:
        query = query.filter(models.Job.id == job_id)
    job = query.order_by(models.Job.run_at, models.Job.id).with_for_update(skip_locked=True).first()
    if job is None:
        db.rollback()
        return None
    job.status = "running"
    job.attempts += 1
    db.commit()
    return job


def _record_failure(db: Session, job_id: int, exc: Exception) -> None:
    job = db.get(models.Job, job_id)
    job.last_error = f"{type(exc).__name__}: {exc}"[:1000]
    if isinstance(exc, PERMANENT_ERRORS) or job.attempts >= job.max_attempts:
        job.status = "failed"
        logger.error("job %s failed for good after %s attempt(s): %s", job_id, job.attempts, job.last_error)
    else:
        delay = backoff_seconds(job.attempts)
        job.status = "pending"
        job.run_at = datetime.now(timezone.utc) + timedelta(seconds=delay)
        logger.warning("job %s attempt %s/%s failed (%s); retrying in %.0fs",
                       job_id, job.attempts, job.max_attempts, job.last_error, delay)
    db.commit()


def process_one(db: Session, job_id: Optional[int] = None) -> bool:
    """Run one due job. Returns True if a job was processed, False if the queue was empty."""
    job = claim_next_job(db, job_id)
    if job is None:
        return False
    jid, job_type = job.id, job.job_type
    handler = HANDLERS.get(job_type)
    try:
        if handler is None:
            raise PermanentJobError(f"no handler for job type {job_type!r}")
        result = handler(db, job)
    except Exception as exc:  # noqa: BLE001 - every failure must be recorded, not crash the worker
        db.rollback()
        _record_failure(db, jid, exc)
        return True
    job = db.get(models.Job, jid)
    job.status = "succeeded"
    job.result = json.dumps(result)
    job.last_error = None
    db.commit()
    return True


def reclaim_stale_jobs(db: Session, stale_after: timedelta = STALE_AFTER) -> int:
    """Return jobs abandoned in 'running' (worker crashed) to the queue, or fail them if out of attempts."""
    cutoff = datetime.now(timezone.utc) - stale_after
    stale = (
        db.query(models.Job)
        .filter(models.Job.status == "running", models.Job.updated_at < cutoff)
        .with_for_update(skip_locked=True)
        .all()
    )
    for job in stale:
        job.last_error = "worker stopped before finishing this job"
        job.status = "failed" if job.attempts >= job.max_attempts else "pending"
        job.run_at = datetime.now(timezone.utc)
    db.commit()
    return len(stale)


def run_worker(stop_event: threading.Event, poll_interval: float = 2.0) -> None:
    """Poll the queue until stop_event is set. Safe to run in a thread or as its own process."""
    logger.info("background worker started")
    while not stop_event.is_set():
        did_work = False
        db = SessionLocal()
        try:
            reclaim_stale_jobs(db)
            did_work = process_one(db)
        except Exception:  # noqa: BLE001 - e.g. database briefly unreachable; keep the loop alive
            logger.exception("worker loop error")
            db.rollback()
        finally:
            db.close()
        if not did_work:
            stop_event.wait(poll_interval)
    logger.info("background worker stopped")
