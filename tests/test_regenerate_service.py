"""DigestService.regenerate_digest() 单元测试（US-035）。"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeClient
from app.models.account import TwitterAccount
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.topic import Topic
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse
from app.services.digest_service import DigestService

DIGEST_DATE = date(2026, 3, 20)


# ──────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────


def _mock_claude_response(content: str = "摘要") -> ClaudeResponse:
    return ClaudeResponse(
        content=content,
        input_tokens=200,
        output_tokens=80,
        model="claude-sonnet-4-20250514",
        duration_ms=1500,
        estimated_cost=0.0018,
    )


def _make_service(db: AsyncSession) -> DigestService:
    """构造带 mock ClaudeClient 的 DigestService。"""
    client = AsyncMock(spec=ClaudeClient)
    client.complete = AsyncMock(return_value=_mock_claude_response())
    return DigestService(db, claude_client=client)


async def _seed_account(db: AsyncSession, handle: str = "testuser") -> TwitterAccount:
    account = TwitterAccount(
        twitter_handle=handle,
        display_name="Test User",
        bio="AI researcher",
        weight=1.0,
        is_active=True,
    )
    db.add(account)
    await db.flush()
    return account


async def _seed_tweet(
    db: AsyncSession,
    account: TwitterAccount,
    tweet_id: str = "t1",
    *,
    heat_score: float = 50.0,
    topic_id: int | None = None,
    is_ai_relevant: bool = True,
    is_processed: bool = True,
) -> Tweet:
    tweet = Tweet(
        tweet_id=tweet_id,
        account_id=account.id,
        digest_date=DIGEST_DATE,
        original_text=f"Original {tweet_id}",
        tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        likes=100,
        retweets=20,
        replies=10,
        tweet_url=f"https://x.com/{account.twitter_handle}/status/{tweet_id}",
        source="auto",
        title="标题",
        translated_text="翻译",
        ai_comment="点评",
        heat_score=heat_score,
        ai_importance_score=70.0,
        base_heat_score=60.0,
        is_ai_relevant=is_ai_relevant,
        is_processed=is_processed,
        topic_id=topic_id,
    )
    db.add(tweet)
    await db.flush()
    return tweet


async def _seed_topic(
    db: AsyncSession,
    topic_type: str = "aggregated",
    heat_score: float = 60.0,
) -> Topic:
    topic = Topic(
        digest_date=DIGEST_DATE,
        type=topic_type,
        title="话题标题",
        summary="话题摘要",
        ai_comment="话题点评",
        heat_score=heat_score,
        ai_importance_score=80.0,
        tweet_count=2,
    )
    db.add(topic)
    await db.flush()
    return topic


async def _seed_draft(
    db: AsyncSession,
    version: int = 1,
    status: str = "draft",
    item_count: int = 2,
) -> DailyDigest:
    """创建 v{version} 草稿 + items。"""
    digest = DailyDigest(
        digest_date=DIGEST_DATE,
        version=version,
        is_current=True,
        status=status,
        summary="旧版本摘要",
        item_count=item_count,
        content_markdown="# 旧版本",
    )
    db.add(digest)
    await db.flush()
    return digest


def _make_mock_process_class(db: AsyncSession) -> type:
    """创建 Mock ProcessService 类：run_daily_process 模拟恢复推文处理状态。"""

    class MockProcessService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def run_daily_process(self, digest_date: date) -> object:
            """模拟 M2：标记推文为已处理。"""
            stmt = (
                update(Tweet)
                .where(Tweet.digest_date == digest_date)
                .values(is_processed=True, is_ai_relevant=True)
            )
            await db.execute(stmt)
            return AsyncMock(processed_count=2, filtered_count=0, topic_count=0)

    return MockProcessService


# ──────────────────────────────────────────────────
# 测试
# ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_regenerate_creates_new_version(db: AsyncSession) -> None:
    """v1 draft → regenerate → v2 draft, is_current 切换正确。"""
    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    await _seed_tweet(db, acct, "tw2", heat_score=70.0)
    old_digest = await _seed_draft(db, version=1)
    await db.commit()

    svc = _make_service(db)
    mock_cls = _make_mock_process_class(db)

    with patch("app.services.process_service.ProcessService", mock_cls):
        new_digest = await svc.regenerate_digest(DIGEST_DATE)

    # 新版本
    assert new_digest.version == 2
    assert new_digest.is_current is True
    assert new_digest.status == "draft"

    # 旧版本 is_current=false
    await db.refresh(old_digest)
    assert old_digest.is_current is False


@pytest.mark.asyncio
async def test_regenerate_no_existing_digest(db: AsyncSession) -> None:
    """当日无草稿 → 等价于首次生成 v1。"""
    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    await db.commit()

    svc = _make_service(db)
    mock_cls = _make_mock_process_class(db)

    with patch("app.services.process_service.ProcessService", mock_cls):
        digest = await svc.regenerate_digest(DIGEST_DATE)

    assert digest.version == 1
    assert digest.is_current is True
    assert digest.status == "draft"


@pytest.mark.asyncio
async def test_regenerate_resets_tweets(db: AsyncSession) -> None:
    """重置推文 is_processed/is_ai_relevant/topic_id。"""
    acct = await _seed_account(db)
    topic = await _seed_topic(db)
    tw1 = await _seed_tweet(db, acct, "tw1", is_processed=True, topic_id=topic.id)
    tw2 = await _seed_tweet(db, acct, "tw2", is_processed=True, is_ai_relevant=False)
    await _seed_draft(db)
    await db.commit()

    svc = _make_service(db)

    # 用一个 mock 在 run_daily_process 前检查推文状态
    reset_observed = {}

    class CheckResetProcessService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def run_daily_process(self, digest_date: date) -> object:
            # 此时推文应已被重置
            await db.refresh(tw1)
            await db.refresh(tw2)
            reset_observed["tw1_processed"] = tw1.is_processed
            reset_observed["tw1_ai_relevant"] = tw1.is_ai_relevant
            reset_observed["tw1_topic_id"] = tw1.topic_id
            reset_observed["tw2_ai_relevant"] = tw2.is_ai_relevant
            # 模拟处理完成
            stmt = (
                update(Tweet)
                .where(Tweet.digest_date == digest_date)
                .values(is_processed=True, is_ai_relevant=True)
            )
            await db.execute(stmt)
            return AsyncMock()

    with patch("app.services.process_service.ProcessService", CheckResetProcessService):
        await svc.regenerate_digest(DIGEST_DATE)

    assert reset_observed["tw1_processed"] is False
    assert reset_observed["tw1_ai_relevant"] is True
    assert reset_observed["tw1_topic_id"] is None
    assert reset_observed["tw2_ai_relevant"] is True


@pytest.mark.asyncio
async def test_regenerate_from_published(db: AsyncSession) -> None:
    """published v1 → regenerate → draft v2。"""
    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    old_digest = await _seed_draft(db, version=1, status="published")
    await db.commit()

    svc = _make_service(db)
    mock_cls = _make_mock_process_class(db)

    with patch("app.services.process_service.ProcessService", mock_cls):
        new_digest = await svc.regenerate_digest(DIGEST_DATE)

    assert new_digest.version == 2
    assert new_digest.status == "draft"
    await db.refresh(old_digest)
    assert old_digest.is_current is False
    assert old_digest.status == "published"  # 旧状态不变


@pytest.mark.asyncio
async def test_regenerate_from_failed(db: AsyncSession) -> None:
    """failed v1 → regenerate → draft v2。"""
    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    old_digest = await _seed_draft(db, version=1, status="failed")
    await db.commit()

    svc = _make_service(db)
    mock_cls = _make_mock_process_class(db)

    with patch("app.services.process_service.ProcessService", mock_cls):
        new_digest = await svc.regenerate_digest(DIGEST_DATE)

    assert new_digest.version == 2
    assert new_digest.status == "draft"
    await db.refresh(old_digest)
    assert old_digest.is_current is False


@pytest.mark.asyncio
async def test_regenerate_rollback_on_failure(db: AsyncSession) -> None:
    """M3 失败时旧版本 is_current 恢复为 true。"""
    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    old_digest = await _seed_draft(db, version=1)
    await db.commit()

    svc = _make_service(db)

    class FailingProcessService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

        async def run_daily_process(self, digest_date: date) -> object:
            msg = "M2 processing error"
            raise RuntimeError(msg)

    with (
        patch("app.services.process_service.ProcessService", FailingProcessService),
        pytest.raises(RuntimeError, match="M2 processing error"),
    ):
        await svc.regenerate_digest(DIGEST_DATE)

    # 回滚：旧版本 is_current 恢复
    await db.refresh(old_digest)
    assert old_digest.is_current is True


@pytest.mark.asyncio
async def test_regenerate_old_items_preserved(db: AsyncSession) -> None:
    """旧版本 digest_items 快照在 regenerate 后不受影响。"""
    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    old_digest = await _seed_draft(db, version=1)

    # 创建旧版本的 item
    old_item = DigestItem(
        digest_id=old_digest.id,
        item_type="tweet",
        item_ref_id=1,
        display_order=1,
        snapshot_title="旧标题",
        snapshot_heat_score=80.0,
    )
    db.add(old_item)
    await db.commit()

    svc = _make_service(db)
    mock_cls = _make_mock_process_class(db)

    with patch("app.services.process_service.ProcessService", mock_cls):
        await svc.regenerate_digest(DIGEST_DATE)

    # 旧 items 不变
    await db.refresh(old_item)
    assert old_item.snapshot_title == "旧标题"
    assert old_item.snapshot_heat_score == 80.0


@pytest.mark.asyncio
async def test_regenerate_skips_stale_topics(db: AsyncSession) -> None:
    """旧 topics 无成员推文时不产生空 digest_item。"""
    acct = await _seed_account(db)
    # 创建旧 topic（regenerate 后其成员推文 topic_id 已指向新 topic）
    old_topic = await _seed_topic(db, heat_score=90.0)
    # 独立推文（无 topic_id）
    await _seed_tweet(db, acct, "tw1", heat_score=80.0)
    await _seed_draft(db, version=1)
    await db.commit()

    svc = _make_service(db)
    mock_cls = _make_mock_process_class(db)

    with patch("app.services.process_service.ProcessService", mock_cls):
        new_digest = await svc.regenerate_digest(DIGEST_DATE)

    # 查询新版本的 items — 不应包含旧 topic 的 item
    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == new_digest.id))
    items = list(items_result.scalars().all())
    topic_items = [it for it in items if it.item_type == "topic" and it.item_ref_id == old_topic.id]
    assert len(topic_items) == 0
