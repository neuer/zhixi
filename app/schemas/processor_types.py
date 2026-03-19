"""AI 加工相关类型。"""

from pydantic import BaseModel


class TopicResult(BaseModel):
    """全局分析输出的话题。"""

    type: str
    topic_label: str | None = None
    ai_importance_score: float
    tweet_ids: list[str]
    merged_text: str | None = None
    reason: str | None = None


class AnalysisResult(BaseModel):
    """全局分析输出。"""

    filtered_ids: list[str]
    filtered_count: int
    topics: list[TopicResult]


class ProcessResult(BaseModel):
    """加工结果统计。"""

    processed_count: int
    filtered_count: int
    topic_count: int
    failed_count: int = 0
