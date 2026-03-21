"""认证相关 Pydantic 类型 — 设置向导与登录。"""

from datetime import datetime

from pydantic import BaseModel, Field


class SetupStatusResponse(BaseModel):
    """设置状态响应。"""

    need_setup: bool


class SetupInitRequest(BaseModel):
    """首次设置请求。"""

    password: str = Field(max_length=128)
    notification_webhook_url: str | None = None


class LoginRequest(BaseModel):
    """管理员登录请求。"""

    username: str
    password: str = Field(max_length=128)


class LoginResponse(BaseModel):
    """登录成功响应。"""

    token: str
    expires_at: datetime
