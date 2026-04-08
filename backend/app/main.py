from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from .database import engine, Base, SessionLocal
from . import models, auth
from .routes import router as app_router

# Create DB tables
models.Base.metadata.create_all(bind=engine)

app = FastAPI(title="AWS Startup Dashboard API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

from .notifier import scheduler
@app.on_event("startup")
def start_scheduler():
    scheduler.start()

app.include_router(app_router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AWS Startup Dashboard API"}
