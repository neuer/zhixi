"""API 调用成本记录公共函数。"""

from datetime import date

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_today_digest_date
from app.models.api_cost_log import ApiCostLog
from app.schemas.client_types import ClaudeResponse
from app.schemas.enums import ServiceType


def record_api_cost(
    db: AsyncSession,
    response: ClaudeResponse,
    call_type: str,
    digest_date: date | None,
    service: ServiceType = ServiceType.CLAUDE,
) -> None:
    """记录成功的 API 调用成本。"""
    db.add(
        ApiCostLog(
            call_date=digest_date or get_today_digest_date(),
            service=service,
            call_type=call_type,
            model=response.model,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            estimated_cost=response.estimated_cost,
            success=True,
            duration_ms=response.duration_ms,
        )
    )


def record_api_cost_failure(
    db: AsyncSession,
    call_type: str,
    digest_date: date | None,
    service: ServiceType = ServiceType.CLAUDE,
) -> None:
    """记录失败的 API 调用。"""
    db.add(
        ApiCostLog(
            call_date=digest_date or get_today_digest_date(),
            service=service,
            call_type=call_type,
            success=False,
        )
    )
