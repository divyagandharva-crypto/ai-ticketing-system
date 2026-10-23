import threading
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from . import models
from .database import engine
from .config import settings
from . import jobs
from .routers import tickets, users, auth, agent


logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Run the background job worker inside the API process (fine for one small service).
    # For more throughput run `python worker.py` separately and set RUN_BACKGROUND_WORKER=false.
    stop = threading.Event()
    thread = None
    if settings.run_background_worker:
        thread = threading.Thread(target=jobs.run_worker, args=(stop,), daemon=True, name="job-worker")
        thread.start()
    yield
    stop.set()
    if thread:
        thread.join(timeout=5)


app = FastAPI(lifespan=lifespan)

models.Base.metadata.create_all(bind=engine)

app.include_router(tickets.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(agent.router)


@app.exception_handler(Exception)
async def debug_exception_handler(request: Request, exc: Exception):
    traceback.print_exc()
    return JSONResponse(status_code=500, content={"error": str(exc)})


@app.get("/")
def root():
    return {"message": "Ticketing System API"}