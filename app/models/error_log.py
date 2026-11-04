from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime
from app.database.session import Base


class ErrorLog(Base):
    """System and API error tracking."""

    __tablename__ = "error_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    error_type = Column(String(100), index=True, nullable=False)
    message = Column(Text, nullable=False)
    traceback = Column(Text, nullable=True)
    payload = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<ErrorLog(id={self.id}, error_type='{self.error_type}')>"
