"""XApiFetcher — X API 实现（US-011 实现）。"""

import logging
from datetime import datetime

import httpx

from app.fetcher.base import BaseFetcher
from app.schemas.fetcher_types import PublicMetrics, RawTweet, ReferencedTweet

logger = logging.getLogger(__name__)

# 分页最大页数，防止无限循环
MAX_PAGES = 5


class XApiFetcher(BaseFetcher):
    """通过 X (Twitter) API v2 抓取推文。"""

    def __init__(self, bearer_token: str) -> None:
        """初始化 httpx 客户端。

        Args:
            bearer_token: X API Bearer Token
        """
        self._client = httpx.AsyncClient(
            base_url="https://api.x.com/2",
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=30.0,
        )

    async def fetch_user_tweets(
        self,
        user_id: str,
        since: datetime,
        until: datetime,
    ) -> list[RawTweet]:
        """抓取指定用户在时间区间内的推文，自动分页，最多 MAX_PAGES 页。

        Args:
            user_id: X API 用户数字 ID
            since: 起始时间（含），带时区
            until: 截止时间（含），带时区

        Returns:
            RawTweet 列表
        """
        results: list[RawTweet] = []
        next_token: str | None = None

        for _page in range(MAX_PAGES):
            params: dict[str, str] = {
                "exclude": "retweets",
                "max_results": "100",
                "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "end_time": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "tweet.fields": "created_at,public_metrics,attachments,referenced_tweets",
                "expansions": "attachments.media_keys,referenced_tweets.id",
                "media.fields": "url,type",
            }
            if next_token:
                params["pagination_token"] = next_token

            response = await self._client.get(
                f"/users/{user_id}/tweets",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()

            # 构建辅助索引：includes.tweets → author_id 映射
            includes = payload.get("includes", {})
            included_tweets: dict[str, str] = {
                t["id"]: t["author_id"]
                for t in includes.get("tweets", [])
                if "id" in t and "author_id" in t
            }

            # 构建辅助索引：media_key → url 映射
            media_url_map: dict[str, str] = {
                m["media_key"]: m["url"]
                for m in includes.get("media", [])
                if "media_key" in m and "url" in m
            }

            # 解析推文列表
            for raw in payload.get("data", []):
                tweet = self._parse_tweet(raw, included_tweets, media_url_map)
                if tweet is not None:
                    results.append(tweet)

            # 判断是否有下一页
            next_token = payload.get("meta", {}).get("next_token")
            if not next_token:
                break

        return results

    def _parse_tweet(
        self,
        raw: dict,  # type: ignore[type-arg]
        included_tweets: dict[str, str],
        media_url_map: dict[str, str],
    ) -> RawTweet | None:
        """将 API 返回的单条 tweet dict 解析为 RawTweet。

        Args:
            raw: API 返回的推文字典
            included_tweets: tweet_id -> author_id 映射（来自 includes.tweets）
            media_url_map: media_key -> url 映射（来自 includes.media）

        Returns:
            RawTweet 或 None（解析失败时记录 warning 并跳过）
        """
        try:
            tweet_id = raw["id"]
            author_id = raw["author_id"]
            text = raw["text"]
            created_at_str = raw["created_at"]

            # 解析时间字符串（X API 返回 Z 结尾的 ISO 8601 字符串）
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"
            created_at = datetime.fromisoformat(created_at_str)

            # 解析 public_metrics（忽略模型中不存在的字段，如 quote_count）
            metrics_raw = raw.get("public_metrics", {})
            public_metrics = PublicMetrics(
                like_count=metrics_raw.get("like_count", 0),
                retweet_count=metrics_raw.get("retweet_count", 0),
                reply_count=metrics_raw.get("reply_count", 0),
            )

            # 解析 referenced_tweets，author_id 从 includes.tweets 补全
            referenced_tweets: list[ReferencedTweet] = []
            for ref in raw.get("referenced_tweets", []):
                ref_id = ref.get("id", "")
                ref_type = ref.get("type", "")
                ref_author_id = included_tweets.get(ref_id, "")
                if ref_id and ref_type:
                    referenced_tweets.append(
                        ReferencedTweet(type=ref_type, id=ref_id, author_id=ref_author_id)
                    )

            # 解析 media_urls：从 attachments.media_keys 查找
            media_urls: list[str] = []
            attachments = raw.get("attachments", {})
            for mk in attachments.get("media_keys", []):
                url = media_url_map.get(mk)
                if url:
                    media_urls.append(url)

            # 构造推文 URL
            tweet_url = f"https://x.com/{author_id}/status/{tweet_id}"

            return RawTweet(
                tweet_id=tweet_id,
                author_id=author_id,
                text=text,
                created_at=created_at,
                public_metrics=public_metrics,
                referenced_tweets=referenced_tweets,
                media_urls=media_urls,
                tweet_url=tweet_url,
            )
        except (KeyError, ValueError) as e:
            logger.warning("解析推文失败，跳过。原始数据: %s，错误: %s", raw, e)
            return None

    async def close(self) -> None:
        """关闭 httpx 客户端，释放连接资源。"""
        await self._client.aclose()
