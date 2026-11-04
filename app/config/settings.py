import os
from functools import lru_cache
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment configuration loaded from .env and environment variables."""

    # Meta Credentials
    META_APP_ID: str = ""
    META_APP_SECRET: str = ""
    VERIFY_TOKEN: str = "default_verify_token_replace_in_prod"
    PAGE_ACCESS_TOKEN: str = ""
    INSTAGRAM_ACCOUNT_ID: str = ""

    # Server Configuration
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    LOG_LEVEL: str = "INFO"
    DEBUG: bool = False

    @field_validator("DEBUG", mode="before")
    @classmethod
    def parse_debug(cls, v):
        if isinstance(v, bool):
            return v
        if isinstance(v, str):
            return v.strip().lower() in ("true", "1", "yes", "t", "on", "debug")
        return False
    ADMIN_API_KEY: Optional[str] = None

    # Database
    DATABASE_URL: str = "sqlite:///./instagram_automation.db"

    # Dynamic Config Path
    CONFIG_PATH: str = "./config.json"

    # Meta Graph API Base URL & Version
    GRAPH_API_VERSION: str = "v21.0"
    GRAPH_API_BASE_URL: str = "https://graph.facebook.com"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache()
def get_settings() -> Settings:
    """Return cached application settings instance."""
    return Settings()
