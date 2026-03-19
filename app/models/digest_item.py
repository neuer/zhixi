"""日报条目模型 — 快照式存储。"""

from datetime import UTC, datetime

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class DigestItem(Base):
    """日报条目（编辑只改 snapshot_* 字段）。"""

    __tablename__ = "digest_items"
    __table_args__ = (
        UniqueConstraint("digest_id", "item_type", "item_ref_id", name="uq_digest_item_ref"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    digest_id: Mapped[int] = mapped_column(Integer, ForeignKey("daily_digest.id"), nullable=False)
    item_type: Mapped[str] = mapped_column(String(20), nullable=False)
    item_ref_id: Mapped[int] = mapped_column(Integer, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_pinned: Mapped[bool] = mapped_column(default=False)
    is_excluded: Mapped[bool] = mapped_column(default=False)
    snapshot_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snapshot_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_translation: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_perspectives: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_heat_score: Mapped[float] = mapped_column(Float, default=0)
    snapshot_author_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    snapshot_author_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    snapshot_tweet_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    snapshot_source_tweets: Mapped[str | None] = mapped_column(Text, nullable=True)
    snapshot_topic_type: Mapped[str | None] = mapped_column(String(20), nullable=True)
    snapshot_tweet_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
