from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CommentFrom(BaseModel):
    id: str
    username: Optional[str] = None


class CommentMedia(BaseModel):
    id: str
    media_product_type: Optional[str] = None


class CommentValue(BaseModel):
    id: str
    text: str
    from_: Optional[CommentFrom] = Field(default=None, alias="from")
    media: Optional[CommentMedia] = None
    parent_id: Optional[str] = None


class WebhookChange(BaseModel):
    field: str
    value: Dict[str, Any]


class WebhookEntry(BaseModel):
    id: str
    time: Optional[int] = None
    changes: Optional[List[WebhookChange]] = None
    messaging: Optional[List[Dict[str, Any]]] = None


class WebhookPayload(BaseModel):
    object: str
    entry: List[WebhookEntry] = []


class CommentEvent(BaseModel):
    """Normalized internal representation of an incoming comment event."""

    comment_id: str
    media_id: str
    ig_user_id: str
    username: Optional[str] = "there"
    text: str
    timestamp: Optional[int] = None
    raw_payload: Optional[Dict[str, Any]] = None
