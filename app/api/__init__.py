"""API package."""
from fastapi import APIRouter
from app.api import health, webhook, admin, dashboard

api_router = APIRouter()
api_router.include_router(health.router, tags=["Health"])
api_router.include_router(webhook.router, tags=["Webhook"])
api_router.include_router(admin.router, prefix="/api/v1/settings", tags=["Admin Settings"])
api_router.include_router(dashboard.router, tags=["Dashboard & Stats"])

__all__ = ["api_router"]

