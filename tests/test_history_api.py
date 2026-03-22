"""US-042 推送历史 API 测试。"""

from datetime import UTC, date, datetime

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.account import TwitterAccount
from app.models.digest import DailyDigest
from tests.factories import (
    create_account,
    create_digest,
    create_digest_item,
    create_tweet,
)

# ── 辅助函数 ──


async def _seed_account(db: AsyncSession) -> TwitterAccount:
    """创建测试账号。"""
    return await create_account(db, twitter_handle="histuser", display_name="Hist User")


async def _seed_digest(
    db: AsyncSession,
    acct: TwitterAccount,
    digest_date: date,
    *,
    version: int = 1,
    is_current: bool = True,
    status: str = "draft",
    item_count: int = 2,
) -> DailyDigest:
    """创建 DailyDigest + items。"""
    digest = await create_digest(
        db,
        digest_date=digest_date,
        version=version,
        is_current=is_current,
        status=status,
        summary=f"{digest_date} 摘要",
        item_count=item_count,
        content_markdown=f"# {digest_date}",
        published_at=datetime.now(UTC) if status == "published" else None,
    )

    for i in range(1, item_count + 1):
        tweet = await create_tweet(
            db,
            acct,
            tweet_id=f"hist_{digest_date}_{version}_{i}",
            digest_date=digest_date,
            text=f"Tweet {i}",
            tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
            is_ai_relevant=True,
            is_processed=True,
        )
        await create_digest_item(
            db,
            digest,
            item_ref_id=tweet.id,
            display_order=i,
            snapshot_title=f"标题{i}",
            snapshot_translation=f"翻译{i}",
            snapshot_comment=f"点评{i}",
            snapshot_heat_score=90.0 - i * 10,
            snapshot_author_name="Hist User",
            snapshot_author_handle="histuser",
            snapshot_tweet_url=f"https://x.com/histuser/status/{i}",
            snapshot_tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        )

    return digest


# ── GET /api/history 列表测试 ──


@pytest.mark.asyncio
async def test_history_list_returns_paginated(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """返回分页历史列表。"""
    acct = await _seed_account(db)
    for i in range(3):
        d = date(2026, 3, 18 + i)
        await _seed_digest(db, acct, d, status="published")
    await db.commit()

    resp = await authed_client.get("/api/history?page=1&page_size=2")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 3
    assert data["page"] == 1
    assert data["page_size"] == 2
    assert len(data["items"]) == 2
    # 按日期降序
    dates = [item["digest_date"] for item in data["items"]]
    assert dates == sorted(dates, reverse=True)


@pytest.mark.asyncio
async def test_history_list_one_per_date(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """每日期只返回一条记录。"""
    acct = await _seed_account(db)
    d = date(2026, 3, 20)
    await _seed_digest(db, acct, d, version=1, is_current=False, status="draft")
    await _seed_digest(db, acct, d, version=2, is_current=True, status="draft")
    await db.commit()

    resp = await authed_client.get("/api/history")
    assert resp.status_code == 200

    data = resp.json()
    assert data["total"] == 1
    assert len(data["items"]) == 1


@pytest.mark.asyncio
async def test_history_version_priority_published(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """published 版本优先于 is_current。"""
    acct = await _seed_account(db)
    d = date(2026, 3, 20)
    # v1 已发布, v2 是 current draft
    pub = await _seed_digest(db, acct, d, version=1, is_current=False, status="published")
    await _seed_digest(db, acct, d, version=2, is_current=True, status="draft")
    await db.commit()

    resp = await authed_client.get("/api/history")
    data = resp.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["version"] == pub.version
    assert data["items"][0]["status"] == "published"


@pytest.mark.asyncio
async def test_history_version_priority_current(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """无 published 时 is_current=true 优先。"""
    acct = await _seed_account(db)
    d = date(2026, 3, 20)
    await _seed_digest(db, acct, d, version=1, is_current=False, status="draft")
    current = await _seed_digest(db, acct, d, version=2, is_current=True, status="draft")
    await db.commit()

    resp = await authed_client.get("/api/history")
    data = resp.json()
    assert data["items"][0]["version"] == current.version


@pytest.mark.asyncio
async def test_history_version_priority_max_version(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """都不满足时取 version 最大的记录。"""
    acct = await _seed_account(db)
    d = date(2026, 3, 20)
    await _seed_digest(db, acct, d, version=1, is_current=False, status="draft")
    v3 = await _seed_digest(db, acct, d, version=3, is_current=False, status="failed")
    await db.commit()

    resp = await authed_client.get("/api/history")
    data = resp.json()
    assert data["items"][0]["version"] == v3.version


# ── GET /api/history/{id} 详情测试 ──


@pytest.mark.asyncio
async def test_history_detail_returns_items(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """返回完整 digest + items 快照。"""
    acct = await _seed_account(db)
    digest = await _seed_digest(db, acct, date(2026, 3, 20), item_count=3)
    await db.commit()

    resp = await authed_client.get(f"/api/history/{digest.id}")
    assert resp.status_code == 200

    data = resp.json()
    assert data["digest"]["id"] == digest.id
    assert data["digest"]["version"] == 1
    assert len(data["items"]) == 3
    # 按 display_order 排序
    orders = [item["display_order"] for item in data["items"]]
    assert orders == sorted(orders)


@pytest.mark.asyncio
async def test_history_detail_not_found(
    authed_client: AsyncClient,
) -> None:
    """id 不存在返回 404。"""
    resp = await authed_client.get("/api/history/99999")
    assert resp.status_code == 404


# ── 认证测试 ──


@pytest.mark.asyncio
async def test_history_requires_auth(
    db: AsyncSession,
) -> None:
    """无 JWT 返回 401。"""
    from app.database import get_db

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp_list = await client.get("/api/history")
            resp_detail = await client.get("/api/history/1")
        assert resp_list.status_code == 401
        assert resp_detail.status_code == 401
    finally:
        app.dependency_overrides.clear()
