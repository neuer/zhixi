"""日报模型。"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow
from app.schemas.enums import DigestStatus, PublishMode


class DailyDigest(Base):
    """每日日报（支持多版本）。"""

    __tablename__ = "daily_digest"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_date: Mapped[date] = mapped_column(Date, nullable=False)
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(default=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_markdown: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_html: Mapped[str | None] = mapped_column(Text, nullable=True)
    cover_image_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    item_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20), default=DigestStatus.DRAFT)
    publish_mode: Mapped[str] = mapped_column(String(20), default=PublishMode.MANUAL)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    job_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("job_runs.id"), nullable=True
    )
    preview_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    preview_expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow, onupdate=_utcnow)
