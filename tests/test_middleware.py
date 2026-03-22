"""RequestIdMiddleware 单元测试 — request_id 注入与 X-Request-ID 响应头。"""

from httpx import AsyncClient

from app.middleware import request_id_var


class TestRequestIdMiddleware:
    """RequestIdMiddleware 功能验证。"""

    async def test_response_has_x_request_id_header(self, client: AsyncClient) -> None:
        """每个响应都应包含 X-Request-ID 头。"""
        resp = await client.get("/api/setup/status")
        assert "X-Request-ID" in resp.headers
        rid = resp.headers["X-Request-ID"]
        # UUID4 格式：8-4-4-4-12
        parts = rid.split("-")
        assert len(parts) == 5
        assert [len(p) for p in parts] == [8, 4, 4, 4, 12]

    async def test_different_requests_get_different_ids(self, client: AsyncClient) -> None:
        """不同请求应获得不同的 request_id。"""
        resp1 = await client.get("/api/setup/status")
        resp2 = await client.get("/api/setup/status")
        rid1 = resp1.headers["X-Request-ID"]
        rid2 = resp2.headers["X-Request-ID"]
        assert rid1 != rid2

    async def test_context_var_reset_after_request(self, client: AsyncClient) -> None:
        """请求结束后 ContextVar 应被重置为 None。"""
        # 请求前应该是 None
        assert request_id_var.get() is None
        await client.get("/api/setup/status")
        # 请求后 ContextVar 应恢复 None
        assert request_id_var.get() is None
