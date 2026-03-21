"""XApiFetcher — X API 实现（US-011 + US-015 限流重试）。"""

import asyncio
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

            response = await self._request_with_retry(
                f"/users/{user_id}/tweets",
                params,
            )
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
        raw: dict[str, object],
        included_tweets: dict[str, str],
        media_url_map: dict[str, str],
    ) -> RawTweet | None:
        """将 API 返回的单条 tweet dict 解析为 RawTweet。

        Args:
            raw: API 返回的推文字典
            included_tweets: tweet_id -> author_id 映射（来自 includes.tweets）
            media_url_map: media_key -> url 映射（来自 includes.media）

        Returns:
            RawTweet 或 None（解析失败时记录日志并跳过）
        """
        # 必需字段提取——缺失时提升为 ERROR（可能意味着 API schema 变更）
        try:
            tweet_id = str(raw["id"])
            author_id = str(raw["author_id"])
            text = str(raw["text"])
            created_at_str = str(raw["created_at"])
        except KeyError as e:
            logger.error(
                "推文缺少必要字段 %s，可能 X API schema 已变更。keys=%s",
                e,
                list(raw.keys()),
            )
            return None

        # 解析时间字符串（X API 返回 Z 结尾的 ISO 8601 字符串）
        try:
            if created_at_str.endswith("Z"):
                created_at_str = created_at_str[:-1] + "+00:00"
            created_at = datetime.fromisoformat(created_at_str)
        except ValueError as e:
            logger.warning("推文 %s 时间格式异常: %s", tweet_id, e)
            return None

        # 解析 public_metrics（忽略模型中不存在的字段，如 quote_count）
        metrics_raw = raw.get("public_metrics", {})
        if not isinstance(metrics_raw, dict):
            metrics_raw = {}
        public_metrics = PublicMetrics(
            like_count=metrics_raw.get("like_count", 0),
            retweet_count=metrics_raw.get("retweet_count", 0),
            reply_count=metrics_raw.get("reply_count", 0),
        )

        # 解析 referenced_tweets，author_id 从 includes.tweets 补全
        referenced_tweets: list[ReferencedTweet] = []
        raw_refs = raw.get("referenced_tweets", [])
        if isinstance(raw_refs, list):
            for ref in raw_refs:
                if isinstance(ref, dict):
                    ref_id = ref.get("id", "")
                    ref_type = ref.get("type", "")
                    ref_author_id = included_tweets.get(str(ref_id), "")
                    if ref_id and ref_type:
                        referenced_tweets.append(
                            ReferencedTweet(
                                type=str(ref_type),
                                id=str(ref_id),
                                author_id=str(ref_author_id),
                            )
                        )

        # 解析 media_urls：从 attachments.media_keys 查找
        media_urls: list[str] = []
        attachments = raw.get("attachments", {})
        if isinstance(attachments, dict):
            for mk in attachments.get("media_keys", []):
                url = media_url_map.get(str(mk))
                if url:
                    media_urls.append(url)

        # 构造推文 URL（此处用 author_id，入库时 _raw_to_model 会用 handle 重新构造）
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

    async def _request_with_retry(
        self,
        url: str,
        params: dict[str, str],
    ) -> httpx.Response:
        """发送 GET 请求，遇到 429 限流时指数退避重试（2s→4s→8s，最多 3 次）。"""
        backoff_delays = [2, 4, 8]
        response = await self._client.get(url, params=params)
        for delay in backoff_delays:
            if response.status_code != 429:
                break
            logger.warning("X API 429 限流，%ds 后重试", delay)
            await asyncio.sleep(delay)
            response = await self._client.get(url, params=params)
        response.raise_for_status()
        return response

    async def fetch_single_tweet(self, tweet_id: str) -> RawTweet:
        """抓取单条推文（X API v2 GET /tweets/:id）。

        Args:
            tweet_id: 推文 ID 字符串

        Returns:
            RawTweet

        Raises:
            httpx.HTTPStatusError: API 调用失败
            ValueError: 解析失败
        """
        params: dict[str, str] = {
            "tweet.fields": "author_id,created_at,public_metrics,attachments,referenced_tweets",
            "expansions": "attachments.media_keys,referenced_tweets.id",
            "media.fields": "url,type",
        }
        response = await self._request_with_retry(f"/tweets/{tweet_id}", params)
        payload = response.json()

        data = payload.get("data")
        if not data:
            msg = f"推文不存在: {tweet_id}"
            raise ValueError(msg)

        includes = payload.get("includes", {})
        included_tweets: dict[str, str] = {
            t["id"]: t["author_id"]
            for t in includes.get("tweets", [])
            if "id" in t and "author_id" in t
        }
        media_url_map: dict[str, str] = {
            m["media_key"]: m["url"]
            for m in includes.get("media", [])
            if "media_key" in m and "url" in m
        }

        tweet = self._parse_tweet(data, included_tweets, media_url_map)
        if tweet is None:
            msg = f"解析推文失败: {tweet_id}"
            raise ValueError(msg)
        return tweet

    async def close(self) -> None:
        """关闭 httpx 客户端，释放连接资源。"""
        await self._client.aclose()
