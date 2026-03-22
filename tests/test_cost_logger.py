"""cost_logger 单元测试 — record_api_cost / record_api_cost_failure 正常路径 + digest_date=None fallback。"""

from datetime import date
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.lib.cost_logger import record_api_cost, record_api_cost_failure
from app.models.api_cost_log import ApiCostLog
from app.schemas.client_types import ClaudeResponse
from app.schemas.enums import CallType, ServiceType


def _make_response(**overrides: object) -> ClaudeResponse:
    """构造测试用 ClaudeResponse。"""
    defaults = {
        "content": "测试内容",
        "input_tokens": 100,
        "output_tokens": 50,
        "model": "claude-sonnet-4-20250514",
        "duration_ms": 1200,
        "estimated_cost": 0.003,
    }
    defaults.update(overrides)
    return ClaudeResponse(**defaults)  # type: ignore[arg-type]


class TestRecordApiCost:
    """record_api_cost 成功路径。"""

    async def test_with_explicit_digest_date(self, db: AsyncSession) -> None:
        """传入 digest_date 时使用指定日期。"""
        resp = _make_response()
        target_date = date(2025, 6, 15)

        record_api_cost(db, resp, CallType.SINGLE_PROCESS, digest_date=target_date)
        await db.flush()

        result = await db.execute(select(ApiCostLog))
        log = result.scalar_one()

        assert log.call_date == target_date
        assert log.service == ServiceType.CLAUDE
        assert log.call_type == CallType.SINGLE_PROCESS
        assert log.model == "claude-sonnet-4-20250514"
        assert log.input_tokens == 100
        assert log.output_tokens == 50
        assert log.estimated_cost == pytest.approx(0.003)
        assert log.success is True
        assert log.duration_ms == 1200

    async def test_with_custom_service(self, db: AsyncSession) -> None:
        """指定非默认 service 类型。"""
        resp = _make_response()
        record_api_cost(
            db, resp, CallType.FETCH_TWEETS, digest_date=date(2025, 1, 1), service=ServiceType.X
        )
        await db.flush()

        result = await db.execute(select(ApiCostLog))
        log = result.scalar_one()
        assert log.service == ServiceType.X

    async def test_digest_date_none_uses_fallback(self, db: AsyncSession) -> None:
        """digest_date=None 时 fallback 到 get_today_digest_date()。"""
        fallback_date = date(2025, 8, 1)
        resp = _make_response()

        with patch("app.lib.cost_logger.get_today_digest_date", return_value=fallback_date):
            record_api_cost(db, resp, CallType.GLOBAL_ANALYSIS, digest_date=None)
        await db.flush()

        result = await db.execute(select(ApiCostLog))
        log = result.scalar_one()
        assert log.call_date == fallback_date


class TestRecordApiCostFailure:
    """record_api_cost_failure 失败记录路径。"""

    async def test_failure_record(self, db: AsyncSession) -> None:
        """正常记录失败的 API 调用。"""
        target_date = date(2025, 6, 15)

        record_api_cost_failure(db, CallType.TOPIC_PROCESS, digest_date=target_date)
        await db.flush()

        result = await db.execute(select(ApiCostLog))
        log = result.scalar_one()

        assert log.call_date == target_date
        assert log.service == ServiceType.CLAUDE
        assert log.call_type == CallType.TOPIC_PROCESS
        assert log.success is False
        assert log.model is None
        assert log.input_tokens == 0
        assert log.output_tokens == 0

    async def test_failure_digest_date_none_fallback(self, db: AsyncSession) -> None:
        """digest_date=None 时 fallback 到 get_today_digest_date()。"""
        fallback_date = date(2025, 12, 25)

        with patch("app.lib.cost_logger.get_today_digest_date", return_value=fallback_date):
            record_api_cost_failure(db, CallType.DEDUP_ANALYSIS, digest_date=None)
        await db.flush()

        result = await db.execute(select(ApiCostLog))
        log = result.scalar_one()
        assert log.call_date == fallback_date

    async def test_failure_with_custom_service(self, db: AsyncSession) -> None:
        """指定非默认 service 类型。"""
        record_api_cost_failure(
            db, CallType.FETCH_TWEETS, digest_date=date(2025, 1, 1), service=ServiceType.GEMINI
        )
        await db.flush()

        result = await db.execute(select(ApiCostLog))
        log = result.scalar_one()
        assert log.service == ServiceType.GEMINI
