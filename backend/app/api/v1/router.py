from fastapi import APIRouter
from app.api.v1.endpoints import auth, cases, members, evidence, devices, acquisitions, video_analysis, recovery, ai_analysis, blockchain, reports

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
api_router.include_router(evidence.router, prefix="/cases", tags=["Evidence"])
api_router.include_router(devices.router, prefix="/cases", tags=["Devices"])
api_router.include_router(acquisitions.router, prefix="/cases", tags=["Acquisition"])
api_router.include_router(video_analysis.router, prefix="/cases", tags=["Video Analysis"])
api_router.include_router(recovery.router, prefix="/cases", tags=["Forensic Recovery"])
api_router.include_router(ai_analysis.router, prefix="/cases", tags=["AI Video Analysis"])
api_router.include_router(blockchain.router, prefix="/cases", tags=["Blockchain & Chain of Custody"])
api_router.include_router(reports.router, prefix="/cases", tags=["Forensic Reports"])


