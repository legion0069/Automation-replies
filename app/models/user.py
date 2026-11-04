from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import relationship
from app.database.session import Base


class User(Base):
    """Instagram User model."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    ig_user_id = Column(String(100), unique=True, index=True, nullable=False)
    username = Column(String(100), index=True, nullable=True)
    first_seen = Column(DateTime, default=datetime.utcnow, nullable=False)
    last_seen = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    comments = relationship("Comment", back_populates="user", cascade="all, delete-orphan")
    dm_logs = relationship("DMLog", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<User(id={self.id}, ig_user_id='{self.ig_user_id}', username='{self.username}')>"
