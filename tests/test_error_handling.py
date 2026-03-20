"""全局异常处理器与客户端错误处理测试。"""

import pytest
import respx
from httpx import Response

from app.clients.x_client import XApiError, lookup_user


@pytest.mark.asyncio
async def test_x_api_error_handler_includes_detail():
    """XApiError 全局处理器应在响应中包含原始错误信息。"""
    from fastapi import Request

    from app.main import handle_x_api_error

    mock_request = Request(scope={"type": "http", "method": "GET", "path": "/"})
    exc = XApiError("Token 已过期")
    response = await handle_x_api_error(mock_request, exc)

    assert response.status_code == 502
    body = response.body
    body_str = body.decode() if isinstance(body, bytes) else str(body)
    assert "Token 已过期" in body_str
    assert "allow_manual" in body_str


@pytest.mark.asyncio
@respx.mock
async def test_lookup_user_non_json_response():
    """X API 返回 200 但非 JSON 内容时应抛 XApiError。"""
    respx.get("https://api.x.com/2/users/by/username/testuser").mock(
        return_value=Response(200, text="<html>Error</html>")
    )
    with pytest.raises(XApiError, match="查询失败"):
        await lookup_user("fake_token", "testuser")


@pytest.mark.asyncio
@respx.mock
async def test_lookup_user_missing_id_field():
    """X API 返回 data 但缺少 id 字段时应抛 XApiError。"""
    respx.get("https://api.x.com/2/users/by/username/testuser").mock(
        return_value=Response(
            200,
            json={"data": {"name": "Test", "description": "bio"}},
        )
    )
    with pytest.raises(XApiError, match="字段缺失|查询失败"):
        await lookup_user("fake_token", "testuser")
