from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.session import Base


class Comment(Base):
    """Instagram Comment model."""

    __tablename__ = "comments"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    comment_id = Column(String(100), unique=True, index=True, nullable=False)
    media_id = Column(String(100), index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    text = Column(Text, nullable=False)
    matched_keyword = Column(String(100), nullable=True)
    is_processed = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    user = relationship("User", back_populates="comments")
    dm_log = relationship("DMLog", back_populates="comment", uselist=False)

    def __repr__(self) -> str:
        return f"<Comment(id={self.id}, comment_id='{self.comment_id}', user_id={self.user_id})>"
