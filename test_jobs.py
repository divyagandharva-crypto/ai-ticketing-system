"""
Tests for the background job queue (app/jobs.py). Run from the project folder:

    python test_jobs.py

Needs the local Postgres container running (it uses the dev database, creates a few
throwaway tickets, and deletes them at the end; jobs are removed by ON DELETE CASCADE).
Claude is never called: ai.analyze_ticket is replaced with fakes that fail on purpose.
"""
from datetime import datetime, timedelta, timezone

import anthropic
import httpx

from app import ai, jobs, models
from app.database import SessionLocal, engine

models.Base.metadata.create_all(bind=engine)   # creates the jobs table if it is new

created_ticket_ids = []


def new_ticket(db):
    t = models.Ticket(title="[job test] Can't log in", description="throwaway ticket for test_jobs.py")
    db.add(t)
    db.flush()
    created_ticket_ids.append(t.id)
    return t


def due_now(db, job_id):
    """Skip the backoff wait so the test does not sleep."""
    job = db.get(models.Job, job_id)
    job.run_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    db.commit()


def transient_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com/v1/messages"))


def test_backoff():
    assert jobs.backoff_seconds(1, jitter=False) == 5
    assert jobs.backoff_seconds(2, jitter=False) == 10
    assert jobs.backoff_seconds(3, jitter=False) == 20
    assert jobs.backoff_seconds(20, jitter=False) == 300          # capped
    for _ in range(50):
        d = jobs.backoff_seconds(3)
        assert 20 <= d <= 25                                       # 0-25% jitter
    print("ok  backoff grows, caps, and jitters")


def test_retry_then_succeed(db):
    calls = {"n": 0}

    def flaky(title, description):
        calls["n"] += 1
        if calls["n"] < 3:
            raise transient_error()
        return {"category": "bug", "urgency": "high", "summary": "ok"}

    ai.analyze_ticket = flaky
    job = jobs.enqueue(db, new_ticket(db).id)
    db.commit()
    jid = job.id

    assert jobs.process_one(db, jid)
    j = db.get(models.Job, jid)
    assert (j.status, j.attempts) == ("pending", 1) and j.last_error, "first failure should reschedule"
    assert j.run_at > datetime.now(timezone.utc), "retry must be delayed by backoff"
    assert not jobs.process_one(db, jid), "job is not due yet, so nothing should run"

    due_now(db, jid)
    assert jobs.process_one(db, jid)
    assert (db.get(models.Job, jid).status, db.get(models.Job, jid).attempts) == ("pending", 2)

    due_now(db, jid)
    assert jobs.process_one(db, jid)
    j = db.get(models.Job, jid)
    assert (j.status, j.attempts) == ("succeeded", 3)
    assert '"category": "bug"' in j.result and j.last_error is None
    print("ok  fails twice, retries with backoff, succeeds on attempt 3")


def test_gives_up_after_max_attempts(db):
    def always_down(title, description):
        raise transient_error()

    ai.analyze_ticket = always_down
    job = jobs.enqueue(db, new_ticket(db).id, max_attempts=2)
    db.commit()
    jid = job.id
    jobs.process_one(db, jid)
    due_now(db, jid)
    jobs.process_one(db, jid)
    j = db.get(models.Job, jid)
    assert (j.status, j.attempts) == ("failed", 2)
    print("ok  gives up after max_attempts and is marked failed")


def test_permanent_error_does_not_retry(db):
    def bad_request(title, description):
        raise jobs.PermanentJobError("input can never succeed")

    ai.analyze_ticket = bad_request
    job = jobs.enqueue(db, new_ticket(db).id)
    db.commit()
    jid = job.id
    jobs.process_one(db, jid)
    j = db.get(models.Job, jid)
    assert (j.status, j.attempts) == ("failed", 1) and "PermanentJobError" in j.last_error
    print("ok  permanent errors fail immediately (no pointless retries)")


def test_stale_running_job_is_reclaimed(db):
    job = jobs.enqueue(db, new_ticket(db).id)
    db.commit()
    jid = job.id
    j = db.get(models.Job, jid)
    j.status, j.attempts = "running", 1
    j.updated_at = datetime.now(timezone.utc) - timedelta(hours=1)   # a worker died an hour ago
    db.commit()
    assert jobs.reclaim_stale_jobs(db) >= 1
    assert db.get(models.Job, jid).status == "pending"
    print("ok  job abandoned by a crashed worker goes back to the queue")


if __name__ == "__main__":
    original = ai.analyze_ticket
    db = SessionLocal()
    try:
        test_backoff()
        test_retry_then_succeed(db)
        test_gives_up_after_max_attempts(db)
        test_permanent_error_does_not_retry(db)
        test_stale_running_job_is_reclaimed(db)
        print("\nALL JOB TESTS PASSED")
    finally:
        ai.analyze_ticket = original
        db.rollback()
        if created_ticket_ids:
            db.query(models.Ticket).filter(models.Ticket.id.in_(created_ticket_ids)).delete(synchronize_session=False)
            db.commit()
        db.close()
