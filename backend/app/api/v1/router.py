from fastapi import APIRouter
from app.api.v1.endpoints import auth, cases, members

api_router = APIRouter()

@api_router.get("/health", tags=["health"])
def health_check():
    from app.core.config import settings
    return {
        "service": settings.APP_NAME,
        "status": "ok",
        "version": settings.APP_VERSION
    }

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(cases.router, prefix="/cases", tags=["Cases"])
api_router.include_router(members.router, prefix="/cases", tags=["Collaborators"])
