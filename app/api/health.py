import time
from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.config.settings import Settings, get_settings
from app.database.session import get_db

router = APIRouter()
START_TIME = time.time()


@router.get("/health")
def health_check(
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    """Health check endpoint verifying application and database connectivity."""
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception as exc:
        db_status = f"unhealthy: {exc}"

    uptime_seconds = round(time.time() - START_TIME, 2)

    return {
        "status": "ok" if db_status == "healthy" else "degraded",
        "database": db_status,
        "uptime_seconds": uptime_seconds,
        "version": "1.0.0",
        "mode": "debug" if settings.DEBUG else "production",
    }
