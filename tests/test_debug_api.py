"""debug 路由测试 — 认证检查 + 正常响应路径（C-5）。

所有 X API 外部调用通过 respx mock，无网络依赖。
"""

from unittest.mock import AsyncMock, patch

import respx
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession


def _mock_get_secret_configured() -> AsyncMock:
    """返回一个 mock，模拟已配置 Bearer Token 的 get_secret_config。"""
    return AsyncMock(return_value="test-bearer-token-123")


# ══════════════════════════════════════════════════════════════
# 认证检查 — 未登录应返回 401
# ══════════════════════════════════════════════════════════════


class TestDebugAuthRequired:
    """所有 debug 端点都需要管理员认证。"""

    async def test_ping_requires_auth(self, client: AsyncClient) -> None:
        """GET /api/debug/x/ping 未登录返回 401。"""
        resp = await client.get("/api/debug/x/ping")
        assert resp.status_code == 401

    async def test_user_requires_auth(self, client: AsyncClient) -> None:
        """GET /api/debug/x/user/test 未登录返回 401。"""
        resp = await client.get("/api/debug/x/user/testuser")
        assert resp.status_code == 401

    async def test_tweets_requires_auth(self, client: AsyncClient) -> None:
        """POST /api/debug/x/tweets 未登录返回 401。"""
        resp = await client.post("/api/debug/x/tweets", json={"handle": "test"})
        assert resp.status_code == 401

    async def test_tweet_requires_auth(self, client: AsyncClient) -> None:
        """GET /api/debug/x/tweet/123 未登录返回 401。"""
        resp = await client.get("/api/debug/x/tweet/123456")
        assert resp.status_code == 401


# ══════════════════════════════════════════════════════════════
# 正常路径 — Token 未配置
# ══════════════════════════════════════════════════════════════


class TestDebugPingUnconfigured:
    """Token 未配置时 ping 返回 unconfigured。"""

    async def test_ping_unconfigured(
        self, authed_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        """未配置 Bearer Token 时返回 status=unconfigured。"""
        mock_get_secret = AsyncMock(return_value="")
        with patch("app.api.debug.get_secret_config", mock_get_secret):
            resp = await authed_client.get("/api/debug/x/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "unconfigured"


class TestDebugUserNoBearerToken:
    """Token 未配置时 user/tweets/tweet 端点返回 400。"""

    async def test_user_no_token(self, authed_client: AsyncClient, seeded_db: AsyncSession) -> None:
        """未配置 Bearer Token 时返回 400。"""
        mock_get_secret = AsyncMock(return_value="")
        with patch("app.api.debug.get_secret_config", mock_get_secret):
            resp = await authed_client.get("/api/debug/x/user/testuser")
        assert resp.status_code == 400


# ══════════════════════════════════════════════════════════════
# 正常路径 — X API 响应 mock
# ══════════════════════════════════════════════════════════════


class TestDebugPingOk:
    """ping 端点 X API 返回成功。"""

    @respx.mock
    async def test_ping_ok(self, authed_client: AsyncClient, seeded_db: AsyncSession) -> None:
        """Bearer Token 已配置且 X API 正常 → status=ok。"""
        respx.get("https://api.x.com/2/users/by/username/x").mock(
            return_value=Response(200, json={"data": {"id": "1", "name": "X"}})
        )

        with patch("app.api.debug.get_secret_config", _mock_get_secret_configured()):
            resp = await authed_client.get("/api/debug/x/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["latency_ms"] is not None
        assert data["raw_response"]["data"]["id"] == "1"

    @respx.mock
    async def test_ping_api_error(
        self, authed_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        """X API 返回 HTTP 错误 → status=error。"""
        respx.get("https://api.x.com/2/users/by/username/x").mock(
            return_value=Response(401, json={"error": "Unauthorized"})
        )

        with patch("app.api.debug.get_secret_config", _mock_get_secret_configured()):
            resp = await authed_client.get("/api/debug/x/ping")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "error"


class TestDebugUser:
    """user 端点测试。"""

    @respx.mock
    async def test_user_found(self, authed_client: AsyncClient, seeded_db: AsyncSession) -> None:
        """查询存在的用户 → 返回解析后的 user 对象。"""
        respx.get("https://api.x.com/2/users/by/username/testuser").mock(
            return_value=Response(
                200,
                json={
                    "data": {
                        "id": "12345",
                        "name": "Test User",
                        "description": "测试用户",
                        "profile_image_url": "https://example.com/avatar.jpg",
                        "public_metrics": {"followers_count": 1000},
                    }
                },
            ),
        )

        with patch("app.api.debug.get_secret_config", _mock_get_secret_configured()):
            resp = await authed_client.get("/api/debug/x/user/testuser")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] is not None
        assert data["user"]["twitter_user_id"] == "12345"
        assert data["user"]["display_name"] == "Test User"

    @respx.mock
    async def test_user_not_found(
        self, authed_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        """查询不存在的用户 → user=None。"""
        respx.get("https://api.x.com/2/users/by/username/nonexistent").mock(
            return_value=Response(200, json={"errors": [{"detail": "Could not find user"}]})
        )

        with patch("app.api.debug.get_secret_config", _mock_get_secret_configured()):
            resp = await authed_client.get("/api/debug/x/user/nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["user"] is None


class TestDebugTweet:
    """单条推文查询测试。"""

    @respx.mock
    async def test_tweet_not_found(
        self, authed_client: AsyncClient, seeded_db: AsyncSession
    ) -> None:
        """推文不存在 → tweet=None。"""
        respx.get("https://api.x.com/2/tweets/999999").mock(
            return_value=Response(200, json={"errors": [{"detail": "Not Found"}]})
        )

        with patch("app.api.debug.get_secret_config", _mock_get_secret_configured()):
            resp = await authed_client.get("/api/debug/x/tweet/999999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tweet"] is None
