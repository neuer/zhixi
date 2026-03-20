"""Dashboard 相关类型。"""

from datetime import date, datetime

from pydantic import BaseModel


class ServiceCostItem(BaseModel):
    """单个服务的成本摘要。"""

    service: str
    call_count: int
    total_tokens: int
    estimated_cost: float


class CostSummary(BaseModel):
    """成本汇总。"""

    total_cost: float
    by_service: list[ServiceCostItem]


class PipelineStatus(BaseModel):
    """今日 Pipeline 状态。"""

    status: str | None = None
    started_at: datetime | None = None
    error_message: str | None = None


class DigestStatus(BaseModel):
    """今日 Digest 状态。"""

    status: str | None = None
    digest_id: int | None = None
    item_count: int = 0
    version: int = 0


class DigestDayRecord(BaseModel):
    """近 7 天推送记录单条。"""

    date: date
    status: str
    item_count: int
    version: int


class AlertItem(BaseModel):
    """告警条目。"""

    job_type: str
    status: str
    error_message: str | None = None
    started_at: datetime


class DashboardOverviewResponse(BaseModel):
    """Dashboard 概览响应。"""

    pipeline_status: PipelineStatus
    digest_status: DigestStatus
    today_cost: CostSummary
    recent_7_days: list[DigestDayRecord]
    alerts: list[AlertItem]
