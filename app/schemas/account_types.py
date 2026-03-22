"""大V账号相关 Pydantic 类型。"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class AccountCreate(BaseModel):
    """创建账号请求。"""

    twitter_handle: str
    weight: float = Field(default=1.0, ge=0.1, le=5.0)
    display_name: str | None = None
    bio: str | None = None
    avatar_url: str | None = None

    @field_validator("twitter_handle")
    @classmethod
    def validate_handle(cls, v: str) -> str:
        """校验 twitter_handle：不含 @、strip 后非空、长度合理。"""
        v = v.strip().lstrip("@")
        if not v:
            msg = "twitter_handle 不能为空"
            raise ValueError(msg)
        if len(v) > 50:
            msg = "twitter_handle 长度不能超过 50"
            raise ValueError(msg)
        return v


class AccountUpdate(BaseModel):
    """更新账号请求 — 部分更新。"""

    weight: float | None = Field(default=None, ge=0.1, le=5.0)
    is_active: bool | None = None


class AccountResponse(BaseModel):
    """账号响应模型。

    当前阶段 AccountResponse 直接复用 DB Model 全部字段，
    因为 Account 表字段较少且无敏感信息。
    若后续字段增多或需要区分列表/详情场景，再拆分为
    AccountBriefResponse / AccountDetailResponse。
    """

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
