"""大V账号相关 Pydantic 类型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AccountCreate(BaseModel):
    """创建账号请求。

    当 display_name 非空时跳过 X API，走手动模式。
    """

    twitter_handle: str
    weight: float = Field(default=1.0, ge=0.1, le=5.0)
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None


class AccountUpdate(BaseModel):
    """更新账号请求 — 部分更新。"""

    weight: float | None = Field(default=None, ge=0.1, le=5.0)
    is_active: bool | None = None


class AccountResponse(BaseModel):
    """账号响应模型。"""

    id: int
    twitter_handle: str
    twitter_user_id: str | None
    display_name: str
    avatar_url: str | None
    bio: str | None
    followers_count: int
    weight: float
    is_active: bool
    last_fetch_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AccountListResponse(BaseModel):
    """分页账号列表响应。"""

    items: list[AccountResponse]
    total: int
    page: int
    page_size: int
