"""推文分类器（US-012 实现）。"""

import logging

from app.schemas.fetcher_types import RawTweet, TweetType

logger = logging.getLogger(__name__)


def classify_tweet(raw_tweet: RawTweet) -> TweetType:
    """根据 referenced_tweets 字段对推文进行分类。

    分类规则：
    - 无 referenced_tweets                            → ORIGINAL
    - referenced_tweets[0].type == "retweeted"       → RETWEET
    - referenced_tweets[0].type == "quoted"          → QUOTE
    - referenced_tweets[0].type == "replied_to" 且
      ref.author_id == raw_tweet.author_id           → SELF_REPLY
    - referenced_tweets[0].type == "replied_to" 且
      ref.author_id != raw_tweet.author_id           → REPLY

    注意：此函数只负责分类，过滤逻辑（KEEP_TYPES）由 US-013 实现。
    """
    if not raw_tweet.referenced_tweets:
        return TweetType.ORIGINAL

    ref = raw_tweet.referenced_tweets[0]

    if ref.type == "retweeted":
        return TweetType.RETWEET

    if ref.type == "quoted":
        return TweetType.QUOTE

    if ref.type == "replied_to":
        if ref.author_id == raw_tweet.author_id:
            return TweetType.SELF_REPLY
        return TweetType.REPLY

    # 未知引用类型按原创处理
    logger.warning("未知推文引用类型: %s，按原创处理", ref.type)
    return TweetType.ORIGINAL
