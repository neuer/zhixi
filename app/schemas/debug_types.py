"""调试接口相关类型。"""

from typing import Literal

from pydantic import BaseModel, Field

from app.clients.x_client import XUserProfile
from app.schemas.fetcher_types import RawTweet


class DebugXPingResponse(BaseModel):
    """X API 连通性检测响应。"""

    status: Literal["ok", "error", "unconfigured"]
    latency_ms: int | None = None
    raw_response: dict[str, object] | None = None


class DebugXUserResponse(BaseModel):
    """X API 用户查询响应。"""

    user: XUserProfile | None = None
    raw_response: dict[str, object]
    latency_ms: int


class DebugXTweetsRequest(BaseModel):
    """推文抓取请求。"""

    handle: str = Field(min_length=1, max_length=100, description="Twitter 用户名（不含 @）")
    hours_back: int = Field(default=24, ge=1, le=168, description="向前查找的小时数")


class DebugXTweetsResponse(BaseModel):
    """推文抓取响应。"""

    tweets: list[RawTweet]
    count: int
    raw_response: dict[str, object]
    latency_ms: int


class DebugXTweetResponse(BaseModel):
    """单条推文查询响应。"""

    tweet: RawTweet | None = None
    raw_response: dict[str, object]
    latency_ms: int
