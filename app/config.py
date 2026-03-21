"""应用配置 — 环境变量读取、DB 业务配置、时间工具函数。"""

import logging
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from pydantic_settings import BaseSettings
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

BEIJING_TZ = ZoneInfo("Asia/Shanghai")


class Settings(BaseSettings):
    """从 .env 读取的系统配置。"""

    X_API_BEARER_TOKEN: str = ""
    ANTHROPIC_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_INPUT_PRICE_PER_MTOK: float = 3.0
    CLAUDE_OUTPUT_PRICE_PER_MTOK: float = 15.0
    GEMINI_API_KEY: str = ""
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 72
    DATABASE_URL: str = "sqlite:///data/zhixi.db"
    DEBUG: bool = False
    TIMEZONE: str = "Asia/Shanghai"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DOMAIN: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()  # type: ignore[call-arg]  # pydantic-settings reads from .env


def get_today_digest_date() -> date:
    """获取今日 digest_date（北京时间自然日）。禁止用 datetime.utcnow().date()。"""
    return datetime.now(BEIJING_TZ).date()


def get_fetch_window(digest_date: date) -> tuple[datetime, datetime]:
    """前一日 06:00:00 ~ 当日 05:59:59（北京时间）→ 转 UTC。"""
    bj_since = datetime(
        digest_date.year, digest_date.month, digest_date.day, 6, 0, 0, tzinfo=BEIJING_TZ
    ) - timedelta(days=1)
    bj_until = datetime(
        digest_date.year, digest_date.month, digest_date.day, 5, 59, 59, tzinfo=BEIJING_TZ
    )
    return bj_since.astimezone(UTC), bj_until.astimezone(UTC)


async def get_system_config(db: AsyncSession, key: str, default: str = "") -> str:
    """从 DB system_config 表读取业务配置。"""
    from app.models.config import SystemConfig

    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else default


async def upsert_system_config(db: AsyncSession, key: str, value: str) -> None:
    """写入或更新 system_config 表中的配置项。"""
    from app.models.config import SystemConfig

    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    if config:
        config.value = value
    else:
        db.add(SystemConfig(key=key, value=value))


async def safe_int_config(db: AsyncSession, key: str, default: int) -> int:
    """安全读取整数配置，转换失败时返回默认值。"""
    raw = await get_system_config(db, key, str(default))
    try:
        return int(raw)
    except (ValueError, TypeError):
        logger.warning("配置 %s 值 '%s' 无法转为 int，使用默认值 %d", key, raw, default)
        return default


async def safe_float_config(db: AsyncSession, key: str, default: float) -> float:
    """安全读取浮点配置，转换失败时返回默认值。"""
    raw = await get_system_config(db, key, str(default))
    try:
        return float(raw)
    except (ValueError, TypeError):
        logger.warning("配置 %s 值 '%s' 无法转为 float，使用默认值 %s", key, raw, default)
        return default


def ensure_utc(dt: datetime) -> datetime:
    """确保 datetime 有 UTC 时区信息（SQLite 读回可能丢失 tzinfo）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


# ---- 密钥配置：DB 优先 + .env fallback ----

# 支持通过 UI 管理的密钥配置项
SECRET_CONFIG_KEYS = frozenset(
    {
        "x_api_bearer_token",
        "anthropic_api_key",
        "gemini_api_key",
        "wechat_app_id",
        "wechat_app_secret",
    }
)

# .env 字段名映射（小写 key → Settings 属性名）
_ENV_ATTR_MAP: dict[str, str] = {
    "x_api_bearer_token": "X_API_BEARER_TOKEN",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
    "gemini_api_key": "GEMINI_API_KEY",
    "wechat_app_id": "WECHAT_APP_ID",
    "wechat_app_secret": "WECHAT_APP_SECRET",
}


async def get_secret_config(db: AsyncSession, key: str) -> str:
    """读取密钥配置：DB 优先（解密），fallback .env。"""
    from app.crypto import decrypt_secret

    db_key = f"secret:{key}"
    db_value = await get_system_config(db, db_key)
    if db_value:
        decrypted = decrypt_secret(db_value)
        if decrypted:
            return decrypted

    # fallback .env
    env_attr = _ENV_ATTR_MAP.get(key, key.upper())
    return str(getattr(settings, env_attr, ""))


def mask_secret(value: str) -> str:
    """掩码处理：首4尾4，中间****。短于12字符只显示****。"""
    if not value:
        return ""
    if len(value) < 12:
        return "****"
    return f"{value[:4]}****{value[-4:]}"
