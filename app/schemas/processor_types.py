"""AI 加工相关类型。"""

from typing import Literal, TypedDict

from pydantic import BaseModel


class SingleTweetResult(TypedDict):
    """单条推文 AI 加工结果（R.1.3）。"""

    title: str
    translation: str
    comment: str


class PerspectiveItem(TypedDict):
    """话题观点条目。"""

    author: str
    handle: str
    viewpoint: str


class TopicProcessResult(TypedDict):
    """聚合话题 AI 加工结果（R.1.4）。"""

    title: str
    summary: str
    perspectives: list[PerspectiveItem]
    comment: str


class ThreadResult(TypedDict):
    """Thread AI 加工结果（R.1.5）。"""

    title: str
    translation: str
    comment: str


class TopicResult(BaseModel):
    """全局分析输出的话题。

    type 包含 "single"（不创建 Topic 记录）、"aggregated"、"thread"。
    DB 层 TopicType 枚举只有 aggregated/thread，single 不入 topics 表。
    """

    type: Literal["aggregated", "thread", "single"]
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

    @classmethod
    def from_parsed(cls, parsed: dict[str, object]) -> "AnalysisResult":
        """从 JSON 校验后的 dict 构建 AnalysisResult。

        统一 analyzer.py 和 batch_merger.py 中重复的构建逻辑。
        """
        raw_topics = parsed.get("topics", [])
        if not isinstance(raw_topics, list):
            raw_topics = []
        topics = [
            TopicResult(
                type=t["type"],
                topic_label=t.get("topic_label"),
                ai_importance_score=t["ai_importance_score"],
                tweet_ids=t["tweet_ids"],
                merged_text=t.get("merged_text"),
                reason=t.get("reason"),
            )
            for t in raw_topics
        ]
        raw_filtered = parsed.get("filtered_ids", [])
        if not isinstance(raw_filtered, list):
            raw_filtered = []
        raw_count = parsed.get("filtered_count")
        filtered_count = raw_count if isinstance(raw_count, int) else len(raw_filtered)
        return cls(
            filtered_ids=raw_filtered,
            filtered_count=filtered_count,
            topics=topics,
        )


class ProcessResult(BaseModel):
    """加工结果统计。"""

    processed_count: int
    filtered_count: int
    topic_count: int
    failed_count: int = 0
