from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from .database import engine, get_db
from . import models, schemas, database, auth
from .routes import router as app_router
from .notifier import scheduler

# Create all database tables on startup
models.Base.metadata.create_all(bind=engine)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: initialize background scheduler if needed
    if not scheduler.running:
        try:
            scheduler.start()
        except Exception:
            pass
    yield
    # Shutdown: cleanly shutdown scheduler
    if scheduler.running:
        try:
            scheduler.shutdown(wait=False)
        except Exception:
            pass

app = FastAPI(
    title="CloudScope — Autonomous AWS Cloud Cost Cleanup Agent API",
    version="1.0.0",
    description="Real-time AWS Cloud Cost Janitor Agent with Human-in-the-Loop Approval Gate and Sandboxed Execution",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(app_router)

@app.post("/auth/aws-login")
def aws_login_alias(request: schemas.AWSConnectRequest, db = Depends(database.get_db)):
    from .routes import aws_login
    return aws_login(request, db)

@app.get("/auth/me", response_model=schemas.UserResponse)
def read_current_user_alias(current_user: models.User = Depends(auth.get_current_user)):
    return schemas.UserResponse(username=current_user.username, role=current_user.role)

@app.get("/")
def read_root():
    return {
        "status": "ok",
        "service": "CloudScope — Autonomous AWS Cloud Cost Cleanup Agent",
        "version": "1.0.0",
        "theme": "Cloud Cost Janitor",
        "hackathon": "Agents That Act — TrueFoundry × Polaris / HackCulture"
    }
