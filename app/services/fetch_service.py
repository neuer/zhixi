"""fetch_service — 数据采集编排层（US-013/014/015 + US-016）。"""

import asyncio
import json
import logging
import re
from datetime import UTC, date, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.x_client import XApiError
from app.config import get_fetch_window, get_today_digest_date, settings
from app.fetcher import get_fetcher
from app.fetcher.base import BaseFetcher
from app.fetcher.tweet_classifier import classify_tweet
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.fetch_log import FetchLog
from app.models.tweet import Tweet
from app.schemas.fetcher_types import KEEP_TYPES, FetchResult, RawTweet, TweetType

logger = logging.getLogger(__name__)


class TweetAlreadyExistsError(Exception):
    """推文已存在于数据库中。"""


# 推文 URL 正则：支持 x.com / twitter.com，可选尾部查询参数
_TWEET_URL_PATTERN = re.compile(r"https?://(?:x\.com|twitter\.com)/(\w+)/status/(\d+)")


def _parse_tweet_id(tweet_url: str) -> str | None:
    """从推文 URL 提取 tweet_id。"""
    match = _TWEET_URL_PATTERN.match(tweet_url.strip())
    return match.group(2) if match else None


def _extract_handle_from_url(tweet_url: str) -> str | None:
    """从推文 URL 提取 handle。"""
    match = _TWEET_URL_PATTERN.match(tweet_url.strip())
    return match.group(1) if match else None


class FetchService:
    """每日推文抓取服务。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_daily_fetch(
        self,
        digest_date: date | None = None,
    ) -> FetchResult:
        """抓取所有活跃账号在时间窗口内的推文。

        流程：
        1. 查询活跃账号
        2. 逐账号调用 X API 抓取推文
        3. 分类过滤 + 去重 + 入库
        4. 记录 fetch_log 和 api_cost_log
        """
        digest_date = digest_date or get_today_digest_date()
        since, until = get_fetch_window(digest_date)

        # 查询活跃账号
        stmt = select(TwitterAccount).where(TwitterAccount.is_active.is_(True))
        accounts = (await self.db.execute(stmt)).scalars().all()

        total_accounts = len(accounts)
        if total_accounts == 0:
            return FetchResult(
                new_tweets_count=0,
                fail_count=0,
                total_accounts=0,
            )

        # 查询已有 tweet_id 用于去重
        existing_ids_stmt = select(Tweet.tweet_id)
        existing_tweet_ids: set[str] = {
            row for row in (await self.db.execute(existing_ids_stmt)).scalars().all()
        }
        seen_ids: set[str] = set()

        started_at = datetime.now(UTC)

        success_count = 0
        fail_count = 0
        skipped_count = 0
        new_tweets_total = 0
        errors: list[dict[str, str]] = []

        async with get_fetcher(settings.X_API_BEARER_TOKEN) as fetcher:
            for idx, account in enumerate(accounts):
                # 跳过无 twitter_user_id 的账号
                if not account.twitter_user_id:
                    logger.warning("账号 %s 无 twitter_user_id，跳过", account.twitter_handle)
                    skipped_count += 1
                    continue

                # 账号间隔 ≥1s（第二个起）
                if idx > 0:
                    await asyncio.sleep(1.0)

                try:
                    new_count = await self._fetch_account(
                        fetcher=fetcher,
                        account=account,
                        since=since,
                        until=until,
                        digest_date=digest_date,
                        existing_ids=existing_tweet_ids,
                        seen_ids=seen_ids,
                    )
                    new_tweets_total += new_count
                    success_count += 1
                except (httpx.HTTPError, XApiError) as e:
                    # 401/403 说明 Bearer Token 失效，立即中止
                    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (
                        401,
                        403,
                    ):
                        logger.error(
                            "X API 认证失败(%d)，中止全部账号抓取",
                            e.response.status_code,
                        )
                        raise
                    logger.warning(
                        "抓取账号 %s 失败（API 错误）: %s",
                        account.twitter_handle,
                        e,
                    )
                    fail_count += 1
                    errors.append(
                        {
                            "handle": account.twitter_handle,
                            "error": str(e),
                        }
                    )
                except Exception:
                    logger.exception(
                        "抓取账号 %s 发生不可恢复错误，终止批处理",
                        account.twitter_handle,
                    )
                    raise

        # 写入 fetch_log
        finished_at = datetime.now(UTC)
        fetch_log = FetchLog(
            fetch_date=digest_date,
            total_accounts=total_accounts,
            success_count=success_count,
            fail_count=fail_count,
            new_tweets=new_tweets_total,
            error_details=json.dumps(errors, ensure_ascii=False) if errors else None,
            started_at=started_at,
            finished_at=finished_at,
        )
        self.db.add(fetch_log)
        await self.db.flush()

        return FetchResult(
            new_tweets_count=new_tweets_total,
            fail_count=fail_count,
            total_accounts=total_accounts,
            skipped_count=skipped_count,
        )

    async def _fetch_account(
        self,
        fetcher: BaseFetcher,
        account: TwitterAccount,
        since: datetime,
        until: datetime,
        digest_date: date,
        existing_ids: set[str],
        seen_ids: set[str],
    ) -> int:
        """抓取单个账号并入库，返回新增推文数。"""
        if account.twitter_user_id is None:
            msg = f"账号 {account.twitter_handle} 缺少 twitter_user_id"
            raise ValueError(msg)

        start_ms = _now_ms()
        raw_tweets = await fetcher.fetch_user_tweets(account.twitter_user_id, since, until)
        duration_ms = _now_ms() - start_ms

        # 记录 api_cost_log
        cost_log = ApiCostLog(
            call_date=digest_date,
            service="x",
            call_type="fetch_tweets",
            endpoint=f"/users/{account.twitter_user_id}/tweets",
            success=True,
            duration_ms=duration_ms,
        )
        self.db.add(cost_log)

        # 分类、过滤、去重、入库
        new_count = 0
        for raw in raw_tweets:
            tweet_type = classify_tweet(raw)
            if tweet_type not in KEEP_TYPES:
                continue
            if raw.tweet_id in existing_ids or raw.tweet_id in seen_ids:
                continue

            tweet = _raw_to_model(raw, account, digest_date, tweet_type)
            self.db.add(tweet)
            seen_ids.add(raw.tweet_id)
            new_count += 1

        # 更新 last_fetch_at
        account.last_fetch_at = datetime.now(UTC)
        await self.db.flush()

        return new_count

    # ── US-016: 单条推文抓取 ──

    async def fetch_single_tweet(
        self,
        tweet_url: str,
        digest_date: date,
    ) -> Tweet:
        """抓取单条推文并入库（source='manual'）。

        流程：
        1. 解析 tweet_url 提取 tweet_id
        2. 检查 tweet_id 是否已存在
        3. 调用 X API 抓取
        4. 查找或创建 account
        5. 入库 Tweet（source='manual', is_ai_relevant=True）

        Raises:
            ValueError: URL 格式无效
            TweetAlreadyExistsError: 推文已存在
            httpx.HTTPStatusError: X API 调用失败
        """
        tweet_id = _parse_tweet_id(tweet_url)
        if not tweet_id:
            msg = "无效的推文URL"
            raise ValueError(msg)

        # 去重检查
        existing = await self.db.execute(select(Tweet).where(Tweet.tweet_id == tweet_id))
        if existing.scalar_one_or_none() is not None:
            raise TweetAlreadyExistsError

        # X API 抓取
        async with get_fetcher(settings.X_API_BEARER_TOKEN) as fetcher:
            raw = await fetcher.fetch_single_tweet(tweet_id)

        # 记录 API 成本
        cost_log = ApiCostLog(
            call_date=digest_date,
            service="x",
            call_type="fetch_single_tweet",
            success=True,
        )
        self.db.add(cost_log)

        # 查找或创建账号
        account = await self._find_or_create_account(raw.author_id, tweet_url)

        # 分类推文
        tweet_type = classify_tweet(raw)

        # 构建 Tweet ORM
        tweet = _raw_to_model(raw, account, digest_date, tweet_type)
        tweet.source = "manual"
        tweet.is_ai_relevant = True
        self.db.add(tweet)
        await self.db.flush()

        return tweet

    async def _find_or_create_account(
        self,
        author_id: str,
        tweet_url: str,
    ) -> TwitterAccount:
        """通过 author_id 查找已有账号，找不到则创建临时账号。"""
        # 按 twitter_user_id 查找
        stmt = select(TwitterAccount).where(TwitterAccount.twitter_user_id == author_id)
        result = await self.db.execute(stmt)
        account = result.scalar_one_or_none()
        if account:
            return account

        # 从 URL 提取 handle，按 handle 查找
        handle = _extract_handle_from_url(tweet_url)
        if handle:
            stmt2 = select(TwitterAccount).where(TwitterAccount.twitter_handle == handle)
            result2 = await self.db.execute(stmt2)
            account2 = result2.scalar_one_or_none()
            if account2:
                # 补全 twitter_user_id
                if not account2.twitter_user_id:
                    account2.twitter_user_id = author_id
                return account2

        # 创建临时账号（不参与自动抓取）
        new_account = TwitterAccount(
            twitter_handle=handle or f"user_{author_id}",
            twitter_user_id=author_id,
            display_name=handle or f"User {author_id}",
            weight=1.0,
            is_active=False,
        )
        self.db.add(new_account)
        await self.db.flush()
        return new_account


# ──────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────


def _raw_to_model(
    raw: RawTweet,
    account: TwitterAccount,
    digest_date: date,
    tweet_type: TweetType,
) -> Tweet:
    """将 RawTweet 映射为 Tweet ORM 模型。"""
    return Tweet(
        tweet_id=raw.tweet_id,
        account_id=account.id,
        digest_date=digest_date,
        original_text=raw.text,
        media_urls=json.dumps(raw.media_urls) if raw.media_urls else None,
        tweet_url=f"https://x.com/{account.twitter_handle}/status/{raw.tweet_id}",
        tweet_time=raw.created_at,
        likes=raw.public_metrics.like_count,
        retweets=raw.public_metrics.retweet_count,
        replies=raw.public_metrics.reply_count,
        is_quote_tweet=tweet_type == TweetType.QUOTE,
        is_self_thread_reply=tweet_type == TweetType.SELF_REPLY,
        source="auto",
    )


def _now_ms() -> int:
    """返回当前时间戳（毫秒）。"""
    return int(datetime.now(UTC).timestamp() * 1000)
