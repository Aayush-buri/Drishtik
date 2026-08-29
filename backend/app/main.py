from fastapi import FastAPI
from app.core.config import settings
from app.core.logging import setup_logging
from app.api.v1.router import api_router

# Setup application logging
setup_logging()

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Execute startup and shutdown events."""
    # Place future startup logic here (e.g., connect to DB, init cache)
    yield
    # Place future shutdown logic here (e.g., close DB connections)

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Backend API for Drishtik Forensic Analysis Platform",
    lifespan=lifespan
)

@app.get("/", tags=["root"])
def read_root():
    """Root endpoint."""
    return {
        "service": "Drishtik Backend",
        "status": "running"
    }

# Include API v1 router
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
