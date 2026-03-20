"""抓取日志模型。"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow


class FetchLog(Base):
    """抓取日志。"""

    __tablename__ = "fetch_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    fetch_date: Mapped[date] = mapped_column(Date, nullable=False)
    job_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("job_runs.id"), nullable=True
    )
    total_accounts: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    fail_count: Mapped[int] = mapped_column(Integer, default=0)
    new_tweets: Mapped[int] = mapped_column(Integer, default=0)
    error_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
