"""推文分类器测试（US-012 + US-047）。"""

from datetime import UTC, datetime

from app.fetcher.tweet_classifier import classify_tweet
from app.schemas.fetcher_types import PublicMetrics, RawTweet, ReferencedTweet, TweetType

# 固定时间戳，避免 pyright 类型警告
_DT = datetime(2026, 3, 18, 10, 0, 0, tzinfo=UTC)


def _make_tweet(
    tweet_id: str = "1",
    author_id: str = "user_a",
    text: str = "测试推文",
    referenced_tweets: list[ReferencedTweet] | None = None,
) -> RawTweet:
    """构造测试用 RawTweet。"""
    return RawTweet(
        tweet_id=tweet_id,
        author_id=author_id,
        text=text,
        created_at=_DT,
        public_metrics=PublicMetrics(),
        referenced_tweets=referenced_tweets or [],
    )


# ---------------------------------------------------------------------------
# ORIGINAL — 无 referenced_tweets
# ---------------------------------------------------------------------------


def test_classify_original_empty_referenced():
    """空 referenced_tweets 列表 → ORIGINAL。"""
    tweet = _make_tweet(referenced_tweets=[])
    assert classify_tweet(tweet) == TweetType.ORIGINAL


def test_classify_original_default_no_referenced():
    """不传 referenced_tweets（默认空列表）→ ORIGINAL。"""
    tweet = RawTweet(
        tweet_id="2",
        author_id="user_b",
        text="另一条原创推文",
        created_at=_DT,
        public_metrics=PublicMetrics(),
    )
    assert classify_tweet(tweet) == TweetType.ORIGINAL


# ---------------------------------------------------------------------------
# RETWEET — referenced_tweets[0].type == "retweeted"
# ---------------------------------------------------------------------------


def test_classify_retweet_basic():
    """referenced_tweets[0].type == 'retweeted' → RETWEET。"""
    ref = ReferencedTweet(type="retweeted", id="100", author_id="user_other")
    tweet = _make_tweet(referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.RETWEET


def test_classify_retweet_author_is_self():
    """即使 ref.author_id == tweet.author_id，只要 type 是 retweeted → RETWEET。"""
    ref = ReferencedTweet(type="retweeted", id="101", author_id="user_a")
    tweet = _make_tweet(author_id="user_a", referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.RETWEET


# ---------------------------------------------------------------------------
# QUOTE — referenced_tweets[0].type == "quoted"
# ---------------------------------------------------------------------------


def test_classify_quote_basic():
    """referenced_tweets[0].type == 'quoted' → QUOTE。"""
    ref = ReferencedTweet(type="quoted", id="200", author_id="user_other")
    tweet = _make_tweet(referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.QUOTE


def test_classify_quote_self_quoting():
    """引用自己的推文，只要 type 是 quoted → QUOTE。"""
    ref = ReferencedTweet(type="quoted", id="201", author_id="user_a")
    tweet = _make_tweet(author_id="user_a", referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.QUOTE


# ---------------------------------------------------------------------------
# SELF_REPLY — replied_to 且 ref.author_id == tweet.author_id
# ---------------------------------------------------------------------------


def test_classify_self_reply_basic():
    """replied_to 且 ref.author_id == tweet.author_id → SELF_REPLY。"""
    ref = ReferencedTweet(type="replied_to", id="300", author_id="user_a")
    tweet = _make_tweet(author_id="user_a", referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.SELF_REPLY


def test_classify_self_reply_different_tweet_id():
    """不同 tweet_id，但 author_id 相同 → SELF_REPLY。"""
    ref = ReferencedTweet(type="replied_to", id="999", author_id="user_z")
    tweet = _make_tweet(tweet_id="888", author_id="user_z", referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.SELF_REPLY


# ---------------------------------------------------------------------------
# REPLY — replied_to 且 ref.author_id != tweet.author_id
# ---------------------------------------------------------------------------


def test_classify_reply_basic():
    """replied_to 且 ref.author_id != tweet.author_id → REPLY。"""
    ref = ReferencedTweet(type="replied_to", id="400", author_id="user_other")
    tweet = _make_tweet(author_id="user_a", referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.REPLY


def test_classify_reply_different_ids():
    """不同用户 id，replied_to → REPLY。"""
    ref = ReferencedTweet(type="replied_to", id="401", author_id="user_b")
    tweet = _make_tweet(tweet_id="500", author_id="user_c", referenced_tweets=[ref])
    assert classify_tweet(tweet) == TweetType.REPLY


# ---------------------------------------------------------------------------
# 边界：多个 referenced_tweets，只看第一个
# ---------------------------------------------------------------------------


def test_classify_uses_first_referenced_tweet_only():
    """多个 referenced_tweets 时，只使用第一个确定分类。"""
    ref0 = ReferencedTweet(type="retweeted", id="600", author_id="user_other")
    ref1 = ReferencedTweet(type="quoted", id="601", author_id="user_other")
    tweet = _make_tweet(referenced_tweets=[ref0, ref1])
    # 第一个是 retweeted，应为 RETWEET
    assert classify_tweet(tweet) == TweetType.RETWEET


def test_classify_reply_with_extra_refs():
    """replied_to 在第一位，后面有其他引用，应按第一个判为 REPLY。"""
    ref0 = ReferencedTweet(type="replied_to", id="700", author_id="user_other")
    ref1 = ReferencedTweet(type="quoted", id="701", author_id="user_a")
    tweet = _make_tweet(author_id="user_a", referenced_tweets=[ref0, ref1])
    assert classify_tweet(tweet) == TweetType.REPLY
