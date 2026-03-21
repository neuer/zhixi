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
from app.schemas.processor_types import (
    PerspectiveItem,
    SingleTweetResult,
    ThreadResult,
    TopicProcessResult,
)

logger = logging.getLogger(__name__)


async def process_single_tweet(
    claude_client: ClaudeClient,
    tweet_data: dict[str, object],
) -> tuple[SingleTweetResult, ClaudeResponse]:
    """单条推文加工（R.1.3）。

    Args:
        claude_client: Claude API 客户端
        tweet_data: 包含 author_name, author_handle, author_bio,
                    tweet_time, likes, retweets, replies, original_text

    Returns:
        (SingleTweetResult, ClaudeResponse)
    """
    prompt = SINGLE_TWEET_PROMPT.format(**tweet_data)
    response = await claude_client.complete(prompt, max_tokens=2048)
    parsed = validate_and_fix(response.content, SINGLE_TWEET_SCHEMA)
    return SingleTweetResult(
        title=str(parsed["title"]),
        translation=str(parsed["translation"]),
        comment=str(parsed["comment"]),
    ), response


async def process_aggregated_topic(
    claude_client: ClaudeClient,
    tweets_json: str,
) -> tuple[TopicProcessResult, ClaudeResponse]:
    """聚合话题加工（R.1.4）。

    Args:
        claude_client: Claude API 客户端
        tweets_json: R.1.4 格式序列化的推文 JSON 字符串

    Returns:
        (TopicProcessResult, ClaudeResponse)
    """
    prompt = TOPIC_PROMPT.format(tweets_json=tweets_json)
    response = await claude_client.complete(prompt, max_tokens=4096)
    parsed = validate_and_fix(response.content, TOPIC_SCHEMA)
    raw_perspectives = parsed.get("perspectives", [])
    perspectives: list[PerspectiveItem] = (
        raw_perspectives if isinstance(raw_perspectives, list) else []
    )
    return TopicProcessResult(
        title=str(parsed["title"]),
        summary=str(parsed["summary"]),
        perspectives=perspectives,
        comment=str(parsed["comment"]),
    ), response


async def process_thread(
    claude_client: ClaudeClient,
    thread_data: dict[str, object],
) -> tuple[ThreadResult, ClaudeResponse]:
    """Thread 加工（R.1.5）。

    Args:
        claude_client: Claude API 客户端
        thread_data: 包含 author_name, author_handle, author_bio,
                     thread_start_time, thread_end_time, tweet_count,
                     total_likes, total_retweets, total_replies, merged_text

    Returns:
        (ThreadResult, ClaudeResponse)
    """
    prompt = THREAD_PROMPT.format(**thread_data)
    response = await claude_client.complete(prompt, max_tokens=4096)
    parsed = validate_and_fix(response.content, THREAD_SCHEMA)
    return ThreadResult(
        title=str(parsed["title"]),
        translation=str(parsed["translation"]),
        comment=str(parsed["comment"]),
    ), response
