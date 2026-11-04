from datetime import datetime
import json
import logging
import traceback
from typing import Optional
from sqlalchemy.orm import Session

from app.config.dynamic_config import get_dynamic_config
from app.models.comment import Comment
from app.models.dm_log import DMLog
from app.models.error_log import ErrorLog
from app.models.user import User
from app.schemas.webhook import CommentEvent
from app.services.duplicate_checker import DuplicateChecker
from app.services.keyword_matcher import KeywordMatcher
from app.services.meta_client import MetaClient

logger = logging.getLogger(__name__)


class CommentProcessor:
    """Orchestrates parsing, database persistence, keyword matching, deduplication, and sending DMs."""

    def __init__(
        self,
        meta_client: Optional[MetaClient] = None,
        keyword_matcher: Optional[KeywordMatcher] = None,
        duplicate_checker: Optional[DuplicateChecker] = None,
    ):
        self.meta_client = meta_client or MetaClient()
        self.keyword_matcher = keyword_matcher or KeywordMatcher()
        self.duplicate_checker = duplicate_checker or DuplicateChecker()

    async def process_comment(self, event: CommentEvent, db: Session) -> Optional[DMLog]:
        """
        Full workflow for an incoming Instagram comment event.
        Returns the created DMLog or None if already processed.
        """
        config = get_dynamic_config().get_config()
        logger.info(
            "Processing comment id=%s from user @%s: '%s'",
            event.comment_id,
            event.username,
            event.text,
        )

        try:
            # 1. Upsert User
            user = db.query(User).filter(User.ig_user_id == event.ig_user_id).first()
            if not user:
                user = User(
                    ig_user_id=event.ig_user_id,
                    username=event.username,
                    first_seen=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                )
                db.add(user)
                db.flush()
            else:
                user.last_seen = datetime.utcnow()
                if event.username and event.username != "there":
                    user.username = event.username
                db.flush()

            # 2. Check for duplicate comment event (Idempotency)
            existing_comment = db.query(Comment).filter(Comment.comment_id == event.comment_id).first()
            if existing_comment and existing_comment.is_processed:
                logger.info("Comment id=%s has already been processed. Skipping.", event.comment_id)
                return None

            # 3. Match Keyword
            is_matched, matched_keyword = self.keyword_matcher.match(event.text, config)

            # 4. Save Comment Record
            if not existing_comment:
                comment_record = Comment(
                    comment_id=event.comment_id,
                    media_id=event.media_id,
                    user_id=user.id,
                    text=event.text,
                    matched_keyword=matched_keyword,
                    is_processed=True,
                    created_at=datetime.utcnow(),
                )
                db.add(comment_record)
            else:
                comment_record = existing_comment
                comment_record.matched_keyword = matched_keyword
                comment_record.is_processed = True
            db.flush()

            # 5. Check if automation is enabled
            if not config.enabled:
                logger.info("Automation is disabled. Skipping DM for comment id=%s", event.comment_id)
                dm_log = DMLog(
                    user_id=user.id,
                    comment_id=event.comment_id,
                    media_id=event.media_id,
                    message_sent=None,
                    status="SKIPPED_DISABLED",
                    error_message="Automation globally disabled in configuration.",
                    sent_at=datetime.utcnow(),
                )
                db.add(dm_log)
                db.commit()
                return dm_log

            # 6. Check if keyword matched
            if not is_matched:
                logger.info("No configured keyword matched for comment id=%s: '%s'", event.comment_id, event.text)
                db.commit()
                return None

            logger.info("Matched keyword '%s' for comment id=%s", matched_keyword, event.comment_id)

            # 7. Check Duplicate / Cooldown Policy
            is_duplicate = self.duplicate_checker.is_duplicate(
                db=db,
                user_id=user.id,
                media_id=event.media_id,
                cooldown_days=config.reply_once_days,
                media_specific=config.media_id_cooldown_only,
            )

            if is_duplicate:
                logger.info(
                    "User @%s (id=%s) already received DM within %d-day cooldown. Skipping.",
                    user.username,
                    user.ig_user_id,
                    config.reply_once_days,
                )
                dm_log = DMLog(
                    user_id=user.id,
                    comment_id=event.comment_id,
                    media_id=event.media_id,
                    message_sent=None,
                    status="SKIPPED_DUPLICATE",
                    error_message=f"Duplicate skipped by {config.reply_once_days}-day cooldown policy.",
                    sent_at=datetime.utcnow(),
                )
                db.add(dm_log)
                db.commit()
                return dm_log

            # 8. Render Message Template
            display_name = user.username if (user.username and user.username != "there") else "friend"
            formatted_message = config.message_template.format(
                username=display_name,
                keyword=matched_keyword or "info",
                media_id=event.media_id,
            )

            # 9. Send Direct Message via Meta Graph API
            dm_response = await self.meta_client.send_dm(
                comment_id=event.comment_id,
                recipient_user_id=event.ig_user_id,
                message_text=formatted_message,
                max_retries=config.max_retries,
                backoff_factor=config.retry_backoff_factor,
            )

            # 10. Record Success in DMLog
            dm_log = DMLog(
                user_id=user.id,
                comment_id=event.comment_id,
                media_id=event.media_id,
                message_sent=formatted_message,
                status="SUCCESS",
                api_response=json.dumps(dm_response),
                sent_at=datetime.utcnow(),
            )
            db.add(dm_log)
            db.commit()
            logger.info("Successfully sent DM to @%s for comment id=%s", user.username, event.comment_id)
            return dm_log

        except Exception as exc:
            db.rollback()
            error_trace = traceback.format_exc()
            logger.error("Error processing comment id=%s: %s\n%s", event.comment_id, exc, error_trace)

            # Persist failure and error log
            try:
                # Find user if created
                u = db.query(User).filter(User.ig_user_id == event.ig_user_id).first()
                user_id_val = u.id if u else 0

                failed_dm_log = DMLog(
                    user_id=user_id_val,
                    comment_id=event.comment_id,
                    media_id=event.media_id,
                    message_sent=None,
                    status="FAILED",
                    error_message=str(exc),
                    sent_at=datetime.utcnow(),
                )
                if user_id_val > 0:
                    db.add(failed_dm_log)

                error_log = ErrorLog(
                    error_type=exc.__class__.__name__,
                    message=str(exc),
                    traceback=error_trace,
                    payload=json.dumps(event.model_dump()),
                    created_at=datetime.utcnow(),
                )
                db.add(error_log)
                db.commit()
                return failed_dm_log
            except Exception as inner_exc:
                db.rollback()
                logger.error("Failed to persist error log: %s", inner_exc)
                return None

