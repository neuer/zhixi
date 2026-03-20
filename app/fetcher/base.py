"""BaseFetcher 抽象基类（US-011 实现）。"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.schemas.fetcher_types import RawTweet


class BaseFetcher(ABC):
    """数据抓取器抽象基类，定义统一接口。"""

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

    async def close(self) -> None:  # noqa: B027  -- 有意设计为可选覆盖，非强制实现
        """释放连接资源。子类可覆盖，默认无操作。"""
