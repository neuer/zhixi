"""API 调用成本日志模型。"""

from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, _utcnow
from app.schemas.enums import ServiceType


class ApiCostLog(Base):
    """API 调用成本记录。"""

    __tablename__ = "api_cost_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    call_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    service: Mapped[ServiceType] = mapped_column(String(20), nullable=False)
    call_type: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str | None] = mapped_column(String(200), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    estimated_cost: Mapped[float] = mapped_column(Float, default=0)
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    duration_ms: Mapped[int] = mapped_column(Integer, default=0)
    job_run_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("job_runs.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)
