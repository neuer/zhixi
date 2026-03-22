"""Settings API 测试 — US-041。"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun
from tests.factories import create_system_config

# ── 认证 ──


@pytest.mark.asyncio
async def test_settings_requires_auth(client: AsyncClient) -> None:
    """未认证 → 401。"""
    resp = await client.get("/api/settings")
    assert resp.status_code == 401

    resp = await client.put("/api/settings", json={"top_n": 5})
    assert resp.status_code == 401


# ── GET /api/settings ──


@pytest.mark.asyncio
async def test_get_settings(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """返回全部配置（push_days 为整数数组）。"""
    await create_system_config(db, admin_password_hash="$2b$12$test")
    await db.commit()

    with patch("app.api.settings._get_db_size_mb", return_value=1.5):
        resp = await authed_client.get("/api/settings")
    assert resp.status_code == 200

    data = resp.json()
    assert data["push_time"] == "08:00"
    assert data["push_days"] == [1, 2, 3, 4, 5, 6, 7]
    assert data["top_n"] == 10
    assert data["min_articles"] == 1
    assert data["publish_mode"] == "manual"
    assert data["enable_cover_generation"] is False
    assert data["cover_generation_timeout"] == 30
    assert data["notification_webhook_url"] == ""
    # DB 信息
    assert data["db_size_mb"] == 1.5
    # 不应包含密码
    assert "admin_password_hash" not in data


@pytest.mark.asyncio
async def test_get_settings_db_info(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """返回 DB 大小和最近备份时间。"""
    await create_system_config(db, admin_password_hash="$2b$12$test")

    # 创建 backup job_run
    backup_job = JobRun(
        job_type="backup",
        trigger_source="cron",
        status="completed",
        started_at=datetime(2026, 3, 19, 21, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 3, 19, 21, 0, 5, tzinfo=UTC),
    )
    db.add(backup_job)
    await db.commit()

    with patch("app.api.settings._get_db_size_mb", return_value=2.3):
        resp = await authed_client.get("/api/settings")
    assert resp.status_code == 200

    data = resp.json()
    assert data["db_size_mb"] == 2.3
    assert data["last_backup_at"] is not None


# ── PUT /api/settings ──


@pytest.mark.asyncio
async def test_update_settings_partial(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """部分更新成功。"""
    await create_system_config(db, admin_password_hash="$2b$12$test")
    await db.commit()

    resp = await authed_client.put("/api/settings", json={"top_n": 15, "push_time": "09:00"})
    assert resp.status_code == 200
    assert resp.json()["message"] == "配置已更新"

    # 验证 DB 已更新
    with patch("app.api.settings._get_db_size_mb", return_value=1.0):
        get_resp = await authed_client.get("/api/settings")
    assert get_resp.json()["top_n"] == 15
    assert get_resp.json()["push_time"] == "09:00"
    # 其他字段不变
    assert get_resp.json()["min_articles"] == 1


@pytest.mark.asyncio
async def test_update_push_days_empty(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """空数组 → 422。"""
    await create_system_config(db, admin_password_hash="$2b$12$test")
    await db.commit()

    resp = await authed_client.put("/api/settings", json={"push_days": []})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_update_push_days_valid(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """合法数组写入 DB 为逗号字符串。"""
    await create_system_config(db, admin_password_hash="$2b$12$test")
    await db.commit()

    resp = await authed_client.put("/api/settings", json={"push_days": [1, 3, 5]})
    assert resp.status_code == 200

    with patch("app.api.settings._get_db_size_mb", return_value=1.0):
        get_resp = await authed_client.get("/api/settings")
    assert get_resp.json()["push_days"] == [1, 3, 5]


@pytest.mark.asyncio
async def test_update_bool_and_int(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """布尔和整数类型正确转换。"""
    await create_system_config(db, admin_password_hash="$2b$12$test")
    await db.commit()

    resp = await authed_client.put(
        "/api/settings",
        json={
            "enable_cover_generation": True,
            "cover_generation_timeout": 60,
        },
    )
    assert resp.status_code == 200

    with patch("app.api.settings._get_db_size_mb", return_value=1.0):
        get_resp = await authed_client.get("/api/settings")
    assert get_resp.json()["enable_cover_generation"] is True
    assert get_resp.json()["cover_generation_timeout"] == 60


# ── GET /api/settings/api-status ──


@pytest.mark.asyncio
async def test_api_status_unconfigured(
    authed_client: AsyncClient,
) -> None:
    """所有 key 为空 → unconfigured。"""
    with patch("app.api.settings.get_secret_config", AsyncMock(return_value="")):
        resp = await authed_client.get("/api/settings/api-status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["x_api"]["status"] == "unconfigured"
    assert data["claude_api"]["status"] == "unconfigured"
    assert data["gemini_api"]["status"] == "unconfigured"
    assert data["wechat_api"]["status"] == "unconfigured"


@pytest.mark.asyncio
async def test_api_status_mock_ping(
    authed_client: AsyncClient,
) -> None:
    """mock httpx/anthropic → ok + latency。

    I-42 局限性说明：此测试 mock 了 httpx.AsyncClient 和 anthropic.AsyncAnthropic
    的内部行为（__aenter__/__aexit__/get/models.list），与路由实现细节耦合较深。
    若路由层重构 API 检测逻辑（如改用独立的 health checker），测试需同步调整。
    更好的做法是将 API 状态检测抽为可注入的 checker 依赖。
    """

    async def _mock_secret(db: object, key: str) -> str:
        return {"x_api_bearer_token": "test-token", "anthropic_api_key": "test-key"}.get(key, "")

    mock_httpx_resp = MagicMock()
    mock_httpx_resp.status_code = 200
    mock_httpx_client = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx_client.get = AsyncMock(return_value=mock_httpx_resp)

    mock_anthropic = AsyncMock()
    mock_anthropic.models = AsyncMock()
    mock_anthropic.models.list = AsyncMock(return_value=[])

    with (
        patch("app.api.settings.get_secret_config", side_effect=_mock_secret),
        patch("app.api.settings.httpx.AsyncClient", return_value=mock_httpx_client),
        patch("app.api.settings.anthropic.AsyncAnthropic", return_value=mock_anthropic),
    ):
        resp = await authed_client.get("/api/settings/api-status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["x_api"]["status"] == "ok"
    assert data["x_api"]["latency_ms"] is not None
    assert data["claude_api"]["status"] == "ok"
    assert data["gemini_api"]["status"] == "unconfigured"
    assert data["wechat_api"]["status"] == "unconfigured"


@pytest.mark.asyncio
async def test_api_status_error_shows_detail(
    authed_client: AsyncClient,
) -> None:
    """API 状态检测失败时应返回具体错误原因。"""
    import httpx as _httpx

    async def _mock_secret(db: object, key: str) -> str:
        return {"x_api_bearer_token": "bad-token"}.get(key, "")

    mock_resp = MagicMock()
    mock_resp.status_code = 401
    mock_resp.request = MagicMock()
    error = _httpx.HTTPStatusError("Unauthorized", request=mock_resp.request, response=mock_resp)

    mock_httpx_client = AsyncMock()
    mock_httpx_client.__aenter__ = AsyncMock(return_value=mock_httpx_client)
    mock_httpx_client.__aexit__ = AsyncMock(return_value=False)
    mock_httpx_client.get = AsyncMock(side_effect=error)

    with (
        patch("app.api.settings.get_secret_config", side_effect=_mock_secret),
        patch("app.api.settings.httpx.AsyncClient", return_value=mock_httpx_client),
    ):
        resp = await authed_client.get("/api/settings/api-status")

    assert resp.status_code == 200
    data = resp.json()
    assert data["x_api"]["status"] == "error"
    assert data["x_api"]["error_detail"] == "HTTP 401"
