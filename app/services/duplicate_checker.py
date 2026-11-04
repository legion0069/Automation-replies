from datetime import datetime, timedelta
import logging
from typing import Optional
from sqlalchemy.orm import Session
from app.models.dm_log import DMLog
from app.models.user import User

logger = logging.getLogger(__name__)


class DuplicateChecker:
    """Enforces spam prevention and duplicate DM cooldown policies."""

    @staticmethod
    def is_duplicate(
        db: Session,
        user_id: int,
        media_id: str,
        cooldown_days: int = 7,
        media_specific: bool = False,
    ) -> bool:
        """
        Check if user has already received a successful DM within the cooldown window.
        Returns True if a message was already sent (i.e. is duplicate), False otherwise.
        """
        if cooldown_days <= 0:
            return False

        cutoff_date = datetime.utcnow() - timedelta(days=cooldown_days)

        query = db.query(DMLog).filter(
            DMLog.user_id == user_id,
            DMLog.status == "SUCCESS",
            DMLog.sent_at >= cutoff_date,
        )

        if media_specific and media_id:
            query = query.filter(DMLog.media_id == media_id)

        existing_entry = query.first()
        if existing_entry:
            logger.info(
                "Duplicate DM detected for user_id=%s, media_id=%s. Last sent at %s (cooldown: %d days).",
                user_id,
                media_id,
                existing_entry.sent_at,
                cooldown_days,
            )
            return True

        return False

