from contextlib import asynccontextmanager
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, RedirectResponse

from app.api import api_router
from app.config.settings import get_settings
from app.database.session import init_db
from app.utils.logger import setup_logging

logger = logging.getLogger(__name__)
settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle event handler for application startup and shutdown."""
    # 1. Initialize rotating file and console logging
    setup_logging(log_level=settings.LOG_LEVEL)
    logger.info("Starting Instagram Comment Auto-DM Service...")

    # 2. Verify or initialize database schema
    init_db()
    logger.info("Database initialized successfully.")

    yield

    logger.info("Shutting down Instagram Comment Auto-DM Service...")


def create_app() -> FastAPI:
    """Application factory for FastAPI service."""
    app = FastAPI(
        title="Instagram Comment Reply & Auto DM Automation",
        description="Official Meta Graph API compliant automation for sending direct messages to comment authors.",
        version="1.0.0",
        lifespan=lifespan,
    )

    # CORS configuration
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Global Exception Handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error("Unhandled exception at %s: %s", request.url.path, exc, exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"detail": "An internal server error occurred.", "type": exc.__class__.__name__},
        )

    # Root redirect to dashboard
    @app.get("/", include_in_schema=False)
    def root():
        return RedirectResponse(url="/dashboard")

    # Include API Routers
    app.include_router(api_router)

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

