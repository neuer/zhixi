"""日志系统测试。"""

import json
import logging
from io import StringIO

from httpx import AsyncClient

from app.logging_config import JsonFormatter
from app.middleware import request_id_var


class TestJsonFormatter:
    """JSON 格式化器测试。"""

    def test_output_is_valid_json(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="test message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert isinstance(parsed, dict)

    def test_contains_required_fields(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test.module",
            level=logging.WARNING,
            pathname="test.py",
            lineno=10,
            msg="warning message",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert "timestamp" in parsed
        assert parsed["level"] == "WARNING"
        assert parsed["message"] == "warning message"
        assert "module" in parsed

    def test_includes_request_id_from_context(self) -> None:
        formatter = JsonFormatter()
        token = request_id_var.set("test-req-123")
        try:
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="test.py",
                lineno=1,
                msg="with request_id",
                args=(),
                exc_info=None,
            )
            output = formatter.format(record)
            parsed = json.loads(output)
            assert parsed["request_id"] == "test-req-123"
        finally:
            request_id_var.reset(token)

    def test_no_request_id_when_not_set(self) -> None:
        formatter = JsonFormatter()
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="no context",
            args=(),
            exc_info=None,
        )
        output = formatter.format(record)
        parsed = json.loads(output)
        assert parsed["request_id"] is None


class TestSetupLogging:
    """日志初始化测试。"""

    def test_log_level_filters(self) -> None:
        stream = StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(JsonFormatter())

        logger = logging.getLogger("test_filter")
        logger.handlers.clear()
        logger.addHandler(handler)
        logger.setLevel(logging.WARNING)

        logger.info("should not appear")
        logger.warning("should appear")

        output = stream.getvalue()
        assert "should not appear" not in output
        assert "should appear" in output


class TestRequestIdMiddleware:
    """request_id 中间件测试。"""

    async def test_response_has_request_id_header(self, client: AsyncClient) -> None:
        """任意请求的响应都应包含 X-Request-ID header。"""
        resp = await client.post("/api/auth/logout")
        assert "x-request-id" in resp.headers
        rid = resp.headers["x-request-id"]
        assert len(rid) > 0
