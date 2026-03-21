"""第三方数据源适配器（预留空壳）。"""

from datetime import datetime

from app.fetcher.base import BaseFetcher
from app.schemas.fetcher_types import RawTweet


class ThirdPartyFetcher(BaseFetcher):
    """第三方数据源抓取器（Phase 2 占位实现）。"""

    async def fetch_user_tweets(
        self,
        user_id: str,
        since: datetime,
        until: datetime,
    ) -> list[RawTweet]:
        """第三方数据源抓取（尚未实现）。

        Raises:
            NotImplementedError: Phase 2 实现前始终抛出
        """
        raise NotImplementedError("第三方数据源抓取功能将在 Phase 2 实现")

    async def fetch_single_tweet(self, tweet_id: str) -> RawTweet:
        """第三方单条推文抓取（尚未实现）。

        签名需与 BaseFetcher.fetch_single_tweet(tweet_id: str) 保持一致。
        """
        raise NotImplementedError("第三方单条推文抓取功能将在 Phase 2 实现")
