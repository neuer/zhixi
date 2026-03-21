"""BaseFetcher 抽象基类（US-011 实现）。"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Self

from app.schemas.fetcher_types import RawTweet


class BaseFetcher(ABC):
    """数据抓取器抽象基类，定义统一接口。"""

    async def __aenter__(self) -> Self:
        """支持 async with 用法。"""
        return self

    async def __aexit__(self, *_: object) -> None:
        """退出时自动关闭资源。"""
        await self.close()

    @abstractmethod
    async def fetch_user_tweets(
        self,
        user_id: str,
        since: datetime,
        until: datetime,
    ) -> list[RawTweet]:
        """抓取指定用户在时间区间内的推文。

        Args:
            user_id: 用户 ID（X API 数字字符串）
            since: 抓取起始时间（含），必须带时区
            until: 抓取截止时间（含），必须带时区

        Returns:
            RawTweet 列表，按 API 返回顺序排列
        """
        ...

    @abstractmethod
    async def fetch_single_tweet(self, tweet_id: str) -> RawTweet:
        """抓取单条推文。

        Args:
            tweet_id: 推文 ID 字符串（X API 数字 ID）

        Returns:
            RawTweet

        Raises:
            httpx.HTTPStatusError: API 错误（含 404 推文不存在）
            ValueError: 解析失败
        """
        ...

    async def close(self) -> None:  # noqa: B027  -- 有意设计为可选覆盖，非强制实现
        """释放连接资源。子类可覆盖，默认无操作。"""
