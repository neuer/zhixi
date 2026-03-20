"""依赖工厂 — 集中管理 Service/Client 注入。"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import InvalidTokenError, verify_jwt
from app.clients.claude_client import get_claude_client
from app.config import get_today_digest_date
from app.database import get_db
from app.services.account_service import AccountService
from app.services.digest_service import DigestService
from app.services.fetch_service import FetchService
from app.services.lock_service import has_running_pipeline
from app.services.process_service import ProcessService


async def get_current_admin(
    authorization: str | None = Header(default=None),
) -> str:
    """从 Authorization header 提取并验证 JWT。返回用户名。"""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = verify_jwt(token)
    except InvalidTokenError:
        raise HTTPException(status_code=401, detail="登录已过期，请重新登录") from None
    return payload["sub"]


async def get_account_service(
    db: AsyncSession = Depends(get_db),
) -> AccountService:
    """构造 AccountService 并注入 DB Session。"""
    return AccountService(db)


async def get_fetch_service(
    db: AsyncSession = Depends(get_db),
) -> FetchService:
    """构造 FetchService 并注入 DB Session。"""
    return FetchService(db)


async def get_process_service(
    db: AsyncSession = Depends(get_db),
) -> ProcessService:
    """构造 ProcessService 并注入 DB Session + ClaudeClient。"""
    return ProcessService(db, claude_client=get_claude_client())


async def get_digest_service(
    db: AsyncSession = Depends(get_db),
) -> DigestService:
    """构造 DigestService 并注入 DB Session + ClaudeClient。"""
    return DigestService(db, claude_client=get_claude_client())


async def require_no_pipeline_lock(
    db: AsyncSession = Depends(get_db),
) -> None:
    """增强锁守卫 — 当日有 pipeline running 时返回 409。"""
    today = get_today_digest_date()
    if await has_running_pipeline(db, today):
        raise HTTPException(
            status_code=409,
            detail="当前有任务在运行中，请稍后再试",
        )
