"""日志系统测试。"""

import json
import logging
from io import StringIO

import pytest
from httpx import ASGITransport, AsyncClient

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

    @pytest.fixture
    def _clean_app(self):
        from app.main import app

        app.dependency_overrides.clear()
        yield app
        app.dependency_overrides.clear()

    async def test_response_has_request_id_header(self, _clean_app) -> None:
        from app.main import app
        from app.middleware import RequestIdMiddleware

        if not any(
            getattr(m, "cls", None) is RequestIdMiddleware
            for m in getattr(app, "user_middleware", [])
        ):
            app.add_middleware(RequestIdMiddleware)

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/setup/status")
            assert "x-request-id" in resp.headers
            rid = resp.headers["x-request-id"]
            assert len(rid) > 0
