from fastapi import FastAPI
from app.config import settings
from app.api.health import router as health_router
from app.api.sessions import router as sessions_router
from app.api.voice import router as voice_router
from app.api.demo import router as demo_router

app = FastAPI(
    title=settings.app_name,
    description="Member 4 Voice Engine & Integration Testing for Personal Call Assistant",
    version="0.1.0"
)
app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(voice_router)
app.include_router(demo_router)


@app.get("/")
def root():
    return {"service": settings.app_name, "docs": "/docs",
            "note": "Live telephony streaming is provider-specific and not configured by default."}
