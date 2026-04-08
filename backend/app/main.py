from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import engine
from . import models
from .routes import router as app_router
from .notifier import scheduler

# Create DB tables on startup
models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: start the background scheduler
    scheduler.start()
    yield
    # Shutdown: stop the scheduler cleanly
    if scheduler.running:
        scheduler.shutdown(wait=False)

app = FastAPI(title="AWS Startup Dashboard API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(app_router)

@app.get("/")
def read_root():
    return {"status": "ok", "message": "AWS Startup Dashboard API"}
