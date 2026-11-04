import logging
from typing import Generator, Optional
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from app.config.settings import Settings, get_settings
from app.database.session import get_db
from app.services.comment_processor import CommentProcessor
from app.services.meta_client import MetaClient
from app.services.keyword_matcher import KeywordMatcher
from app.services.duplicate_checker import DuplicateChecker

logger = logging.getLogger(__name__)


def verify_admin_key(
    x_api_key: Optional[str] = Header(None, alias="X-API-Key"),
    settings: Settings = Depends(get_settings),
) -> bool:
    """Verify admin API key if configured in environment."""
    if not settings.ADMIN_API_KEY:
        # If no admin key is configured, allow requests (e.g. in local/demo mode)
        return True

    if not x_api_key or x_api_key != settings.ADMIN_API_KEY:
        logger.warning("Unauthorized admin access attempt with key: %s", x_api_key)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing X-API-Key header",
        )
    return True


def get_meta_client(settings: Settings = Depends(get_settings)) -> MetaClient:
    """Dependency that provides MetaClient."""
    return MetaClient(settings=settings)


def get_comment_processor(
    meta_client: MetaClient = Depends(get_meta_client),
) -> CommentProcessor:
    """Dependency that provides CommentProcessor."""
    return CommentProcessor(
        meta_client=meta_client,
        keyword_matcher=KeywordMatcher(),
        duplicate_checker=DuplicateChecker(),
    )
