from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base


class DMLog(Base):
    """Direct Message Delivery Log."""

    __tablename__ = "dm_logs"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    comment_id = Column(String(100), ForeignKey("comments.comment_id", ondelete="SET NULL"), nullable=True, index=True)
    media_id = Column(String(100), index=True, nullable=False)
    message_sent = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, index=True)  # SUCCESS, FAILED, SKIPPED_DUPLICATE, SKIPPED_DISABLED
    api_response = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    user = relationship("User", back_populates="dm_logs")
    comment = relationship("Comment", back_populates="dm_log")

    def __repr__(self) -> str:
        return f"<DMLog(id={self.id}, user_id={self.user_id}, status='{self.status}')>"

