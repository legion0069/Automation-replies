from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class AutomationConfig(BaseModel):
    """Configuration model for automation rules stored in config.json."""

    enabled: bool = Field(
        default=True,
        description="Master switch to enable or disable auto-DM automation.",
    )
    match_mode: Literal["partial", "exact", "regex"] = Field(
        default="partial",
        description="Matching mode for keywords in comment text.",
    )
    case_sensitive: bool = Field(
        default=False,
        description="Whether keyword matching is case sensitive.",
    )
    keywords: List[str] = Field(
        default_factory=lambda: [
            "link",
            "guide",
            "pdf",
            "roadmap",
            "job",
            "placement",
            "send",
            "help",
            "info",
        ],
        description="List of keywords or regex patterns to monitor.",
    )
    reply_once_days: int = Field(
        default=7,
        ge=0,
        description="Cooldown period in days to avoid sending duplicate DMs to the same user.",
    )
    media_id_cooldown_only: bool = Field(
        default=False,
        description="If true, cooldown is scoped per media post rather than globally per user.",
    )
    message_template: str = Field(
        default="Hi {username} 👋\n\nThanks for commenting! Here are the requested resources:\n\n📌 Resources:\nhttps://example.com/resources\n\nBest of luck! ❤️",
        description="Message template sent to users. Supports placeholders like {username} and {keyword}.",
    )
    rate_limit_per_minute: int = Field(
        default=60,
        ge=1,
        le=300,
        description="Maximum outbound DM requests allowed per minute.",
    )
    max_retries: int = Field(
        default=3,
        ge=0,
        le=5,
        description="Maximum retries for transient Meta API failures.",
    )
    retry_backoff_factor: float = Field(
        default=2.0,
        ge=1.0,
        description="Exponential backoff multiplier for retries.",
    )


class AutomationConfigUpdate(BaseModel):
    """Partial update model for admin controls."""

    enabled: Optional[bool] = None
    match_mode: Optional[Literal["partial", "exact", "regex"]] = None
    case_sensitive: Optional[bool] = None
    keywords: Optional[List[str]] = None
    reply_once_days: Optional[int] = Field(default=None, ge=0)
    media_id_cooldown_only: Optional[bool] = None
    message_template: Optional[str] = None
    rate_limit_per_minute: Optional[int] = Field(default=None, ge=1, le=300)
    max_retries: Optional[int] = Field(default=None, ge=0, le=5)
    retry_backoff_factor: Optional[float] = Field(default=None, ge=1.0)

