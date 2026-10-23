"""
Run the background worker as its own process (instead of inside the API):

    python worker.py

Set RUN_BACKGROUND_WORKER=false on the API when you do this, so only one place runs jobs
(running several workers is also safe, jobs are claimed with SKIP LOCKED).
"""
import logging
import signal
import threading

from app.jobs import run_worker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

stop = threading.Event()
signal.signal(signal.SIGINT, lambda *_: stop.set())
signal.signal(signal.SIGTERM, lambda *_: stop.set())

if __name__ == "__main__":
    run_worker(stop)
