from fastapi import FastAPI
from . import models
from .database import engine
from .routers import tickets, users, auth, agent


app = FastAPI()

models.Base.metadata.create_all(bind=engine)

app.include_router(tickets.router)
app.include_router(users.router)
app.include_router(auth.router)
app.include_router(agent.router)

@app.get("/")
def root():
    return {"message": "Ticketing System API"}