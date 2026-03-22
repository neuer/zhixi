"""DigestService.regenerate_digest() 单元测试（US-035）。"""

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeClient
from app.models.digest_item import DigestItem
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse
from app.services.digest_service import DigestService
from tests.factories import create_account, create_digest, create_topic, create_tweet

DIGEST_DATE = date(2026, 3, 20)

TWEET_TIME = datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC)

# create_tweet 的公共默认参数，匹配原 _seed_tweet 行为
_TW: dict[str, Any] = dict(
    digest_date=DIGEST_DATE,
    tweet_time=TWEET_TIME,
    is_processed=True,
    ai_importance_score=70.0,
    base_heat_score=60.0,
    title="标题",
    translated_text="翻译",
    ai_comment="点评",
)


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
    acct = await create_account(db)
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
    await create_tweet(db, acct, **_TW, tweet_id="tw2", heat_score=70.0)
    old_digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        version=1,
        status="draft",
        summary="旧版本摘要",
        item_count=2,
        content_markdown="# 旧版本",
    )
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
    acct = await create_account(db)
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
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
    acct = await create_account(db)
    topic = await create_topic(db, digest_date=DIGEST_DATE)
    tw1 = await create_tweet(db, acct, **_TW, tweet_id="tw1", topic_id=topic.id)
    tw2 = await create_tweet(db, acct, **{**_TW, "is_ai_relevant": False}, tweet_id="tw2")
    await create_digest(
        db, digest_date=DIGEST_DATE, summary="旧版本摘要", item_count=2, content_markdown="# 旧版本"
    )
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
    acct = await create_account(db)
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
    old_digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        version=1,
        status="published",
        summary="旧版本摘要",
        item_count=2,
        content_markdown="# 旧版本",
    )
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
    acct = await create_account(db)
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
    old_digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        version=1,
        status="failed",
        summary="旧版本摘要",
        item_count=2,
        content_markdown="# 旧版本",
    )
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
    acct = await create_account(db)
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
    old_digest = await create_digest(
        db, digest_date=DIGEST_DATE, summary="旧版本摘要", item_count=2, content_markdown="# 旧版本"
    )
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
    acct = await create_account(db)
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
    old_digest = await create_digest(
        db, digest_date=DIGEST_DATE, summary="旧版本摘要", item_count=2, content_markdown="# 旧版本"
    )

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
    acct = await create_account(db)
    # 创建旧 topic（regenerate 后其成员推文 topic_id 已指向新 topic）
    old_topic = await create_topic(db, digest_date=DIGEST_DATE, heat_score=90.0)
    # 独立推文（无 topic_id）
    await create_tweet(db, acct, **_TW, tweet_id="tw1", heat_score=80.0)
    await create_digest(
        db, digest_date=DIGEST_DATE, summary="旧版本摘要", item_count=2, content_markdown="# 旧版本"
    )
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
