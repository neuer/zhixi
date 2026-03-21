"""auth 路由 — 管理员登录认证（US-008）。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    check_login_rate_limit,
    create_jwt,
    record_login_failure,
    record_login_success,
    verify_password,
)
from app.database import get_db
from app.models.config import SystemConfig
from app.schemas.auth_types import LoginRequest, LoginResponse
from app.schemas.digest_types import MessageResponse

router = APIRouter()


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> LoginResponse:
    """管理员登录 → JWT token。"""
    # 限流检查
    if not check_login_rate_limit(body.username):
        raise HTTPException(status_code=423, detail="登录失败次数过多，请15分钟后再试")

    # 读取密码哈希
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == "admin_password_hash"))
    config = result.scalar_one_or_none()
    password_hash = config.value if config else ""

    # 验证凭据
    if (
        not password_hash
        or body.username != "admin"
        or not await verify_password(body.password, password_hash)
    ):
        record_login_failure(body.username)
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    # 成功
    record_login_success(body.username)
    token, expires_at = create_jwt(body.username)
    return LoginResponse(token=token, expires_at=expires_at)


@router.post("/logout", response_model=MessageResponse)
async def logout() -> MessageResponse:
    """退出登录（后端无状态操作，前端清 token）。"""
    return MessageResponse(message="已退出登录")
