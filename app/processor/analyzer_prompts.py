"""全局分析 Prompt 模板与 JSON Schema（R.1.2）。"""

from datetime import datetime

from app.models.account import TwitterAccount
from app.models.tweet import Tweet

# ──────────────────────────────────────────────────
# R.1.2 全局分析 Prompt
# ──────────────────────────────────────────────────

GLOBAL_ANALYSIS_PROMPT = """\
你是 智曦的内容总编辑，负责从大量推文中筛选和组织今日AI热点。

## 你的任务

### 任务1：内容过滤
- 剔除与AI/科技领域无关的推文（如个人生活、政治观点、体育等）
- 对 quote tweet：如果作者有实质性新增观点则保留，纯转发无观点则剔除

### 任务2：Thread识别
- 检查是否有同一作者的连续自回复构成Thread
- 如果Thread内容完整且有价值，将其合并为一条，拼接文本

### 任务3：话题聚合
- 判断是否有多条推文在讨论同一事件或话题
- 将讨论同一话题的推文归为一组

### 任务4：热度评估
- 对每条/每个话题，给出 AI 重要性修正分（0-100）
- 评估维度：内容突破性、行业影响力、讨论集中度

## 输入推文列表

{tweets_json}

## 输出格式

请严格按以下JSON格式输出，不要添加其他内容：
{{
  "filtered_ids": ["被过滤的推文id列表"],
  "filtered_count": 3,
  "topics": [
    {{
      "type": "aggregated",
      "topic_label": "话题标签",
      "ai_importance_score": 85,
      "tweet_ids": ["id1", "id2"],
      "reason": "聚合原因"
    }},
    {{
      "type": "single",
      "ai_importance_score": 70,
      "tweet_ids": ["id3"],
      "reason": null
    }},
    {{
      "type": "thread",
      "ai_importance_score": 75,
      "tweet_ids": ["id4", "id5"],
      "merged_text": "合并后的Thread全文",
      "reason": "Thread合并原因"
    }}
  ]
}}"""


# ──────────────────────────────────────────────────
# JSON Schema（用于 validate_and_fix）
# ──────────────────────────────────────────────────

GLOBAL_ANALYSIS_SCHEMA: dict[str, object] = {
    "required": ["filtered_ids", "topics"],
    "properties": {
        "filtered_ids": {"type": "array", "items": {"type": "string"}},
        "filtered_count": {"type": "integer"},
        "topics": {
            "type": "array",
            "items": {
                "required": ["type", "ai_importance_score", "tweet_ids"],
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["aggregated", "single", "thread"],
                    },
                    "topic_label": {"type": "string"},
                    "ai_importance_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 100,
                    },
                    "tweet_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "merged_text": {"type": "string"},
                    "reason": {"type": "string"},
                },
            },
        },
    },
}


# ──────────────────────────────────────────────────
# 推文序列化（R.1.1b 格式）
# ──────────────────────────────────────────────────


def serialize_tweets_for_analysis(
    tweets: list[Tweet],
    accounts_map: dict[int, TwitterAccount],
) -> list[dict[str, object]]:
    """将推文 ORM 列表序列化为 R.1.1b 全局分析输入格式。

    按 tweet_time 降序排列（最新在前）。
    """
    sorted_tweets = sorted(tweets, key=lambda t: t.tweet_time, reverse=True)

    result: list[dict[str, object]] = []
    for tweet in sorted_tweets:
        account = accounts_map.get(tweet.account_id)
        result.append(
            {
                "id": tweet.tweet_id,
                "author": account.display_name if account else "",
                "handle": account.twitter_handle if account else "",
                "bio": (account.bio or "") if account else "",
                "text": tweet.original_text,
                "likes": tweet.likes,
                "retweets": tweet.retweets,
                "replies": tweet.replies,
                "time": _format_time(tweet.tweet_time),
                "url": tweet.tweet_url or "",
                "is_quote": tweet.is_quote_tweet,
                "quoted_text": tweet.quoted_text,
                "is_self_reply": tweet.is_self_thread_reply,
                "reply_to_id": None,
            }
        )
    return result


def _format_time(dt: datetime) -> str:
    """格式化为 ISO 8601 UTC 字符串。"""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
