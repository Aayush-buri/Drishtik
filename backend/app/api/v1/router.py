from fastapi import APIRouter
from pydantic import BaseModel
from app.core.config import settings

api_router = APIRouter()

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str

@api_router.get("/health", response_model=HealthResponse, tags=["health"])
def health_check():
    """
    Health check endpoint.
    """
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=settings.APP_VERSION
    )

# Note: Future modules (auth, cases, evidence, etc.) will be added here.
