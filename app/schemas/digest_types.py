"""日报相关类型。"""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.enums import DigestStatus, ItemType, TopicType


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
    item_type: ItemType
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
    snapshot_topic_type: TopicType | None
    snapshot_tweet_time: datetime | None

    model_config = ConfigDict(from_attributes=True)


class DigestBriefResponse(BaseModel):
    """日报摘要响应。"""

    id: int
    digest_date: date
    version: int
    status: DigestStatus
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


class EditItemRequest(BaseModel):
    """编辑单条内容请求（所有字段可选，partial update）。"""

    title: str | None = Field(default=None, max_length=200)
    translation: str | None = Field(default=None, max_length=5000)
    summary: str | None = Field(default=None, max_length=2000)
    perspectives: str | None = Field(default=None, max_length=5000)
    comment: str | None = Field(default=None, max_length=2000)


class EditSummaryRequest(BaseModel):
    """编辑导读摘要请求。"""

    summary: str


class ReorderRequest(BaseModel):
    """调整排序请求。"""

    items: list[ReorderInput]


class MarkdownResponse(BaseModel):
    """Markdown 内容响应（供一键复制）。"""

    content_markdown: str


# ── US-038: 预览功能 ──


class PreviewResponse(BaseModel):
    """预览响应（digest + items + Markdown）。"""

    digest: DigestBriefResponse
    items: list[DigestItemResponse]
    content_markdown: str


# ── US-009: 预览签名链接 ──


class PreviewLinkResponse(BaseModel):
    """预览签名链接响应。"""

    token: str
    expires_at: datetime


# ── US-042: 推送历史 ──


class HistoryListItem(BaseModel):
    """历史列表条目（每日期一条）。"""

    id: int
    digest_date: date
    version: int
    status: DigestStatus
    summary: str | None
    item_count: int
    published_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class HistoryListResponse(BaseModel):
    """历史列表分页响应。"""

    items: list[HistoryListItem]
    total: int
    page: int
    page_size: int


class HistoryDetailResponse(BaseModel):
    """历史详情响应（完整信息 + items 快照）。"""

    digest: DigestBriefResponse
    items: list[DigestItemResponse]


# ── US-016: 手动补录推文 ──


class AddTweetRequest(BaseModel):
    """手动补录推文请求。"""

    tweet_url: str = Field(min_length=1, max_length=500)


class AddTweetResponse(BaseModel):
    """手动补录推文响应。"""

    message: str
    item: DigestItemResponse
