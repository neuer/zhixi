"""batch_strategy 单元测试（US-020）。"""

from datetime import UTC, datetime

from app.models.account import TwitterAccount
from app.models.tweet import Tweet
from app.processor.batch_strategy import split_into_batches


def _make_account(aid: int, weight: float = 1.0) -> TwitterAccount:
    """构造测试用 TwitterAccount（不入库）。"""
    return TwitterAccount(
        id=aid,
        twitter_handle=f"user{aid}",
        display_name=f"User {aid}",
        bio="Test bio",
        weight=weight,
        is_active=True,
    )


def _make_tweet(
    tweet_id: str,
    account_id: int,
    text: str = "Test tweet",
    tweet_time: datetime | None = None,
) -> Tweet:
    """构造测试用 Tweet（不入库）。"""
    return Tweet(
        tweet_id=tweet_id,
        account_id=account_id,
        original_text=text,
        tweet_time=tweet_time or datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        likes=100,
        retweets=20,
        replies=10,
        is_quote_tweet=False,
        is_self_thread_reply=False,
        quoted_text=None,
        tweet_url=f"https://x.com/test/status/{tweet_id}",
        digest_date=datetime(2026, 3, 19).date(),
    )


class TestSplitIntoBatches:
    """分批策略测试。"""

    def test_empty_tweets(self) -> None:
        """空列表 → 空列表。"""
        result = split_into_batches([], {})
        assert result == []

    def test_under_limit_single_batch(self) -> None:
        """总 token < limit → 返回单批。"""
        account = _make_account(1)
        tweets = [_make_tweet("t1", 1)]
        accounts_map = {1: account}

        batches = split_into_batches(tweets, accounts_map, token_limit=100_000)
        assert len(batches) == 1
        assert len(batches[0]) == 1

    def test_over_limit_splits(self) -> None:
        """用极小 token_limit 强制分批。"""
        account = _make_account(1)
        tweets = [
            _make_tweet("t1", 1, text="First tweet about AI"),
            _make_tweet("t2", 1, text="Second tweet about ML"),
        ]
        accounts_map = {1: account}

        # 用极小 limit 强制每条独立成批
        batches = split_into_batches(tweets, accounts_map, token_limit=50)
        assert len(batches) >= 2

    def test_sorted_by_weight_desc(self) -> None:
        """高 weight 账号的推文在前面批次。"""
        high = _make_account(1, weight=3.0)
        low = _make_account(2, weight=1.0)
        tweets = [
            _make_tweet("t_low", 2, text="Low weight tweet"),
            _make_tweet("t_high", 1, text="High weight tweet"),
        ]
        accounts_map = {1: high, 2: low}

        # 用极小 limit 分批
        batches = split_into_batches(tweets, accounts_map, token_limit=50)
        assert len(batches) >= 2
        # 第一批应包含高 weight 推文
        first_batch_ids = {t.tweet_id for t in batches[0]}
        assert "t_high" in first_batch_ids

    def test_same_weight_sorted_by_time_desc(self) -> None:
        """同 weight 按 tweet_time 降序（最新在前）。"""
        account = _make_account(1, weight=1.0)
        old = _make_tweet(
            "t_old",
            1,
            text="Old tweet",
            tweet_time=datetime(2026, 3, 19, 8, 0, 0, tzinfo=UTC),
        )
        new = _make_tweet(
            "t_new",
            1,
            text="New tweet",
            tweet_time=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        )
        accounts_map = {1: account}

        # 用极小 limit 分批
        batches = split_into_batches([old, new], accounts_map, token_limit=50)
        assert len(batches) >= 2
        # 第一批应包含最新的推文
        assert batches[0][0].tweet_id == "t_new"

    def test_single_huge_tweet(self) -> None:
        """单条推文超 limit → 独立成批（不丢推文）。"""
        account = _make_account(1)
        huge = _make_tweet("t_huge", 1, text="x" * 1000)
        small = _make_tweet("t_small", 1, text="hi")
        accounts_map = {1: account}

        # limit 很小但能放下 small
        batches = split_into_batches([huge, small], accounts_map, token_limit=50)
        # huge 独立成批，small 独立成批
        assert len(batches) >= 2
        # 所有推文都在结果中
        all_ids = {t.tweet_id for batch in batches for t in batch}
        assert all_ids == {"t_huge", "t_small"}

    def test_preserves_all_tweets(self) -> None:
        """分批后所有推文都被保留。"""
        account = _make_account(1)
        tweets = [_make_tweet(f"t{i}", 1, text=f"Tweet number {i}") for i in range(10)]
        accounts_map = {1: account}

        batches = split_into_batches(tweets, accounts_map, token_limit=200)
        all_ids = {t.tweet_id for batch in batches for t in batch}
        expected_ids = {f"t{i}" for i in range(10)}
        assert all_ids == expected_ids

    def test_missing_account_uses_default_weight(self) -> None:
        """找不到 account 时用默认 weight=1.0。"""
        tweet = _make_tweet("t1", 999, text="Orphan tweet")
        # 空 accounts_map
        batches = split_into_batches([tweet], {}, token_limit=100_000)
        assert len(batches) == 1
        assert batches[0][0].tweet_id == "t1"
