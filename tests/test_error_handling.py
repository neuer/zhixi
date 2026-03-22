"""全局异常处理器与客户端错误处理测试。"""

import pytest

from app.clients.x_client import XApiError


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
    # I-1: 异常处理器不再泄露内部异常信息，返回固定消息
    assert "X API 拉取失败，请稍后重试" in body_str
    assert "allow_manual" in body_str
