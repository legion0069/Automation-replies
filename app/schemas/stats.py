from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, ConfigDict


class DMLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    username: Optional[str] = None
    ig_user_id: Optional[str] = None
    comment_id: Optional[str] = None
    media_id: str
    message_sent: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    retry_count: int
    sent_at: datetime


class ErrorLogItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    error_type: str
    message: str
    created_at: datetime


class DashboardStats(BaseModel):
    total_comments: int
    matched_comments: int
    dms_sent: int
    dms_failed: int
    dms_skipped_duplicate: int
    dms_skipped_disabled: int
    success_rate_percent: float
    automation_enabled: bool
    active_keywords_count: int
    recent_logs: List[DMLogItem] = []
    recent_errors: List[ErrorLogItem] = []
