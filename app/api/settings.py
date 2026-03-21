"""Settings 路由 — US-041 + API Key UI 管理。"""

import asyncio
import logging
import os
import time

import anthropic
import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import (
    SECRET_CONFIG_KEYS,
    get_secret_config,
    mask_secret,
    settings,
    upsert_system_config,
)
from app.crypto import encrypt_secret
from app.database import get_db
from app.models.config import SystemConfig
from app.models.job_run import JobRun
from app.schemas.digest_types import MessageResponse
from app.schemas.enums import JobStatus, JobType, PublishMode
from app.schemas.settings_types import (
    ApiStatusItem,
    ApiStatusResponse,
    SecretsStatusResponse,
    SecretStatusItem,
    SecretsUpdateRequest,
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

# 密钥 key → 前端显示名
_SECRET_LABELS: dict[str, str] = {
    "x_api_bearer_token": "X API",
    "anthropic_api_key": "Claude API",
    "gemini_api_key": "Gemini API",
    "wechat_app_id": "微信 App ID",
    "wechat_app_secret": "微信 App Secret",
}


def _get_db_size_mb() -> float:
    """获取 SQLite 数据库文件大小（MB）。非 SQLite 数据库返回 0.0。"""
    db_url = settings.DATABASE_URL
    if not db_url.startswith("sqlite"):
        return 0.0
    db_path = db_url.replace("sqlite+aiosqlite:///", "").replace("sqlite:///", "")
    if os.path.exists(db_path):
        return round(os.path.getsize(db_path) / (1024 * 1024), 2)
    return 0.0


def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _parse_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")


def _parse_int_list(value: str) -> list[int]:
    result: list[int] = []
    for x in value.split(","):
        x = x.strip()
        if not x:
            continue
        try:
            result.append(int(x))
        except ValueError:
            continue
    return result


def _serialize_config_value(key: str, value: int | bool | str | list[int]) -> str:
    """将 Python 类型转为 DB 存储字符串。"""
    if key == "push_days" and isinstance(value, list):
        return ",".join(str(x) for x in value)
    if key == "enable_cover_generation" and isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


# ---- 业务配置 CRUD ----


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
        .where(JobRun.job_type == JobType.BACKUP, JobRun.status == JobStatus.COMPLETED)
        .order_by(desc(JobRun.finished_at))
        .limit(1)
    )
    last_backup = backup_result.scalar_one_or_none()

    return SettingsResponse(
        push_time=configs.get("push_time", "08:00"),
        push_days=_parse_int_list(configs.get("push_days", "1,2,3,4,5,6,7")),
        top_n=_parse_int(configs.get("top_n", "10"), 10),
        min_articles=_parse_int(configs.get("min_articles", "1"), 1),
        publish_mode=PublishMode(configs.get("publish_mode", "manual")),
        enable_cover_generation=_parse_bool(configs.get("enable_cover_generation", "false")),
        cover_generation_timeout=_parse_int(configs.get("cover_generation_timeout", "30"), 30),
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
        await upsert_system_config(db, key, db_value)

    return MessageResponse(message="配置已更新")


# ---- 密钥管理 ----


@router.get("/secrets-status", response_model=SecretsStatusResponse)
async def get_secrets_status(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> SecretsStatusResponse:
    """获取各密钥配置状态（掩码展示，不返回原文）。"""
    from app.crypto import decrypt_secret

    items: list[SecretStatusItem] = []
    for key in SECRET_CONFIG_KEYS:
        label = _SECRET_LABELS.get(key, key)
        db_key = f"secret:{key}"
        db_value = await _get_raw_config(db, db_key)

        if db_value:
            decrypted = decrypt_secret(db_value)
            if decrypted:
                items.append(
                    SecretStatusItem(
                        key=key,
                        label=label,
                        configured=True,
                        masked=mask_secret(decrypted),
                        source="db",
                    )
                )
                continue

        # fallback .env
        from app.config import _ENV_ATTR_MAP

        env_attr = _ENV_ATTR_MAP.get(key, key.upper())
        env_value = str(getattr(settings, env_attr, ""))
        if env_value:
            items.append(
                SecretStatusItem(
                    key=key,
                    label=label,
                    configured=True,
                    masked=mask_secret(env_value),
                    source="env",
                )
            )
        else:
            items.append(
                SecretStatusItem(
                    key=key,
                    label=label,
                    configured=False,
                    masked="",
                    source="none",
                )
            )

    return SecretsStatusResponse(items=items)


@router.put("/secrets", response_model=MessageResponse)
async def update_secrets(
    data: SecretsUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """更新密钥配置（加密存储）。"""
    updates = data.model_dump(exclude_none=True)
    if not updates:
        raise HTTPException(status_code=422, detail="未提供任何密钥") from None

    for key, value in updates.items():
        if key not in SECRET_CONFIG_KEYS:
            continue
        ciphertext = encrypt_secret(str(value))
        await upsert_system_config(db, f"secret:{key}", ciphertext)

    return MessageResponse(message="密钥已更新")


@router.delete("/secrets/{key}", response_model=MessageResponse)
async def delete_secret(
    key: str,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """删除 DB 中的密钥配置（恢复 .env fallback）。"""
    if key not in SECRET_CONFIG_KEYS:
        raise HTTPException(status_code=422, detail=f"不支持的密钥名: {key}") from None

    db_key = f"secret:{key}"
    await db.execute(delete(SystemConfig).where(SystemConfig.key == db_key))
    return MessageResponse(message="密钥已清除，将使用 .env 配置")


# ---- API 状态检测 ----


@router.get("/api-status", response_model=ApiStatusResponse)
async def get_api_status(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> ApiStatusResponse:
    """并发 Ping 各 API，检测状态。"""
    x_status, claude_status, gemini_status = await asyncio.gather(
        _ping_x_api(db),
        _ping_claude_api(db),
        _ping_gemini_api(db),
    )

    return ApiStatusResponse(
        x_api=x_status,
        claude_api=claude_status,
        gemini_api=gemini_status,
        wechat_api=ApiStatusItem(status="unconfigured"),
    )


async def _get_raw_config(db: AsyncSession, key: str) -> str:
    """直接读 system_config 原始值。"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else ""


async def _ping_x_api(db: AsyncSession) -> ApiStatusItem:
    """Ping X API: GET /2/users/me。"""
    token = await get_secret_config(db, "x_api_bearer_token")
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


async def _ping_claude_api(db: AsyncSession) -> ApiStatusItem:
    """Ping Claude API: models.list()。"""
    api_key = await get_secret_config(db, "anthropic_api_key")
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


async def _ping_gemini_api(db: AsyncSession) -> ApiStatusItem:
    """Ping Gemini API。MVP 阶段仅检查 key 是否配置。"""
    api_key = await get_secret_config(db, "gemini_api_key")
    if not api_key:
        return ApiStatusItem(status="unconfigured")
    return ApiStatusItem(status="ok", latency_ms=0)


def _elapsed_ms(start: float) -> int:
    """计算耗时毫秒。"""
    return int((time.monotonic() - start) * 1000)
