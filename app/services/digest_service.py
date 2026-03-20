"""digest_service — 草稿组装编排层（US-023 + US-024 + US-025）。

编排草稿创建、快照写入、导读摘要生成、Markdown 渲染。
"""

import json
import logging
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeClient
from app.config import get_system_config, get_today_digest_date
from app.digest.renderer import render_markdown
from app.digest.summary_generator import generate_summary
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.topic import Topic
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse

logger = logging.getLogger(__name__)

# 导读摘要取 TOP N 条目
_SUMMARY_TOP_N = 5


class DigestService:
    """草稿组装服务。"""

    def __init__(self, db: AsyncSession, claude_client: ClaudeClient) -> None:
        self._db = db
        self._claude = claude_client

    async def generate_daily_digest(self, digest_date: date | None = None) -> DailyDigest:
        """生成当日草稿。

        流程：查询数据 → 创建 DailyDigest → 创建 DigestItem 快照 → 生成导读摘要。
        """
        if digest_date is None:
            digest_date = get_today_digest_date()

        # 1. 查询已处理推文（独立推文，topic_id IS NULL）
        standalone_tweets = await self._get_standalone_tweets(digest_date)

        # 2. 查询话题及其成员推文
        topics_with_members = await self._get_topics_with_members(digest_date)

        # 3. 收集所有相关 account_id 并批量查询
        account_ids: set[int] = set()
        for tweet in standalone_tweets:
            account_ids.add(tweet.account_id)
        for _topic, members in topics_with_members:
            for tweet in members:
                account_ids.add(tweet.account_id)
        accounts_map = await self._get_accounts_map(account_ids)

        # 4. 构建待排序项：(heat_score, item_type, source_obj, extra_data)
        sortable_items = self._build_sortable_items(
            standalone_tweets, topics_with_members, accounts_map
        )

        # 5. 按 heat_score 降序排序
        sortable_items.sort(key=lambda x: x[0], reverse=True)

        # 6. 创建 DailyDigest
        digest = DailyDigest(
            digest_date=digest_date,
            version=1,
            is_current=True,
            status="draft",
            item_count=len(sortable_items),
        )
        self._db.add(digest)
        await self._db.flush()

        # 7. 创建 DigestItem 快照
        created_items: list[DigestItem] = []
        for order, (_score, item_type, source_obj, extra) in enumerate(sortable_items, start=1):
            item = self._create_digest_item(
                digest_id=digest.id,
                display_order=order,
                item_type=item_type,
                source_obj=source_obj,
                accounts_map=accounts_map,
                extra=extra,
            )
            self._db.add(item)
            created_items.append(item)

        await self._db.flush()

        # 8. 生成导读摘要
        top_items = created_items[:_SUMMARY_TOP_N]
        summary, cost_response = await generate_summary(self._claude, top_items)
        digest.summary = summary
        if cost_response:
            self._record_cost(cost_response, "summary", digest_date)

        # 9. 渲染 Markdown
        top_n = int(await get_system_config(self._db, "top_n", "10"))
        digest.content_markdown = render_markdown(digest, created_items, top_n)

        await self._db.flush()
        logger.info(
            "草稿生成完成: digest_id=%d, items=%d, date=%s",
            digest.id,
            len(created_items),
            digest_date,
        )
        return digest

    # ──────────────────────────────────────────────────
    # 查询方法
    # ──────────────────────────────────────────────────

    async def _get_standalone_tweets(self, digest_date: date) -> list[Tweet]:
        """查询当日已处理的独立推文（topic_id IS NULL）。"""
        stmt = (
            select(Tweet)
            .where(
                Tweet.digest_date == digest_date,
                Tweet.is_ai_relevant.is_(True),
                Tweet.is_processed.is_(True),
                Tweet.topic_id.is_(None),
            )
            .order_by(Tweet.heat_score.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def _get_topics_with_members(self, digest_date: date) -> list[tuple[Topic, list[Tweet]]]:
        """查询当日话题及各话题的成员推文。"""
        topic_stmt = select(Topic).where(Topic.digest_date == digest_date)
        topic_result = await self._db.execute(topic_stmt)
        topics = list(topic_result.scalars().all())

        result: list[tuple[Topic, list[Tweet]]] = []
        for topic in topics:
            member_stmt = (
                select(Tweet).where(Tweet.topic_id == topic.id).order_by(Tweet.tweet_time.asc())
            )
            member_result = await self._db.execute(member_stmt)
            members = list(member_result.scalars().all())
            result.append((topic, members))
        return result

    async def _get_accounts_map(self, account_ids: set[int]) -> dict[int, TwitterAccount]:
        """批量查询账号信息。"""
        if not account_ids:
            return {}
        stmt = select(TwitterAccount).where(TwitterAccount.id.in_(account_ids))
        result = await self._db.execute(stmt)
        return {acct.id: acct for acct in result.scalars().all()}

    # ──────────────────────────────────────────────────
    # 构建排序项
    # ──────────────────────────────────────────────────

    def _build_sortable_items(
        self,
        standalone_tweets: list[Tweet],
        topics_with_members: list[tuple[Topic, list[Tweet]]],
        accounts_map: dict[int, TwitterAccount],
    ) -> list[tuple[float, str, Tweet | Topic, dict[str, object]]]:
        """构建 (heat_score, item_type, source_obj, extra_data) 元组列表。"""
        items: list[tuple[float, str, Tweet | Topic, dict[str, object]]] = []

        # 独立推文
        for tweet in standalone_tweets:
            items.append((tweet.heat_score, "tweet", tweet, {}))

        # 话题
        for topic, members in topics_with_members:
            extra: dict[str, object] = {"members": members}
            items.append((topic.heat_score, "topic", topic, extra))

        return items

    # ──────────────────────────────────────────────────
    # 创建 DigestItem
    # ──────────────────────────────────────────────────

    def _create_digest_item(
        self,
        *,
        digest_id: int,
        display_order: int,
        item_type: str,
        source_obj: Tweet | Topic,
        accounts_map: dict[int, TwitterAccount],
        extra: dict[str, object],
    ) -> DigestItem:
        """根据源对象类型创建 DigestItem 并填充 snapshot。"""
        if item_type == "tweet" and isinstance(source_obj, Tweet):
            return self._create_tweet_item(digest_id, display_order, source_obj, accounts_map)

        if item_type == "topic" and isinstance(source_obj, Topic):
            members = extra.get("members", [])
            assert isinstance(members, list)
            return self._create_topic_item(
                digest_id, display_order, source_obj, members, accounts_map
            )

        msg = f"未知 item_type: {item_type}"
        raise ValueError(msg)

    def _create_tweet_item(
        self,
        digest_id: int,
        display_order: int,
        tweet: Tweet,
        accounts_map: dict[int, TwitterAccount],
    ) -> DigestItem:
        """创建 tweet 类型 DigestItem。"""
        account = accounts_map.get(tweet.account_id)
        return DigestItem(
            digest_id=digest_id,
            item_type="tweet",
            item_ref_id=tweet.id,
            display_order=display_order,
            snapshot_title=tweet.title,
            snapshot_translation=tweet.translated_text,
            snapshot_comment=tweet.ai_comment,
            snapshot_heat_score=tweet.heat_score,
            snapshot_author_name=account.display_name if account else None,
            snapshot_author_handle=account.twitter_handle if account else None,
            snapshot_tweet_url=tweet.tweet_url,
            snapshot_tweet_time=tweet.tweet_time,
        )

    def _create_topic_item(
        self,
        digest_id: int,
        display_order: int,
        topic: Topic,
        members: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
    ) -> DigestItem:
        """创建 topic 类型 DigestItem。"""
        if topic.type == "aggregated":
            return self._create_aggregated_item(
                digest_id, display_order, topic, members, accounts_map
            )
        return self._create_thread_item(digest_id, display_order, topic, members, accounts_map)

    def _create_aggregated_item(
        self,
        digest_id: int,
        display_order: int,
        topic: Topic,
        members: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
    ) -> DigestItem:
        """创建 aggregated topic 的 DigestItem。"""
        source_tweets = self._build_source_tweets_json(members, accounts_map)
        return DigestItem(
            digest_id=digest_id,
            item_type="topic",
            item_ref_id=topic.id,
            display_order=display_order,
            snapshot_title=topic.title,
            snapshot_summary=topic.summary,
            snapshot_comment=topic.ai_comment,
            snapshot_perspectives=topic.perspectives,
            snapshot_heat_score=topic.heat_score,
            snapshot_source_tweets=source_tweets,
            snapshot_topic_type="aggregated",
        )

    def _create_thread_item(
        self,
        digest_id: int,
        display_order: int,
        topic: Topic,
        members: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
    ) -> DigestItem:
        """创建 thread topic 的 DigestItem。"""
        # Thread 作者 = 第一条推文的作者（members 已按 tweet_time ASC 排序）
        first_tweet = members[0] if members else None
        first_account = accounts_map.get(first_tweet.account_id) if first_tweet else None
        return DigestItem(
            digest_id=digest_id,
            item_type="topic",
            item_ref_id=topic.id,
            display_order=display_order,
            snapshot_title=topic.title,
            snapshot_translation=topic.summary,
            snapshot_comment=topic.ai_comment,
            snapshot_heat_score=topic.heat_score,
            snapshot_author_name=first_account.display_name if first_account else None,
            snapshot_author_handle=first_account.twitter_handle if first_account else None,
            snapshot_tweet_url=first_tweet.tweet_url if first_tweet else None,
            snapshot_topic_type="thread",
        )

    def _build_source_tweets_json(
        self,
        members: list[Tweet],
        accounts_map: dict[int, TwitterAccount],
    ) -> str:
        """构建 snapshot_source_tweets JSON: [{handle, tweet_url}]。"""
        sources: list[dict[str, str]] = []
        for tweet in members:
            account = accounts_map.get(tweet.account_id)
            sources.append(
                {
                    "handle": account.twitter_handle if account else "",
                    "tweet_url": tweet.tweet_url or "",
                }
            )
        return json.dumps(sources, ensure_ascii=False)

    # ──────────────────────────────────────────────────
    # 成本记录
    # ──────────────────────────────────────────────────

    def _record_cost(self, response: ClaudeResponse, call_type: str, digest_date: date) -> None:
        """写入 api_cost_log。"""
        cost_log = ApiCostLog(
            call_date=digest_date,
            service="claude",
            call_type=call_type,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=response.estimated_cost,
            duration_ms=response.duration_ms,
        )
        self._db.add(cost_log)
