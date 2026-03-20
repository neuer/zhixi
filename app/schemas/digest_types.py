"""日报相关类型。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class ReorderInput(BaseModel):
    """排序请求条目。"""

    id: int = Field(gt=0)
    display_order: int = Field(ge=0)
    is_pinned: bool = False


class MessageResponse(BaseModel):
    """通用消息响应。"""

    message: str


class DigestItemResponse(BaseModel):
    """日报条目响应。"""

    id: int
    item_type: str
    item_ref_id: int
    display_order: int
    is_pinned: bool
    is_excluded: bool
    snapshot_title: str | None
    snapshot_translation: str | None
    snapshot_summary: str | None
    snapshot_comment: str | None
    snapshot_perspectives: str | None
    snapshot_heat_score: float
    snapshot_author_name: str | None
    snapshot_author_handle: str | None
    snapshot_tweet_url: str | None
    snapshot_source_tweets: str | None
    snapshot_topic_type: str | None
    snapshot_tweet_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DigestBriefResponse(BaseModel):
    """日报摘要响应。"""

    id: int
    digest_date: date
    version: int
    status: str
    summary: str | None
    item_count: int
    content_markdown: str | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TodayResponse(BaseModel):
    """今日内容列表响应。"""

    digest: DigestBriefResponse | None
    items: list[DigestItemResponse]
    low_content_warning: bool
