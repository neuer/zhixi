"""统一测试数据工厂 — 所有 seed 操作的单一入口。"""

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import TwitterAccount
from app.models.config import SystemConfig
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.topic import Topic
from app.models.tweet import Tweet
from app.schemas.enums import DigestStatus, ItemType, TopicType

# ── 默认日期常量 ──

DEFAULT_DATE = date(2026, 3, 20)
DEFAULT_TWEET_TIME = datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC)


# ── SystemConfig ──


async def create_system_config(
    db: AsyncSession,
    *,
    top_n: str = "10",
    min_articles: str = "1",
    push_time: str = "08:00",
    push_days: str = "1,2,3,4,5,6,7",
    publish_mode: str = "manual",
    enable_cover_generation: str = "false",
    cover_generation_timeout: str = "30",
    notification_webhook_url: str = "",
    admin_password_hash: str = "",
    display_mode: str = "simple",
) -> list[SystemConfig]:
    """预置系统配置。返回所有配置项列表。"""
    configs = [
        SystemConfig(key="push_time", value=push_time),
        SystemConfig(key="push_days", value=push_days),
        SystemConfig(key="top_n", value=top_n),
        SystemConfig(key="min_articles", value=min_articles),
        SystemConfig(key="display_mode", value=display_mode),
        SystemConfig(key="publish_mode", value=publish_mode),
        SystemConfig(key="enable_cover_generation", value=enable_cover_generation),
        SystemConfig(key="cover_generation_timeout", value=cover_generation_timeout),
        SystemConfig(key="notification_webhook_url", value=notification_webhook_url),
        SystemConfig(key="admin_password_hash", value=admin_password_hash),
    ]
    db.add_all(configs)
    await db.flush()
    return configs


async def seed_config_keys(db: AsyncSession, **key_values: str) -> None:
    """预置指定的配置键值对（仅需要的最小集合）。"""
    for key, value in key_values.items():
        db.add(SystemConfig(key=key, value=value))
    await db.flush()


# ── TwitterAccount ──


async def create_account(
    db: AsyncSession,
    *,
    twitter_handle: str = "testuser",
    display_name: str = "Test User",
    bio: str | None = "AI researcher",
    weight: float = 1.0,
    is_active: bool = True,
    twitter_user_id: str | None = None,
    followers_count: int = 0,
    **overrides: Any,
) -> TwitterAccount:
    """创建测试账号。"""
    fields: dict[str, object] = {
        "twitter_handle": twitter_handle,
        "display_name": display_name,
        "bio": bio,
        "weight": weight,
        "is_active": is_active,
        "twitter_user_id": twitter_user_id,
        "followers_count": followers_count,
        **overrides,
    }
    account = TwitterAccount(**fields)  # type: ignore[arg-type]
    db.add(account)
    await db.flush()
    return account


# ── Tweet ──


async def create_tweet(
    db: AsyncSession,
    account: TwitterAccount,
    *,
    tweet_id: str = "t1",
    text: str = "AI tweet",
    tweet_time: datetime | None = None,
    digest_date: date | None = None,
    likes: int = 100,
    retweets: int = 20,
    replies: int = 10,
    is_quote_tweet: bool = False,
    is_self_thread_reply: bool = False,
    is_ai_relevant: bool = True,
    is_processed: bool = False,
    title: str | None = None,
    translated_text: str | None = None,
    ai_comment: str | None = None,
    ai_importance_score: float = 0,
    base_heat_score: float = 0,
    heat_score: float = 0,
    topic_id: int | None = None,
    **overrides: Any,
) -> Tweet:
    """创建测试推文。"""
    actual_time = tweet_time or DEFAULT_TWEET_TIME
    actual_date = digest_date or DEFAULT_DATE
    fields: dict[str, object] = {
        "tweet_id": tweet_id,
        "account_id": account.id,
        "digest_date": actual_date,
        "original_text": text,
        "tweet_time": actual_time,
        "likes": likes,
        "retweets": retweets,
        "replies": replies,
        "is_quote_tweet": is_quote_tweet,
        "is_self_thread_reply": is_self_thread_reply,
        "is_ai_relevant": is_ai_relevant,
        "is_processed": is_processed,
        "title": title,
        "translated_text": translated_text,
        "ai_comment": ai_comment,
        "ai_importance_score": ai_importance_score,
        "base_heat_score": base_heat_score,
        "heat_score": heat_score,
        "topic_id": topic_id,
        "tweet_url": f"https://x.com/{account.twitter_handle}/status/{tweet_id}",
        **overrides,
    }
    tweet = Tweet(**fields)  # type: ignore[arg-type]
    db.add(tweet)
    await db.flush()
    return tweet


# ── Topic ──


async def create_topic(
    db: AsyncSession,
    *,
    digest_date: date | None = None,
    topic_type: TopicType | str = TopicType.AGGREGATED,
    title: str = "话题标题",
    summary: str | None = "话题摘要",
    perspectives: str | None = None,
    ai_comment: str = "话题点评",
    heat_score: float = 60.0,
    ai_importance_score: float = 80.0,
    tweet_count: int = 2,
    **overrides: Any,
) -> Topic:
    """创建测试话题。"""
    fields: dict[str, object] = {
        "digest_date": digest_date or DEFAULT_DATE,
        "type": topic_type,
        "title": title,
        "summary": summary,
        "perspectives": perspectives,
        "ai_comment": ai_comment,
        "heat_score": heat_score,
        "ai_importance_score": ai_importance_score,
        "tweet_count": tweet_count,
        **overrides,
    }
    topic = Topic(**fields)  # type: ignore[arg-type]
    db.add(topic)
    await db.flush()
    return topic


# ── DailyDigest ──


async def create_digest(
    db: AsyncSession,
    *,
    digest_date: date | None = None,
    version: int = 1,
    is_current: bool = True,
    status: DigestStatus | str = DigestStatus.DRAFT,
    item_count: int = 0,
    summary: str | None = None,
    content_markdown: str | None = None,
    published_at: datetime | None = None,
    **overrides: Any,
) -> DailyDigest:
    """创建测试日报。"""
    fields: dict[str, object] = {
        "digest_date": digest_date or DEFAULT_DATE,
        "version": version,
        "is_current": is_current,
        "status": status,
        "item_count": item_count,
        "summary": summary,
        "content_markdown": content_markdown,
        "published_at": published_at,
        **overrides,
    }
    digest = DailyDigest(**fields)  # type: ignore[arg-type]
    db.add(digest)
    await db.flush()
    return digest


# ── DigestItem ──


async def create_digest_item(
    db: AsyncSession,
    digest: DailyDigest,
    *,
    item_type: ItemType | str = ItemType.TWEET,
    item_ref_id: int = 1,
    display_order: int = 1,
    is_excluded: bool = False,
    snapshot_title: str | None = "标题",
    snapshot_translation: str | None = "翻译",
    snapshot_comment: str | None = "点评",
    snapshot_heat_score: float = 85.0,
    snapshot_author_name: str | None = None,
    snapshot_author_handle: str | None = None,
    snapshot_tweet_url: str | None = None,
    snapshot_tweet_time: datetime | None = None,
    snapshot_topic_type: TopicType | str | None = None,
    snapshot_summary: str | None = None,
    snapshot_perspectives: str | None = None,
    snapshot_source_tweets: str | None = None,
    **overrides: Any,
) -> DigestItem:
    """创建测试日报条目。"""
    fields: dict[str, object] = {
        "digest_id": digest.id,
        "item_type": item_type,
        "item_ref_id": item_ref_id,
        "display_order": display_order,
        "is_excluded": is_excluded,
        "snapshot_title": snapshot_title,
        "snapshot_translation": snapshot_translation,
        "snapshot_comment": snapshot_comment,
        "snapshot_heat_score": snapshot_heat_score,
        "snapshot_author_name": snapshot_author_name,
        "snapshot_author_handle": snapshot_author_handle,
        "snapshot_tweet_url": snapshot_tweet_url,
        "snapshot_tweet_time": snapshot_tweet_time or DEFAULT_TWEET_TIME,
        "snapshot_topic_type": snapshot_topic_type,
        "snapshot_summary": snapshot_summary,
        "snapshot_perspectives": snapshot_perspectives,
        "snapshot_source_tweets": snapshot_source_tweets,
        **overrides,
    }
    item = DigestItem(**fields)  # type: ignore[arg-type]
    db.add(item)
    await db.flush()
    return item


# ── 组合工厂 ──


async def create_digest_with_items(
    db: AsyncSession,
    *,
    digest_date: date | None = None,
    status: DigestStatus | str = DigestStatus.DRAFT,
    item_count: int = 2,
    version: int = 1,
    include_excluded: bool = False,
) -> tuple[DailyDigest, list[DigestItem]]:
    """创建 Digest + 多条 DigestItem。"""
    account = await create_account(db, twitter_handle="factory_user")
    actual_date = digest_date or DEFAULT_DATE

    digest = await create_digest(
        db,
        digest_date=actual_date,
        status=status,
        item_count=item_count,
        version=version,
    )

    items: list[DigestItem] = []
    for i in range(item_count):
        tweet = await create_tweet(
            db,
            account,
            tweet_id=f"tw_{i}",
            is_processed=True,
            heat_score=100.0 - i * 10,
            title=f"标题{i}",
            translated_text=f"翻译{i}",
            ai_comment=f"点评{i}",
        )
        item = await create_digest_item(
            db,
            digest,
            item_type=ItemType.TWEET,
            item_ref_id=tweet.id,
            display_order=i + 1,
            snapshot_title=f"标题{i}",
            snapshot_translation=f"翻译{i}",
            snapshot_comment=f"点评{i}",
            snapshot_heat_score=100.0 - i * 10,
            snapshot_author_name=account.display_name,
            snapshot_author_handle=account.twitter_handle,
            snapshot_tweet_url=tweet.tweet_url,
        )
        items.append(item)

    if include_excluded:
        excl_tweet = await create_tweet(
            db,
            account,
            tweet_id="tw_excluded",
            is_processed=True,
            heat_score=10.0,
        )
        excl_item = await create_digest_item(
            db,
            digest,
            item_type=ItemType.TWEET,
            item_ref_id=excl_tweet.id,
            display_order=item_count + 1,
            is_excluded=True,
            snapshot_title="排除条目",
            snapshot_heat_score=10.0,
        )
        items.append(excl_item)

    await db.flush()
    return digest, items
