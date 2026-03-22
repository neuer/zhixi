"""Digest 编辑 API 测试 — US-031/032/033/034。"""

import json
from datetime import UTC, date, datetime

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.topic import Topic
from app.models.tweet import Tweet
from tests.factories import (
    create_account,
    create_digest,
    create_digest_item,
    create_topic,
    create_tweet,
    seed_config_keys,
)

DIGEST_DATE = date(2026, 3, 20)

TWEET_TIME = datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC)


# ── 辅助函数 ──


async def _setup_draft_with_tweet_item(
    db: AsyncSession,
    *,
    status: str = "draft",
) -> tuple[DailyDigest, DigestItem, Tweet]:
    """创建 config + account + tweet + digest + item 的完整组合。"""
    await seed_config_keys(db, top_n="10", min_articles="1")

    acct = await create_account(db, twitter_handle="karpathy", display_name="Andrej Karpathy")
    tweet = await create_tweet(
        db,
        acct,
        tweet_id="t_100",
        text="Original text",
        digest_date=DIGEST_DATE,
        tweet_time=TWEET_TIME,
        title="原始标题",
        translated_text="原始翻译",
        ai_comment="原始点评",
        is_processed=True,
    )

    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        status=status,
        summary="今日导读摘要",
        item_count=1,
        content_markdown="# 旧 Markdown",
    )

    item = await create_digest_item(
        db,
        digest,
        item_ref_id=tweet.id,
        snapshot_title="原始标题",
        snapshot_translation="原始翻译",
        snapshot_comment="原始点评",
        snapshot_heat_score=85.0,
        snapshot_author_name="Andrej Karpathy",
        snapshot_author_handle="karpathy",
        snapshot_tweet_url="https://x.com/karpathy/status/100",
        snapshot_tweet_time=TWEET_TIME,
    )
    return digest, item, tweet


async def _setup_draft_with_topic_item(
    db: AsyncSession,
    *,
    topic_type: str = "aggregated",
) -> tuple[DailyDigest, DigestItem, Topic]:
    """创建 config + topic + digest + item 的完整组合。"""
    await seed_config_keys(db, top_n="10", min_articles="1")

    perspectives_json = json.dumps(
        [{"author": "Sam", "handle": "sama", "viewpoint": "观点1"}],
        ensure_ascii=False,
    )
    topic = await create_topic(
        db,
        digest_date=DIGEST_DATE,
        topic_type=topic_type,
        title="话题标题",
        summary="话题摘要",
        perspectives=perspectives_json,
        ai_comment="AI 点评",
        heat_score=90.0,
    )

    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        summary="今日导读摘要",
        item_count=1,
        content_markdown="# 旧 Markdown",
    )

    extra_kwargs: dict[str, object] = {}
    if topic_type == "aggregated":
        extra_kwargs["snapshot_summary"] = "话题摘要"
        extra_kwargs["snapshot_perspectives"] = topic.perspectives
        extra_kwargs["snapshot_source_tweets"] = json.dumps(
            [{"handle": "sama", "tweet_url": "https://x.com/sama/status/1"}],
            ensure_ascii=False,
        )
    else:
        # thread
        extra_kwargs["snapshot_translation"] = "Thread 翻译"
        extra_kwargs["snapshot_author_name"] = "Sam Altman"
        extra_kwargs["snapshot_author_handle"] = "sama"

    item = await create_digest_item(
        db,
        digest,
        item_type="topic",
        item_ref_id=topic.id,
        snapshot_title="话题标题",
        snapshot_comment="AI 点评",
        snapshot_heat_score=90.0,
        snapshot_topic_type=topic_type,
        **extra_kwargs,
    )
    return digest, item, topic


async def _setup_draft_with_multiple_items(
    db: AsyncSession,
    count: int = 3,
) -> tuple[DailyDigest, list[DigestItem]]:
    """创建 config + account + tweets + digest + items 的完整组合。"""
    await seed_config_keys(db, top_n="10", min_articles="1")

    acct = await create_account(db)

    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        summary="今日导读",
        item_count=count,
        content_markdown="# 旧 Markdown",
    )

    items: list[DigestItem] = []
    for i in range(1, count + 1):
        tweet = await create_tweet(
            db,
            acct,
            tweet_id=f"tweet_multi_{i}",
            text=f"Text {i}",
            digest_date=DIGEST_DATE,
            tweet_time=TWEET_TIME,
            is_processed=True,
        )
        item = await create_digest_item(
            db,
            digest,
            item_ref_id=tweet.id,
            display_order=i,
            snapshot_title=f"标题{i}",
            snapshot_translation=f"翻译{i}",
            snapshot_comment=f"点评{i}",
            snapshot_heat_score=100.0 - i * 10,
            snapshot_author_name="Test User",
            snapshot_author_handle="testuser",
            snapshot_tweet_url=f"https://x.com/testuser/status/{i}",
            snapshot_tweet_time=TWEET_TIME,
        )
        items.append(item)

    return digest, items


# ── US-031: 编辑单条内容 ──


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_tweet_item(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """编辑 tweet 的 title/translation/comment → snapshot 更新 + Markdown 重渲染。"""
    digest, item, tweet = await _setup_draft_with_tweet_item(db)
    await db.commit()

    resp = await authed_client.put(
        f"/api/digest/item/tweet/{tweet.id}",
        json={"title": "新标题", "translation": "新翻译", "comment": "新点评"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["snapshot_title"] == "新标题"
    assert data["snapshot_translation"] == "新翻译"
    assert data["snapshot_comment"] == "新点评"

    # Markdown 应被重渲染
    await db.refresh(digest)
    assert digest.content_markdown is not None
    assert digest.content_markdown != "# 旧 Markdown"
    assert "新标题" in digest.content_markdown


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_aggregated_topic_item(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """编辑 aggregated topic 的 title/summary/perspectives/comment。"""
    digest, item, topic = await _setup_draft_with_topic_item(db, topic_type="aggregated")
    await db.commit()

    new_perspectives = json.dumps(
        [{"author": "Yann", "handle": "ylecun", "viewpoint": "新观点"}],
        ensure_ascii=False,
    )
    resp = await authed_client.put(
        f"/api/digest/item/topic/{topic.id}",
        json={
            "title": "新话题标题",
            "summary": "新话题摘要",
            "perspectives": new_perspectives,
            "comment": "新话题点评",
        },
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["snapshot_title"] == "新话题标题"
    assert data["snapshot_summary"] == "新话题摘要"
    assert data["snapshot_perspectives"] == new_perspectives
    assert data["snapshot_comment"] == "新话题点评"


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_thread_topic_item(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """编辑 thread 的 title/translation/comment。"""
    digest, item, topic = await _setup_draft_with_topic_item(db, topic_type="thread")
    await db.commit()

    resp = await authed_client.put(
        f"/api/digest/item/topic/{topic.id}",
        json={"title": "新 Thread 标题", "translation": "新 Thread 翻译", "comment": "新点评"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["snapshot_title"] == "新 Thread 标题"
    assert data["snapshot_translation"] == "新 Thread 翻译"
    assert data["snapshot_comment"] == "新点评"


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_item_partial_update(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """只传 title → 其他字段不变。"""
    digest, item, tweet = await _setup_draft_with_tweet_item(db)
    await db.commit()

    resp = await authed_client.put(
        f"/api/digest/item/tweet/{tweet.id}",
        json={"title": "仅更新标题"},
    )
    assert resp.status_code == 200

    data = resp.json()
    assert data["snapshot_title"] == "仅更新标题"
    assert data["snapshot_translation"] == "原始翻译"
    assert data["snapshot_comment"] == "原始点评"


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_item_not_found_404(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """不存在的条目 → 404。"""
    await _setup_draft_with_tweet_item(db)
    await db.commit()

    resp = await authed_client.put(
        "/api/digest/item/tweet/9999",
        json={"title": "新标题"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_item_published_409(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """已发布草稿 → 409。"""
    digest, item, tweet = await _setup_draft_with_tweet_item(db, status="published")
    await db.commit()

    resp = await authed_client.put(
        f"/api/digest/item/tweet/{tweet.id}",
        json={"title": "试图编辑已发布"},
    )
    assert resp.status_code == 409
    assert "不可编辑" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_edit_item_requires_auth_401(client: AsyncClient) -> None:
    """无 JWT → 401。"""
    resp = await client.put("/api/digest/item/tweet/1", json={"title": "x"})
    assert resp.status_code == 401


# ── US-032: 编辑导读摘要 ──


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_summary(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """更新 summary + Markdown 重渲染。"""
    digest, _, _ = await _setup_draft_with_tweet_item(db)
    await db.commit()

    resp = await authed_client.put(
        "/api/digest/summary",
        json={"summary": "全新导读摘要"},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "导读摘要已更新"

    await db.refresh(digest)
    assert digest.summary == "全新导读摘要"
    assert digest.content_markdown is not None
    assert "全新导读摘要" in digest.content_markdown


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_edit_summary_published_409(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """已发布 → 409。"""
    await _setup_draft_with_tweet_item(db, status="published")
    await db.commit()

    resp = await authed_client.put(
        "/api/digest/summary",
        json={"summary": "试图修改"},
    )
    assert resp.status_code == 409


# ── US-033: 调整排序与置顶 ──


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_reorder_items(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """更新 display_order 和 is_pinned。"""
    digest, items = await _setup_draft_with_multiple_items(db, count=3)
    await db.commit()

    # 反转排序，置顶第三条
    reorder_data = [
        {"id": items[2].id, "display_order": 0, "is_pinned": True},
        {"id": items[0].id, "display_order": 1, "is_pinned": False},
        {"id": items[1].id, "display_order": 2, "is_pinned": False},
    ]
    resp = await authed_client.put(
        "/api/digest/reorder",
        json={"items": reorder_data},
    )
    assert resp.status_code == 200
    assert resp.json()["message"] == "排序已更新"

    # 验证 DB 更新
    for item in items:
        await db.refresh(item)
    assert items[2].display_order == 0
    assert items[2].is_pinned is True
    assert items[0].display_order == 1
    assert items[1].display_order == 2


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_reorder_rerenders_markdown(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """排序后 Markdown 被重渲染。"""
    digest, items = await _setup_draft_with_multiple_items(db, count=2)
    await db.commit()

    reorder_data = [
        {"id": items[1].id, "display_order": 0, "is_pinned": False},
        {"id": items[0].id, "display_order": 1, "is_pinned": False},
    ]
    resp = await authed_client.put(
        "/api/digest/reorder",
        json={"items": reorder_data},
    )
    assert resp.status_code == 200

    await db.refresh(digest)
    assert digest.content_markdown != "# 旧 Markdown"


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_reorder_invalid_item_404(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """不属于当前 digest 的 item → 404。"""
    await _setup_draft_with_multiple_items(db, count=1)
    await db.commit()

    resp = await authed_client.put(
        "/api/digest/reorder",
        json={"items": [{"id": 9999, "display_order": 0, "is_pinned": False}]},
    )
    assert resp.status_code == 404


# ── US-034: 剔除与恢复条目 ──


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_exclude_item(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """is_excluded=True + Markdown 重渲染。"""
    digest, item, tweet = await _setup_draft_with_tweet_item(db)
    await db.commit()

    resp = await authed_client.post(f"/api/digest/exclude/tweet/{tweet.id}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "条目已剔除"

    await db.refresh(item)
    assert item.is_excluded is True

    # Markdown 应更新
    await db.refresh(digest)
    assert digest.content_markdown != "# 旧 Markdown"


@pytest.mark.asyncio
@freeze_time("2026-03-20 08:00:00+08:00")
async def test_restore_item(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """is_excluded=False, display_order=max+1。"""
    digest, items = await _setup_draft_with_multiple_items(db, count=3)
    # 先剔除第一条
    items[0].is_excluded = True
    await db.commit()

    # 通过 item_ref_id (tweet.id) 来恢复
    tweet_id = items[0].item_ref_id
    resp = await authed_client.post(f"/api/digest/restore/tweet/{tweet_id}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "条目已恢复"

    await db.refresh(items[0])
    assert items[0].is_excluded is False
    # display_order 应为 max(非 excluded) + 1
    max_order = max(i.display_order for i in items[1:])
    assert items[0].display_order == max_order + 1


@pytest.mark.asyncio
async def test_exclude_restore_requires_auth_401(client: AsyncClient) -> None:
    """无 JWT → 401。"""
    resp = await client.post("/api/digest/exclude/tweet/1")
    assert resp.status_code == 401

    resp = await client.post("/api/digest/restore/tweet/1")
    assert resp.status_code == 401
