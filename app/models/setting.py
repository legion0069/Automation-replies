from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime
from app.database.session import Base


class Setting(Base):
    """Database key-value settings overrides."""

    __tablename__ = "settings"

    key = Column(String(100), primary_key=True, index=True)
    value = Column(Text, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Setting(key='{self.key}')>"

