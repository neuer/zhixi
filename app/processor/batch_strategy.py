"""分批策略 — 按 author_weight 降序分批（US-020）。

当推文总 token 超过单批上限时，按账号权重降序排列后逐条累加，
超限时切分新批次。
"""

import logging

from app.models.account import TwitterAccount
from app.models.tweet import Tweet
from app.processor.analyzer_prompts import serialize_tweets_for_analysis
from app.processor.token_estimator import (
    _PROMPT_OVERHEAD_TOKENS,
    estimate_tokens_for_tweet,
)

logger = logging.getLogger(__name__)

DEFAULT_BATCH_TOKEN_LIMIT = 100_000


def split_into_batches(
    tweets: list[Tweet],
    accounts_map: dict[int, TwitterAccount],
    token_limit: int = DEFAULT_BATCH_TOKEN_LIMIT,
) -> list[list[Tweet]]:
    """按 author_weight 降序分批。

    算法：
    1. 按 author_weight 降序 + tweet_time 降序排序
    2. 序列化每条推文并估算 token
    3. 逐条累加，当前批 + 当前推文 + Prompt 开销 > limit 时切分新批次
    4. 单条超限时独立成批（不丢推文）

    Args:
        tweets: 当日待处理推文列表
        accounts_map: account_id → TwitterAccount 映射
        token_limit: 单批 token 上限（默认 100K）

    Returns:
        分批后的推文列表。空输入返回空列表。
    """
    if not tweets:
        return []

    # 1. 排序：weight 降序 → tweet_time 降序
    sorted_tweets = sorted(
        tweets,
        key=lambda t: (
            -(accounts_map[t.account_id].weight if t.account_id in accounts_map else 1.0),
            -(t.tweet_time.timestamp() if t.tweet_time else 0),
        ),
    )

    # 2. 序列化每条推文并估算 token
    serialized = serialize_tweets_for_analysis(sorted_tweets, accounts_map)
    tweet_tokens = [estimate_tokens_for_tweet(s) for s in serialized]

    # 3. 逐条累加分批
    batches: list[list[Tweet]] = []
    current_batch: list[Tweet] = []
    current_tokens = 0

    for i, tweet in enumerate(sorted_tweets):
        tokens = tweet_tokens[i]

        # 当前批加上这条推文是否超限
        if current_batch and (current_tokens + tokens + _PROMPT_OVERHEAD_TOKENS > token_limit):
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        current_batch.append(tweet)
        current_tokens += tokens

    if current_batch:
        batches.append(current_batch)

    if len(batches) > 1:
        logger.info(
            "推文分 %d 批处理（总 %d 条，limit=%d tokens）",
            len(batches),
            len(tweets),
            token_limit,
        )

    return batches
