from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import traceback
from . import models
from .database import engine
from .routers import tickets, users, auth, agent


app = FastAPI()

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