"""US-038 预览功能 API 测试。"""

from datetime import UTC, date, datetime
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.account import TwitterAccount
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.tweet import Tweet

DIGEST_DATE = date(2026, 3, 20)


# ── 辅助函数 ──


async def _seed_digest_with_items(
    db: AsyncSession,
    item_count: int = 2,
    *,
    include_excluded: bool = False,
) -> DailyDigest:
    """创建 DailyDigest + N 条 DigestItem。"""
    digest = DailyDigest(
        digest_date=DIGEST_DATE,
        version=1,
        is_current=True,
        status="draft",
        summary="今日摘要",
        item_count=item_count,
        content_markdown="# 智曦日报\n\n测试内容",
    )
    db.add(digest)
    await db.flush()

    acct = TwitterAccount(
        twitter_handle="testuser",
        display_name="Test User",
    )
    db.add(acct)
    await db.flush()

    for i in range(1, item_count + 1):
        tweet = Tweet(
            tweet_id=f"preview_tweet_{i}",
            account_id=acct.id,
            digest_date=DIGEST_DATE,
            original_text=f"Test tweet {i}",
            tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
            is_ai_relevant=True,
            is_processed=True,
        )
        db.add(tweet)
        await db.flush()

        item = DigestItem(
            digest_id=digest.id,
            item_type="tweet",
            item_ref_id=tweet.id,
            display_order=i,
            is_excluded=(include_excluded and i == item_count),
            snapshot_title=f"标题{i}",
            snapshot_translation=f"翻译{i}",
            snapshot_comment=f"点评{i}",
            snapshot_heat_score=100.0 - i * 10,
            snapshot_author_name="Test User",
            snapshot_author_handle="testuser",
            snapshot_tweet_url=f"https://x.com/testuser/status/{i}",
            snapshot_tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        )
        db.add(item)

    await db.flush()
    return digest


# ── 测试 ──


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_preview_returns_digest_with_items(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """有 current digest 时返回完整预览数据。"""
    await _seed_digest_with_items(db, item_count=3)
    await db.commit()

    resp = await authed_client.get("/api/digest/preview")
    assert resp.status_code == 200

    data = resp.json()
    assert data["digest"]["status"] == "draft"
    assert data["digest"]["summary"] == "今日摘要"
    assert len(data["items"]) == 3
    assert data["content_markdown"] == "# 智曦日报\n\n测试内容"
    # items 按 display_order 排序
    orders = [item["display_order"] for item in data["items"]]
    assert orders == sorted(orders)


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_preview_no_digest_returns_404(
    _mock_date: object,
    authed_client: AsyncClient,
) -> None:
    """无 current digest 时返回 404。"""
    resp = await authed_client.get("/api/digest/preview")
    assert resp.status_code == 404


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_preview_requires_auth(
    _mock_date: object,
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
            resp = await client.get("/api/digest/preview")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_preview_includes_excluded_items(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """预览 API 返回所有条目（含 excluded），前端过滤。"""
    await _seed_digest_with_items(db, item_count=3, include_excluded=True)
    await db.commit()

    resp = await authed_client.get("/api/digest/preview")
    assert resp.status_code == 200

    data = resp.json()
    # API 返回全部条目，前端根据 is_excluded 过滤
    assert len(data["items"]) == 3
