"""digest_service — 草稿组装编排层。

编排草稿创建、快照写入、导读摘要生成、Markdown 渲染、编辑操作。
"""

import json
import logging
import secrets
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import func, select, update
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

# 预览链接有效期（小时）
_PREVIEW_LINK_HOURS = 24


def _ensure_utc(dt: datetime) -> datetime:
    """确保 datetime 有 UTC 时区信息（SQLite 读回可能丢失 tzinfo）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


class DigestService:
    """草稿组装服务。"""

    def __init__(self, db: AsyncSession, claude_client: ClaudeClient) -> None:
        self._db = db
        self._claude = claude_client

    async def generate_daily_digest(
        self, digest_date: date | None = None, *, version: int = 1
    ) -> DailyDigest:
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
            version=version,
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
            if members:  # 过滤空成员话题（regenerate 后旧话题无成员）
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

    # ──────────────────────────────────────────────────
    # 重新生成（US-035）
    # ──────────────────────────────────────────────────

    async def regenerate_digest(self, digest_date: date | None = None) -> DailyDigest:
        """重新生成草稿（重置推文 → M2 全量重跑 → M3 新版本）。

        当日无草稿时等价于首次生成 v1。
        M3 失败时自动回滚旧版本 is_current=true。
        """
        from app.services.process_service import ProcessService

        if digest_date is None:
            digest_date = get_today_digest_date()

        # 1. 查询旧版本（不校验 status）
        old_digest = await self._get_current_digest_or_none(digest_date)
        old_version = old_digest.version if old_digest else 0

        # 2. 重置推文状态（M2 重跑前必须执行）
        await self._reset_tweets_for_reprocess(digest_date)

        # 3. 旧版本 is_current=false
        if old_digest:
            old_digest.is_current = False
            await self._db.flush()

        # 4. M2 + M3
        try:
            process_svc = ProcessService(self._db, claude_client=self._claude)
            await process_svc.run_daily_process(digest_date)

            new_digest = await self.generate_daily_digest(digest_date, version=old_version + 1)
            return new_digest
        except Exception:
            # 回滚：恢复旧版本 is_current
            if old_digest:
                old_digest.is_current = True
                await self._db.flush()
            raise

    async def _get_current_digest_or_none(self, digest_date: date) -> DailyDigest | None:
        """查询当日 is_current=true 的 digest（不校验 status）。"""
        stmt = select(DailyDigest).where(
            DailyDigest.digest_date == digest_date,
            DailyDigest.is_current.is_(True),
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def _reset_tweets_for_reprocess(self, digest_date: date) -> int:
        """重置当日所有推文的 AI 字段，为全量重跑铺路。"""
        stmt = (
            update(Tweet)
            .where(Tweet.digest_date == digest_date)
            .values(is_processed=False, is_ai_relevant=True, topic_id=None)
        )
        result = await self._db.execute(stmt)
        count: int = result.rowcount  # type: ignore[assignment]
        logger.info("重置 %d 条推文状态 (%s)", count, digest_date)
        return count

    # ──────────────────────────────────────────────────
    # US-016: 手动补录推文
    # ──────────────────────────────────────────────────

    async def add_manual_tweet_item(
        self,
        tweet: Tweet,
        digest_date: date,
    ) -> DigestItem:
        """将手动补录推文添加到当日草稿。

        流程：
        1. 获取 current draft
        2. 计算热度分（base_score → normalize 用已有推文范围 → heat_score）
        3. 创建 DigestItem 快照（display_order=max+1）
        4. 更新 item_count + 重渲染 Markdown
        """
        digest = await self._get_current_draft(digest_date)

        # 热度计算
        accounts_map = await self._get_accounts_map({tweet.account_id})
        account = accounts_map.get(tweet.account_id)
        await self._calculate_manual_heat(tweet, account, digest_date)

        # 查询当前最大 display_order
        max_order_result = await self._db.execute(
            select(func.max(DigestItem.display_order)).where(DigestItem.digest_id == digest.id)
        )
        max_order: int = max_order_result.scalar_one_or_none() or 0

        # 创建 DigestItem
        item = self._create_tweet_item(
            digest_id=digest.id,
            display_order=max_order + 1,
            tweet=tweet,
            accounts_map=accounts_map,
        )
        self._db.add(item)

        # 更新 item_count
        digest.item_count = (digest.item_count or 0) + 1

        # 重渲染 Markdown
        await self._rerender_markdown(digest)
        await self._db.flush()

        return item

    async def _calculate_manual_heat(
        self,
        tweet: Tweet,
        account: TwitterAccount | None,
        digest_date: date,
    ) -> None:
        """计算手动补录推文的热度分。

        规则：
        - base_score 按公式正常计算
        - ai_importance_score 固定 50
        - normalize 使用当日已有推文的 base_heat_score min/max
        - 超出范围截断到 0 或 100
        """
        from app.processor.heat_calculator import (
            calculate_base_score,
            calculate_heat_score,
            calculate_hours_since_post,
            get_reference_time,
        )

        ref_time = get_reference_time(digest_date)
        weight = account.weight if account else 1.0
        tweet_time = _ensure_utc(tweet.tweet_time)
        hours = calculate_hours_since_post(tweet_time, ref_time)

        tweet.base_heat_score = calculate_base_score(
            tweet.likes,
            tweet.retweets,
            tweet.replies,
            weight,
            hours,
        )
        tweet.ai_importance_score = 50.0

        # 查询当日已有推文的 base_heat_score 范围
        existing_scores = await self._get_existing_base_scores(digest_date)

        if len(existing_scores) < 2:
            normalized = 50.0
        else:
            min_score = min(existing_scores)
            max_score = max(existing_scores)
            if min_score == max_score:
                normalized = 50.0
            else:
                raw_normalized = (tweet.base_heat_score - min_score) / (max_score - min_score) * 100
                normalized = max(0.0, min(100.0, raw_normalized))

        tweet.heat_score = calculate_heat_score(normalized, 50.0)

    async def _get_existing_base_scores(self, digest_date: date) -> list[float]:
        """查询当日已处理推文的 base_heat_score（用于 normalize 参照范围）。"""
        stmt = select(Tweet.base_heat_score).where(
            Tweet.digest_date == digest_date,
            Tweet.is_ai_relevant.is_(True),
            Tweet.is_processed.is_(True),
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    # ──────────────────────────────────────────────────
    # 编辑操作（US-031/032/033/034）
    # ──────────────────────────────────────────────────

    async def _get_current_draft(self, digest_date: date) -> DailyDigest:
        """获取当日 is_current=true 的草稿，校验 status=draft。"""
        stmt = select(DailyDigest).where(
            DailyDigest.digest_date == digest_date,
            DailyDigest.is_current.is_(True),
        )
        result = await self._db.execute(stmt)
        digest = result.scalar_one_or_none()
        if digest is None:
            raise DigestNotFoundError
        if digest.status != "draft":
            raise DigestNotEditableError
        return digest

    async def _find_item(self, digest_id: int, item_type: str, item_ref_id: int) -> DigestItem:
        """通过 (digest_id, item_type, item_ref_id) 定位 digest_item。"""
        stmt = select(DigestItem).where(
            DigestItem.digest_id == digest_id,
            DigestItem.item_type == item_type,
            DigestItem.item_ref_id == item_ref_id,
        )
        result = await self._db.execute(stmt)
        item = result.scalar_one_or_none()
        if item is None:
            raise DigestItemNotFoundError
        return item

    async def _rerender_markdown(self, digest: DailyDigest) -> None:
        """重新查询 items → 调用 render_markdown → 写回 content_markdown。"""
        items_stmt = (
            select(DigestItem)
            .where(DigestItem.digest_id == digest.id)
            .order_by(DigestItem.display_order)
        )
        items_result = await self._db.execute(items_stmt)
        items = list(items_result.scalars().all())
        top_n = int(await get_system_config(self._db, "top_n", "10"))
        digest.content_markdown = render_markdown(digest, items, top_n)

    async def edit_item(
        self,
        item_type: str,
        item_ref_id: int,
        updates: dict[str, str],
        digest_date: date | None = None,
    ) -> DigestItem:
        """编辑单条内容的 snapshot 字段（US-031）。"""
        if digest_date is None:
            digest_date = get_today_digest_date()

        digest = await self._get_current_draft(digest_date)
        item = await self._find_item(digest.id, item_type, item_ref_id)

        # 字段映射：请求字段 → snapshot 字段
        field_map = {
            "title": "snapshot_title",
            "translation": "snapshot_translation",
            "summary": "snapshot_summary",
            "perspectives": "snapshot_perspectives",
            "comment": "snapshot_comment",
        }
        for req_field, snap_field in field_map.items():
            value = updates.get(req_field)
            if value is not None:
                setattr(item, snap_field, value)

        await self._rerender_markdown(digest)
        await self._db.flush()
        return item

    async def edit_summary(
        self,
        summary: str,
        digest_date: date | None = None,
    ) -> None:
        """编辑导读摘要并重渲染 Markdown（US-032）。"""
        if digest_date is None:
            digest_date = get_today_digest_date()

        digest = await self._get_current_draft(digest_date)
        digest.summary = summary
        await self._rerender_markdown(digest)
        await self._db.flush()

    async def reorder_items(
        self,
        items_input: list[dict[str, object]],
        digest_date: date | None = None,
    ) -> None:
        """调整排序与置顶（US-033）。"""
        if digest_date is None:
            digest_date = get_today_digest_date()

        digest = await self._get_current_draft(digest_date)

        for entry in items_input:
            item_id = entry["id"]
            stmt = select(DigestItem).where(
                DigestItem.id == item_id,
                DigestItem.digest_id == digest.id,
            )
            result = await self._db.execute(stmt)
            item = result.scalar_one_or_none()
            if item is None:
                raise DigestItemNotFoundError
            item.display_order = entry["display_order"]  # type: ignore[assignment]
            item.is_pinned = entry.get("is_pinned", False)  # type: ignore[assignment]

        await self._rerender_markdown(digest)
        await self._db.flush()

    async def exclude_item(
        self,
        item_type: str,
        item_ref_id: int,
        digest_date: date | None = None,
    ) -> None:
        """剔除条目（US-034）。"""
        if digest_date is None:
            digest_date = get_today_digest_date()

        digest = await self._get_current_draft(digest_date)
        item = await self._find_item(digest.id, item_type, item_ref_id)
        item.is_excluded = True
        await self._rerender_markdown(digest)
        await self._db.flush()

    async def restore_item(
        self,
        item_type: str,
        item_ref_id: int,
        digest_date: date | None = None,
    ) -> None:
        """恢复条目（US-034）。"""
        if digest_date is None:
            digest_date = get_today_digest_date()

        digest = await self._get_current_draft(digest_date)
        item = await self._find_item(digest.id, item_type, item_ref_id)
        item.is_excluded = False

        # display_order = max(非 excluded 条目) + 1
        max_order_stmt = select(func.max(DigestItem.display_order)).where(
            DigestItem.digest_id == digest.id,
            DigestItem.is_excluded.is_(False),
            DigestItem.id != item.id,
        )
        max_result = await self._db.execute(max_order_stmt)
        max_order = max_result.scalar_one_or_none() or 0
        item.display_order = max_order + 1

        await self._rerender_markdown(digest)
        await self._db.flush()

    # ──────────────────────────────────────────────────
    # 预览签名链接（US-009）
    # ──────────────────────────────────────────────────

    async def generate_preview_link(self, digest_date: date | None = None) -> tuple[str, datetime]:
        """生成预览签名 token。

        同一 digest 只允许一个有效 token，新 token 覆盖旧 token。
        返回 (token, expires_at)。
        """
        if digest_date is None:
            digest_date = get_today_digest_date()

        digest = await self._get_current_digest_or_none(digest_date)
        if digest is None:
            raise DigestNotFoundError

        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=_PREVIEW_LINK_HOURS)

        digest.preview_token = token
        digest.preview_expires_at = expires_at
        await self._db.flush()

        return token, expires_at

    async def get_preview_by_token(self, token: str) -> tuple[DailyDigest, list[DigestItem]]:
        """根据签名 token 获取预览内容。

        验证：token 匹配 + 未过期 + digest is_current=True。
        无效 token 抛 PreviewTokenInvalidError。
        """
        stmt = select(DailyDigest).where(DailyDigest.preview_token == token)
        result = await self._db.execute(stmt)
        digest = result.scalar_one_or_none()

        if digest is None:
            raise PreviewTokenInvalidError

        if not digest.is_current:
            raise PreviewTokenInvalidError

        if digest.preview_expires_at is None:
            raise PreviewTokenInvalidError

        if _ensure_utc(digest.preview_expires_at) < datetime.now(UTC):
            raise PreviewTokenInvalidError

        items_stmt = (
            select(DigestItem)
            .where(DigestItem.digest_id == digest.id)
            .order_by(DigestItem.display_order)
        )
        items_result = await self._db.execute(items_stmt)
        items = list(items_result.scalars().all())

        return digest, items


class DigestNotFoundError(Exception):
    """当日无 is_current=true 的草稿。"""


class DigestNotEditableError(Exception):
    """草稿状态非 draft，不可编辑。"""


class DigestItemNotFoundError(Exception):
    """指定的 digest_item 不存在。"""


class PreviewTokenInvalidError(Exception):
    """预览 token 无效、已过期或对应版本已失效。"""
