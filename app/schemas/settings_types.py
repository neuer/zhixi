"""系统设置相关类型。"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class SettingsResponse(BaseModel):
    """系统设置响应（不含密钥）。"""

    push_time: str
    push_days: list[int]
    top_n: int
    min_articles: int
    publish_mode: str
    enable_cover_generation: bool
    cover_generation_timeout: int
    notification_webhook_url: str
    db_size_mb: float
    last_backup_at: datetime | None = None


class SettingsUpdate(BaseModel):
    """系统设置更新请求（所有字段可选）。"""

    push_time: str | None = None
    push_days: list[int] | None = None
    top_n: int | None = None
    min_articles: int | None = None
    publish_mode: str | None = None
    enable_cover_generation: bool | None = None
    cover_generation_timeout: int | None = None
    notification_webhook_url: str | None = None

    @field_validator("push_days")
    @classmethod
    def push_days_not_empty(cls, v: list[int] | None) -> list[int] | None:
        """push_days 不允许为空数组。"""
        if v is not None and len(v) == 0:
            msg = "至少选择一个推送日"
            raise ValueError(msg)
        return v


class ApiStatusItem(BaseModel):
    """单个 API 状态。"""

    status: str
    latency_ms: int | None = None


class ApiStatusResponse(BaseModel):
    """API 状态检测响应。"""

    x_api: ApiStatusItem
    claude_api: ApiStatusItem
    gemini_api: ApiStatusItem
    wechat_api: ApiStatusItem
