"""共享枚举类型 — 跨模型与 Schema 使用的 StrEnum 定义。"""

from enum import StrEnum


class DigestStatus(StrEnum):
    """日报状态。"""

    DRAFT = "draft"
    PUBLISHED = "published"
    FAILED = "failed"


class JobType(StrEnum):
    """任务类型。"""

    PIPELINE = "pipeline"
    FETCH = "fetch"
    PROCESS = "process"
    DIGEST = "digest"
    BACKUP = "backup"
    CLEANUP = "cleanup"


class JobStatus(StrEnum):
    """任务状态。"""

    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class TriggerSource(StrEnum):
    """任务触发来源。"""

    CRON = "cron"
    MANUAL = "manual"
    REGENERATE = "regenerate"


class TopicType(StrEnum):
    """话题类型。"""

    AGGREGATED = "aggregated"
    THREAD = "thread"


class ItemType(StrEnum):
    """日报条目类型。"""

    TWEET = "tweet"
    TOPIC = "topic"


class TweetSource(StrEnum):
    """推文来源。"""

    AUTO = "auto"
    MANUAL = "manual"


class ServiceType(StrEnum):
    """外部服务类型。"""

    X = "x"
    CLAUDE = "claude"
    GEMINI = "gemini"
    WECHAT = "wechat"


class CallType(StrEnum):
    """API 调用类型 — 标识各环节的成本归属。"""

    FETCH_TWEETS = "fetch_tweets"
    FETCH_SINGLE_TWEET = "fetch_single_tweet"
    SINGLE_PROCESS = "single_process"
    GLOBAL_ANALYSIS = "global_analysis"
    DEDUP_ANALYSIS = "dedup_analysis"
    TOPIC_PROCESS = "topic_process"
    THREAD_PROCESS = "thread_process"
    COVER = "cover"
    SUMMARY = "summary"


class PublishMode(StrEnum):
    """发布模式。"""

    API = "api"
    MANUAL = "manual"


class SecretKey(StrEnum):
    """密钥配置键名。"""

    X_API_BEARER_TOKEN = "x_api_bearer_token"
    ANTHROPIC_API_KEY = "anthropic_api_key"
    GEMINI_API_KEY = "gemini_api_key"
    WECHAT_APP_ID = "wechat_app_id"
    WECHAT_APP_SECRET = "wechat_app_secret"
