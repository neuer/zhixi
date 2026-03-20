"""话题模型 — 聚合话题和 Thread。"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow


class Topic(Base):
    """聚合话题 / Thread。"""

    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_date: Mapped[date] = mapped_column(Date, nullable=False)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    topic_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    perspectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    heat_score: Mapped[float] = mapped_column(Float, default=0)
    ai_importance_score: Mapped[float] = mapped_column(Float, default=0)
    merge_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    tweet_count: Mapped[int] = mapped_column(Integer, default=0)
    version: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
