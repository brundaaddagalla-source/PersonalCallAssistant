import sys
from fastapi import APIRouter
from app.config import settings
from app.state.session_store import store

router = APIRouter(tags=["health"])

@router.get("/health")
@router.get("/api/health")
def health():
    active_count = sum(1 for s in store.items.values() if s.get("status") == "active")
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.app_env,
        "python_version": sys.version.split()[0],
        "stt_provider": settings.stt_provider,
        "tts_provider": settings.tts_provider,
        "decision_mode": "http" if settings.decision_api_url else "mock",
        "active_sessions": active_count,
        "total_sessions": len(store.items)
    }

