"""系统设置相关类型。"""

import re
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


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
    top_n: int | None = Field(default=None, ge=1, le=50)
    min_articles: int | None = Field(default=None, ge=0, le=50)
    publish_mode: Literal["manual", "api"] | None = None
    enable_cover_generation: bool | None = None
    cover_generation_timeout: int | None = Field(default=None, ge=5, le=300)
    notification_webhook_url: str | None = None

    @field_validator("push_time")
    @classmethod
    def push_time_format(cls, v: str | None) -> str | None:
        """push_time 必须为 HH:MM 格式。"""
        if v is not None and not re.match(r"^\d{2}:\d{2}$", v):
            msg = "时间格式必须为 HH:MM"
            raise ValueError(msg)
        return v

    @field_validator("push_days")
    @classmethod
    def push_days_valid(cls, v: list[int] | None) -> list[int] | None:
        """push_days 不允许为空数组，且每个值必须在 1-7 之间。"""
        if v is not None:
            if len(v) == 0:
                msg = "至少选择一个推送日"
                raise ValueError(msg)
            if any(d < 1 or d > 7 for d in v):
                msg = "推送日必须在 1-7 之间"
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
