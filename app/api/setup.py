"""setup 路由 — 首次设置向导（US-007）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import WeakPasswordError, hash_password, validate_password_strength
from app.config import upsert_system_config
from app.database import get_db
from app.models.config import SystemConfig
from app.schemas.auth_types import SetupInitRequest, SetupStatusResponse
from app.schemas.digest_types import MessageResponse

router = APIRouter()


async def _get_password_hash(db: AsyncSession) -> str:
    """读取 admin_password_hash。"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == "admin_password_hash"))
    config = result.scalar_one_or_none()
    return config.value if config else ""


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status(
    db: AsyncSession = Depends(get_db),
) -> SetupStatusResponse:
    """检查是否需要首次设置。"""
    password_hash = await _get_password_hash(db)
    return SetupStatusResponse(need_setup=not password_hash)


@router.post("/init", response_model=MessageResponse)
async def setup_init(
    body: SetupInitRequest,
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    """首次设置 — 设定管理员密码。"""
    # 检查是否已完成初始化
    password_hash = await _get_password_hash(db)
    if password_hash:
        raise HTTPException(status_code=403, detail="系统已完成初始化")

    # 校验密码强度
    try:
        validate_password_strength(body.password)
    except WeakPasswordError as e:
        raise HTTPException(status_code=422, detail=e.reason) from None

    # 写入密码哈希
    hashed = await hash_password(body.password)
    await upsert_system_config(db, "admin_password_hash", hashed)

    # 写入 webhook（如果有）
    if body.notification_webhook_url is not None:
        await upsert_system_config(db, "notification_webhook_url", body.notification_webhook_url)

    await db.flush()
    return MessageResponse(message="初始化完成")
