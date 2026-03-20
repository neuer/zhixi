"""大V账号模型。"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow


class TwitterAccount(Base):
    """推特大V账号。"""

    __tablename__ = "twitter_accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    twitter_handle: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    twitter_user_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    bio: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    followers_count: Mapped[int] = mapped_column(Integer, default=0)
    weight: Mapped[float] = mapped_column(Float, default=1.0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_fetch_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
