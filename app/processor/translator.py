"""逐条/逐话题 AI 加工 — 第二步（US-021）。

三种加工模式：
- 单条推文 → R.1.3 Prompt → {title, translation, comment}
- 聚合话题 → R.1.4 Prompt → {title, summary, perspectives, comment}
- Thread   → R.1.5 Prompt → {title, translation, comment}
"""

import logging

from app.clients.claude_client import ClaudeClient
from app.processor.json_validator import validate_and_fix
from app.processor.translator_prompts import (
    SINGLE_TWEET_PROMPT,
    SINGLE_TWEET_SCHEMA,
    THREAD_PROMPT,
    THREAD_SCHEMA,
    TOPIC_PROMPT,
    TOPIC_SCHEMA,
)
from app.schemas.client_types import ClaudeResponse

logger = logging.getLogger(__name__)


async def process_single_tweet(
    claude_client: ClaudeClient,
    tweet_data: dict[str, object],
) -> tuple[dict[str, object], ClaudeResponse]:
    """单条推文加工（R.1.3）。

    Args:
        claude_client: Claude API 客户端
        tweet_data: 包含 author_name, author_handle, author_bio,
                    tweet_time, likes, retweets, replies, original_text

    Returns:
        ({title, translation, comment}, ClaudeResponse)
    """
    prompt = SINGLE_TWEET_PROMPT.format(**tweet_data)
    response = await claude_client.complete(prompt, max_tokens=2048)
    parsed = validate_and_fix(response.content, SINGLE_TWEET_SCHEMA)
    return parsed, response


async def process_aggregated_topic(
    claude_client: ClaudeClient,
    tweets_json: str,
) -> tuple[dict[str, object], ClaudeResponse]:
    """聚合话题加工（R.1.4）。

    Args:
        claude_client: Claude API 客户端
        tweets_json: R.1.4 格式序列化的推文 JSON 字符串

    Returns:
        ({title, summary, perspectives, comment}, ClaudeResponse)
    """
    prompt = TOPIC_PROMPT.format(tweets_json=tweets_json)
    response = await claude_client.complete(prompt, max_tokens=4096)
    parsed = validate_and_fix(response.content, TOPIC_SCHEMA)
    return parsed, response


async def process_thread(
    claude_client: ClaudeClient,
    thread_data: dict[str, object],
) -> tuple[dict[str, object], ClaudeResponse]:
    """Thread 加工（R.1.5）。

    Args:
        claude_client: Claude API 客户端
        thread_data: 包含 author_name, author_handle, author_bio,
                     thread_start_time, thread_end_time, tweet_count,
                     total_likes, total_retweets, total_replies, merged_text

    Returns:
        ({title, translation, comment}, ClaudeResponse)
    """
    prompt = THREAD_PROMPT.format(**thread_data)
    response = await claude_client.complete(prompt, max_tokens=4096)
    parsed = validate_and_fix(response.content, THREAD_SCHEMA)
    return parsed, response
