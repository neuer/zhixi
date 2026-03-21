"""Settings 路由 — US-041。"""

import asyncio
import logging
import os
import time

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import settings
from app.database import get_db
from app.models.config import SystemConfig
from app.models.job_run import JobRun
from app.schemas.digest_types import MessageResponse
from app.schemas.enums import PublishMode
from app.schemas.settings_types import (
    ApiStatusItem,
    ApiStatusResponse,
    SettingsResponse,
    SettingsUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# 可读写的配置键（排除密钥类）
_EDITABLE_KEYS = {
    "push_time",
    "push_days",
    "top_n",
    "min_articles",
    "publish_mode",
    "enable_cover_generation",
    "cover_generation_timeout",
    "notification_webhook_url",
}


def _get_db_size_mb() -> float:
    """获取 SQLite 数据库文件大小（MB）。"""
    db_path = settings.DATABASE_URL.replace("sqlite:///", "")
    if os.path.exists(db_path):
        return round(os.path.getsize(db_path) / (1024 * 1024), 2)
    return 0.0


def _parse_config_value(key: str, value: str) -> int | bool | str | list[int]:
    """将 DB 字符串值转为对应 Python 类型。"""
    if key == "push_days":
        return [int(x.strip()) for x in value.split(",") if x.strip()] if value else []
    if key in ("top_n", "min_articles", "cover_generation_timeout"):
        return int(value) if value else 0
    if key == "enable_cover_generation":
        return value.lower() == "true"
    return value


def _serialize_config_value(key: str, value: int | bool | str | list[int]) -> str:
    """将 Python 类型转为 DB 存储字符串。"""
    if key == "push_days" and isinstance(value, list):
        return ",".join(str(x) for x in value)
    if key == "enable_cover_generation" and isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


@router.get("", response_model=SettingsResponse)
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> SettingsResponse:
    """获取全部业务配置（不含密钥）。"""
    result = await db.execute(select(SystemConfig))
    configs = {c.key: c.value for c in result.scalars().all()}

    # 查询最近 backup
    backup_result = await db.execute(
        select(JobRun)
        .where(JobRun.job_type == "backup", JobRun.status == "completed")
        .order_by(desc(JobRun.finished_at))
        .limit(1)
    )
    last_backup = backup_result.scalar_one_or_none()

    return SettingsResponse(
        push_time=configs.get("push_time", "08:00"),
        push_days=_parse_config_value("push_days", configs.get("push_days", "1,2,3,4,5,6,7")),  # type: ignore[arg-type]
        top_n=_parse_config_value("top_n", configs.get("top_n", "10")),  # type: ignore[arg-type]
        min_articles=_parse_config_value("min_articles", configs.get("min_articles", "1")),  # type: ignore[arg-type]
        publish_mode=PublishMode(configs.get("publish_mode", "manual")),
        enable_cover_generation=_parse_config_value(
            "enable_cover_generation", configs.get("enable_cover_generation", "false")
        ),  # type: ignore[arg-type]
        cover_generation_timeout=_parse_config_value(
            "cover_generation_timeout", configs.get("cover_generation_timeout", "30")
        ),  # type: ignore[arg-type]
        notification_webhook_url=configs.get("notification_webhook_url", ""),
        db_size_mb=_get_db_size_mb(),
        last_backup_at=last_backup.finished_at if last_backup else None,
    )


@router.put("", response_model=MessageResponse)
async def update_settings(
    data: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """部分更新业务配置。"""
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="未提供任何配置项") from None

    for key, value in updates.items():
        if key not in _EDITABLE_KEYS:
            continue
        db_value = _serialize_config_value(key, value)
        result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
        config = result.scalar_one_or_none()
        if config:
            config.value = db_value
        else:
            db.add(SystemConfig(key=key, value=db_value))

    return MessageResponse(message="配置已更新")


@router.get("/api-status", response_model=ApiStatusResponse)
async def get_api_status(
    _admin: str = Depends(get_current_admin),
) -> ApiStatusResponse:
    """并发 Ping 各 API，检测状态。"""
    x_status, claude_status, gemini_status = await asyncio.gather(
        _ping_x_api(),
        _ping_claude_api(),
        _ping_gemini_api(),
    )

    return ApiStatusResponse(
        x_api=x_status,
        claude_api=claude_status,
        gemini_api=gemini_status,
        wechat_api=ApiStatusItem(status="unconfigured"),
    )


async def _ping_x_api() -> ApiStatusItem:
    """Ping X API: GET /2/users/me。"""
    token = settings.X_API_BEARER_TOKEN
    if not token:
        return ApiStatusItem(status="unconfigured")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.x.com/2/users/me",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
    except Exception:
        logger.warning("X API ping 失败", exc_info=True)
        return ApiStatusItem(status="error", latency_ms=_elapsed_ms(start))

    return ApiStatusItem(status="ok", latency_ms=_elapsed_ms(start))


async def _ping_claude_api() -> ApiStatusItem:
    """Ping Claude API: models.list()。"""
    api_key = settings.ANTHROPIC_API_KEY
    if not api_key:
        return ApiStatusItem(status="unconfigured")

    start = time.monotonic()
    try:
        client = anthropic.AsyncAnthropic(api_key=api_key, timeout=5.0)
        await client.models.list()
    except Exception:
        logger.warning("Claude API ping 失败", exc_info=True)
        return ApiStatusItem(status="error", latency_ms=_elapsed_ms(start))

    return ApiStatusItem(status="ok", latency_ms=_elapsed_ms(start))


async def _ping_gemini_api() -> ApiStatusItem:
    """Ping Gemini API。MVP 阶段仅检查 key 是否配置。"""
    if not settings.GEMINI_API_KEY:
        return ApiStatusItem(status="unconfigured")
    # 有 key 但暂不实际 ping（MVP），标记为 ok
    return ApiStatusItem(status="ok", latency_ms=0)


def _elapsed_ms(start: float) -> int:
    """计算耗时毫秒。"""
    return int((time.monotonic() - start) * 1000)
