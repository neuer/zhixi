"""任务运行记录模型。"""

from datetime import date, datetime

from sqlalchemy import Date, DateTime, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow
from app.schemas.enums import JobStatus, JobType, TriggerSource


class JobRun(Base):
    """任务运行记录。"""

    __tablename__ = "job_runs"
    __table_args__ = (Index("ix_job_run_type_date_status", "job_type", "digest_date", "status"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_type: Mapped[JobType] = mapped_column(String(50), nullable=False)
    digest_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    trigger_source: Mapped[TriggerSource] = mapped_column(String(20), nullable=False)
    status: Mapped[JobStatus] = mapped_column(String(20), default=JobStatus.RUNNING)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
