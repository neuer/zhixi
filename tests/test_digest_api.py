"""Digest API 测试 — US-030 查看今日内容列表。"""

from datetime import UTC, date, datetime
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig
from app.models.digest import DailyDigest
from tests.factories import (
    create_account,
    create_digest,
    create_digest_item,
    create_tweet,
    seed_config_keys,
)

DIGEST_DATE = date(2026, 3, 20)


# ── 辅助函数 ──


async def _seed_digest_with_items(
    db: AsyncSession,
    item_count: int = 2,
    digest_date: date = DIGEST_DATE,
) -> DailyDigest:
    """创建 DailyDigest + N 条 DigestItem。"""
    digest = await create_digest(
        db,
        digest_date=digest_date,
        summary="今日摘要",
        item_count=item_count,
        content_markdown="# 测试 Markdown",
    )

    acct = await create_account(db, twitter_handle="testuser", display_name="Test User")

    for i in range(1, item_count + 1):
        tweet = await create_tweet(
            db,
            acct,
            tweet_id=f"tweet_{i}",
            digest_date=digest_date,
            text=f"Test tweet {i}",
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
            snapshot_heat_score=100.0 - i * 10,
            snapshot_author_name="Test User",
            snapshot_author_handle="testuser",
            snapshot_tweet_url=f"https://x.com/testuser/status/{i}",
            snapshot_tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        )

    return digest


# ── 测试 ──


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_today_with_data(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """有草稿时返回 digest + items。"""
    await seed_config_keys(db, top_n="10", min_articles="3")
    await _seed_digest_with_items(db, item_count=3)
    await db.commit()

    resp = await authed_client.get("/api/digest/today")
    assert resp.status_code == 200

    data = resp.json()
    assert data["digest"] is not None
    assert data["digest"]["status"] == "draft"
    assert data["digest"]["summary"] == "今日摘要"
    assert len(data["items"]) == 3
    assert data["low_content_warning"] is False


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_today_no_data(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """无草稿时返回 null digest。"""
    await seed_config_keys(db, top_n="10", min_articles="3")
    await db.commit()

    resp = await authed_client.get("/api/digest/today")
    assert resp.status_code == 200

    data = resp.json()
    assert data["digest"] is None
    assert data["items"] == []
    assert data["low_content_warning"] is False


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_today_items_sorted_by_display_order(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """items 按 display_order 排序。"""
    await seed_config_keys(db, top_n="10", min_articles="3")
    await _seed_digest_with_items(db, item_count=3)
    await db.commit()

    resp = await authed_client.get("/api/digest/today")
    data = resp.json()
    orders = [item["display_order"] for item in data["items"]]
    assert orders == sorted(orders)


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_today_low_content_warning(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """item_count < min_articles 时 warning=true。"""
    await seed_config_keys(db, top_n="10", min_articles="3")  # min_articles=3
    await _seed_digest_with_items(db, item_count=2)  # 只有 2 条
    await db.commit()

    resp = await authed_client.get("/api/digest/today")
    data = resp.json()
    assert data["low_content_warning"] is True


@pytest.mark.asyncio
async def test_today_requires_auth(client: AsyncClient) -> None:
    """无 JWT 返回 401。"""
    resp = await client.get("/api/digest/today")
    assert resp.status_code == 401


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_today_shows_summary_degraded(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """导读摘要降级时 summary_degraded=True。"""
    from app.digest.summary_prompts import DEFAULT_SUMMARY

    await seed_config_keys(db, top_n="10", min_articles="3")
    digest = await _seed_digest_with_items(db, item_count=2)
    digest.summary = DEFAULT_SUMMARY
    await db.commit()

    resp = await authed_client.get("/api/digest/today")
    data = resp.json()
    assert data["digest"]["summary_degraded"] is True


@pytest.mark.asyncio
@patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE)
async def test_today_cover_failed(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """封面图开启但未生成时 cover_failed=True。"""
    await seed_config_keys(db, top_n="10", min_articles="3")
    db.add(SystemConfig(key="enable_cover_generation", value="true"))
    await _seed_digest_with_items(db, item_count=2)
    await db.commit()

    resp = await authed_client.get("/api/digest/today")
    data = resp.json()
    assert data["cover_failed"] is True
