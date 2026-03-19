"""推文模型。"""

from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Tweet(Base):
    """推文。"""

    __tablename__ = "tweets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    tweet_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("twitter_accounts.id"))
    digest_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    media_urls: Mapped[str | None] = mapped_column(Text, nullable=True)
    translated_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    base_heat_score: Mapped[float] = mapped_column(Float, default=0)
    ai_importance_score: Mapped[float] = mapped_column(Float, default=0)
    heat_score: Mapped[float] = mapped_column(Float, default=0, index=True)
    likes: Mapped[int] = mapped_column(Integer, default=0)
    retweets: Mapped[int] = mapped_column(Integer, default=0)
    replies: Mapped[int] = mapped_column(Integer, default=0)
    tweet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    tweet_time: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    quoted_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_quote_tweet: Mapped[bool] = mapped_column(Boolean, default=False)
    is_self_thread_reply: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_relevant: Mapped[bool] = mapped_column(Boolean, default=True)
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    topic_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("topics.id"), nullable=True, index=True
    )
    source: Mapped[str] = mapped_column(String(20), default="auto")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
