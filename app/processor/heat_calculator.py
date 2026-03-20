"""热度分计算 — 纯函数，无 DB 依赖（US-022）。

公式：
  engagement = likes*1 + retweets*3 + replies*2
  base_score = engagement * author_weight * exp(-0.05 * hours)
  heat_score = normalized_base * 0.7 + ai_importance * 0.3
"""

import math
from datetime import date, datetime
from zoneinfo import ZoneInfo

BEIJING_TZ = ZoneInfo("Asia/Shanghai")
UTC = ZoneInfo("UTC")


def get_reference_time(digest_date: date) -> datetime:
    """获取热度计算参考时间点：digest_date 当日北京时间 06:00 → UTC。"""
    bj_ref = datetime(
        digest_date.year, digest_date.month, digest_date.day, 6, 0, 0, tzinfo=BEIJING_TZ
    )
    return bj_ref.astimezone(UTC)


def calculate_hours_since_post(tweet_time: datetime, reference_time: datetime) -> float:
    """计算推文发布到参考时间点的小时数。"""
    delta = reference_time - tweet_time
    return delta.total_seconds() / 3600


def calculate_base_score(
    likes: int,
    retweets: int,
    replies: int,
    author_weight: float,
    hours: float,
) -> float:
    """计算原始热度分。

    base_score = (likes*1 + retweets*3 + replies*2) * author_weight * exp(-0.05 * hours)
    """
    engagement = likes * 1 + retweets * 3 + replies * 2
    return engagement * author_weight * math.exp(-0.05 * hours)


def normalize_scores(scores: list[float]) -> list[float]:
    """min-max 归一化到 0-100。

    全部相同或仅 1 条 → 全部返回 50。空列表 → 空列表。
    """
    if not scores:
        return []

    min_score = min(scores)
    max_score = max(scores)

    if min_score == max_score:
        return [50.0] * len(scores)

    score_range = max_score - min_score
    return [(s - min_score) / score_range * 100 for s in scores]


def calculate_heat_score(normalized_base: float, ai_importance: float) -> float:
    """最终热度分 = normalized_base * 0.7 + ai_importance * 0.3，保留 2 位小数。"""
    return round(normalized_base * 0.7 + ai_importance * 0.3, 2)
