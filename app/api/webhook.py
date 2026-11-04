import json
import logging
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from app.config.settings import Settings, get_settings
from app.database.session import SessionLocal
from app.schemas.webhook import CommentEvent
from app.services.comment_processor import CommentProcessor
from app.services.meta_client import MetaClient
from app.utils.security import verify_meta_signature

logger = logging.getLogger(__name__)

router = APIRouter()


async def process_comment_background(event_dict: dict) -> None:
    """Asynchronous background worker executing comment workflow with dedicated DB session."""
    db: Session = SessionLocal()
    try:
        event = CommentEvent(**event_dict)
        processor = CommentProcessor()
        await processor.process_comment(event, db)
    except Exception as exc:
        logger.error("Error in background comment processing: %s", exc, exc_info=True)
    finally:
        db.close()


@router.get("/webhook")
async def verify_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    settings: Settings = Depends(get_settings),
):
    """
    Official Meta Webhook Verification endpoint.
    Meta sends a GET request with hub.mode, hub.challenge, and hub.verify_token.
    """
    logger.info("Webhook verification request received. Mode: %s", hub_mode)

    if hub_mode == "subscribe" and hub_verify_token == settings.VERIFY_TOKEN:
        logger.info("Webhook verification succeeded.")
        # Meta requires returning the challenge as plain text with 200 OK
        return Response(content=hub_challenge or "", media_type="text/plain")

    logger.warning(
        "Webhook verification failed. Token mismatch or invalid mode: mode=%s, token=%s",
        hub_mode,
        hub_verify_token,
    )
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="Verification token mismatch or invalid mode",
    )


@router.post("/webhook")
async def receive_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_hub_signature_256: Optional[str] = Header(None, alias="X-Hub-Signature-256"),
    settings: Settings = Depends(get_settings),
):
    """
    Official Meta Webhook Event receiver endpoint.
    Verifies payload signature and dispatches events to background processing.
    Returns 200 OK immediately (< 2 seconds required by Meta).
    """
    body_bytes = await request.body()

    # Enforce signature verification if META_APP_SECRET is set
    if settings.META_APP_SECRET:
        is_valid = verify_meta_signature(
            payload_body=body_bytes,
            signature_header=x_hub_signature_256,
            app_secret=settings.META_APP_SECRET,
        )
        if not is_valid:
            logger.warning("Rejected webhook event due to invalid HMAC signature.")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid webhook signature",
            )

    try:
        payload = json.loads(body_bytes.decode("utf-8"))
    except Exception as exc:
        logger.error("Failed to parse JSON webhook payload: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Malformed JSON body",
        )

    # Parse comments from payload
    meta_client = MetaClient(settings=settings)
    events = meta_client.parse_comment(payload)

    if not events:
        logger.info("Webhook received, but contained no relevant comment events.")
        return {"status": "ok", "message": "No actionable comment events"}

    logger.info("Webhook received with %d actionable comment event(s).", len(events))

    # Queue background task for each comment event
    for event in events:
        background_tasks.add_task(process_comment_background, event.model_dump())

    return {"status": "ok", "enqueued_events": len(events)}
