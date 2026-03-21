"""数据采集相关类型。"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TweetType(StrEnum):
    """推文类型。"""

    ORIGINAL = "original"
    SELF_REPLY = "self_reply"
    QUOTE = "quote"
    RETWEET = "retweet"
    REPLY = "reply"


KEEP_TYPES = {TweetType.ORIGINAL, TweetType.SELF_REPLY, TweetType.QUOTE}


class ReferenceType(StrEnum):
    """X API 推文引用类型。已知值: retweeted, quoted, replied_to。"""

    RETWEETED = "retweeted"
    QUOTED = "quoted"
    REPLIED_TO = "replied_to"


class ReferencedTweet(BaseModel):
    """被引用推文信息。

    type 字段为 str 而非 ReferenceType 枚举，因为 X API 可能返回未知引用类型，
    分类器需要能容错处理（记录 warning 后兜底为 ORIGINAL）。
    """

    type: str
    id: str
    author_id: str


class PublicMetrics(BaseModel):
    """推文互动指标。"""

    like_count: int = Field(default=0, ge=0)
    retweet_count: int = Field(default=0, ge=0)
    reply_count: int = Field(default=0, ge=0)


class RawTweet(BaseModel):
    """从 X API 获取的原始推文。"""

    tweet_id: str
    author_id: str
    text: str
    created_at: datetime
    public_metrics: PublicMetrics
    referenced_tweets: list[ReferencedTweet] = []
    media_urls: list[str] = []
    tweet_url: str = ""


class FetchResult(BaseModel):
    """抓取结果统计。"""

    new_tweets_count: int = Field(ge=0)
    fail_count: int = Field(ge=0)
    total_accounts: int = Field(ge=0)
    skipped_count: int = Field(default=0, ge=0)
