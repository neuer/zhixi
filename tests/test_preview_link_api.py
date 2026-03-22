"""US-009 预览签名链接 API 测试。"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.digest import DailyDigest
from tests.factories import (
    create_account,
    create_digest,
    create_digest_item,
    create_tweet,
)

DIGEST_DATE = date(2026, 3, 20)


# ── 辅助函数 ──


async def _seed_digest_with_items(
    db: AsyncSession,
    item_count: int = 2,
    *,
    include_excluded: bool = False,
) -> DailyDigest:
    """创建 DailyDigest + N 条 DigestItem。"""
    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        summary="今日摘要",
        item_count=item_count,
        content_markdown="# 智曦日报\n\n测试内容",
    )

    acct = await create_account(db, twitter_handle="testuser", display_name="Test User")

    for i in range(1, item_count + 1):
        tweet = await create_tweet(
            db,
            acct,
            tweet_id=f"preview_link_tweet_{i}",
            digest_date=DIGEST_DATE,
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

    return digest


# ── POST /preview-link 测试 ──


@pytest.mark.asyncio
@patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE)
async def test_create_preview_link_success(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """有 current digest 时成功生成 token，DB 字段已写入。"""
    digest = await _seed_digest_with_items(db)
    await db.commit()

    resp = await authed_client.post("/api/digest/preview-link")
    assert resp.status_code == 200

    data = resp.json()
    assert "token" in data
    assert "expires_at" in data
    assert len(data["token"]) > 20  # token_urlsafe(32) 产出约 43 字符

    # 验证 DB 字段已写入
    result = await db.execute(select(DailyDigest).where(DailyDigest.id == digest.id))
    updated = result.scalar_one()
    assert updated.preview_token == data["token"]
    assert updated.preview_expires_at is not None


@pytest.mark.asyncio
@patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE)
async def test_create_preview_link_no_digest_404(
    _mock_date: object,
    authed_client: AsyncClient,
) -> None:
    """无 current digest 时返回 404。"""
    resp = await authed_client.post("/api/digest/preview-link")
    assert resp.status_code == 404


@pytest.mark.asyncio
@patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE)
async def test_create_preview_link_requires_auth(
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
            resp = await client.post("/api/digest/preview-link")
        assert resp.status_code == 401
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
@patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE)
async def test_create_preview_link_overwrites_old(
    _mock_date: object,
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """生成新 token 覆盖旧 token。"""
    digest = await _seed_digest_with_items(db)
    # 预设旧 token
    digest.preview_token = "old-token-12345"
    digest.preview_expires_at = datetime.now(UTC) + timedelta(hours=12)
    await db.commit()

    resp = await authed_client.post("/api/digest/preview-link")
    assert resp.status_code == 200

    new_token = resp.json()["token"]
    assert new_token != "old-token-12345"

    # DB 中旧 token 已被覆盖
    result = await db.execute(select(DailyDigest).where(DailyDigest.id == digest.id))
    updated = result.scalar_one()
    assert updated.preview_token == new_token


# ── GET /preview/{token} 测试 ──


@pytest.mark.asyncio
async def test_preview_by_token_success(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """有效 token 返回完整预览数据。"""
    digest = await _seed_digest_with_items(db, item_count=3)
    digest.preview_token = "valid-test-token"
    digest.preview_expires_at = datetime.now(UTC) + timedelta(hours=24)
    await db.commit()

    resp = await client.get("/api/digest/preview/valid-test-token")
    assert resp.status_code == 200

    data = resp.json()
    assert data["digest"]["status"] == "draft"
    assert data["digest"]["summary"] == "今日摘要"
    assert len(data["items"]) == 3
    assert data["content_markdown"] == "# 智曦日报\n\n测试内容"


@pytest.mark.asyncio
async def test_preview_by_token_invalid_403(
    client: AsyncClient,
) -> None:
    """不存在的 token 返回 403。"""
    resp = await client.get("/api/digest/preview/nonexistent-token")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "链接已失效或过期"


@pytest.mark.asyncio
async def test_preview_by_token_expired_403(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """过期 token 返回 403。"""
    digest = await _seed_digest_with_items(db)
    digest.preview_token = "expired-test-token"
    digest.preview_expires_at = datetime(2026, 3, 19, 0, 0, 0, tzinfo=UTC)
    await db.commit()

    resp = await client.get("/api/digest/preview/expired-test-token")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "链接已失效或过期"


@pytest.mark.asyncio
async def test_preview_by_token_not_current_403(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """token 对应的 digest is_current=False 时返回 403。"""
    digest = await _seed_digest_with_items(db)
    digest.preview_token = "stale-token"
    digest.preview_expires_at = datetime.now(UTC) + timedelta(hours=24)
    digest.is_current = False
    await db.commit()

    resp = await client.get("/api/digest/preview/stale-token")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "链接已失效或过期"


@pytest.mark.asyncio
async def test_preview_by_token_no_auth_required(
    db: AsyncSession,
) -> None:
    """不带 JWT 也能正常访问 token 预览。"""
    from app.database import get_db

    digest = await _seed_digest_with_items(db)
    digest.preview_token = "no-auth-token"
    digest.preview_expires_at = datetime.now(UTC) + timedelta(hours=24)
    await db.commit()

    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://test") as anon:
            resp = await anon.get("/api/digest/preview/no-auth-token")
        assert resp.status_code == 200
        assert resp.json()["digest"]["summary"] == "今日摘要"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_preview_by_token_includes_excluded(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """token 预览返回全部条目（含 excluded）。"""
    digest = await _seed_digest_with_items(db, item_count=3, include_excluded=True)
    digest.preview_token = "excluded-test-token"
    digest.preview_expires_at = datetime.now(UTC) + timedelta(hours=24)
    await db.commit()

    resp = await client.get("/api/digest/preview/excluded-test-token")
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == 3


@pytest.mark.asyncio
async def test_regenerate_invalidates_old_token(
    client: AsyncClient,
    db: AsyncSession,
) -> None:
    """regenerate 后旧版本 is_current=False，旧 token 自动失效。"""
    digest = await _seed_digest_with_items(db)
    digest.preview_token = "old-version-token"
    digest.preview_expires_at = datetime.now(UTC) + timedelta(hours=24)
    await db.commit()

    # 模拟 regenerate：旧版本 is_current=False
    digest.is_current = False
    await db.commit()

    resp = await client.get("/api/digest/preview/old-version-token")
    assert resp.status_code == 403
    assert resp.json()["detail"] == "链接已失效或过期"
