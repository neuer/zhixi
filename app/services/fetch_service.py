"""fetch_service — 数据采集编排层（US-013/014/015）。"""

import asyncio
import json
import logging
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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

        fetcher = get_fetcher(settings.X_API_BEARER_TOKEN)
        started_at = datetime.now(UTC)

        success_count = 0
        fail_count = 0
        skipped_count = 0
        new_tweets_total = 0
        errors: list[dict[str, str]] = []

        try:
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
                except Exception:
                    logger.exception("抓取账号 %s 失败", account.twitter_handle)
                    fail_count += 1
                    errors.append(
                        {
                            "handle": account.twitter_handle,
                            "error": _safe_exc_message(),
                        }
                    )
        finally:
            await fetcher.close()

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
        assert account.twitter_user_id is not None

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


def _safe_exc_message() -> str:
    """从当前异常上下文安全获取错误消息。"""
    import sys

    exc = sys.exc_info()[1]
    return str(exc) if exc else "unknown error"
