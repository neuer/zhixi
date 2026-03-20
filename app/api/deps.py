"""依赖工厂 — 集中管理 Service/Client 注入。"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import InvalidTokenError, verify_jwt
from app.clients.claude_client import get_claude_client
from app.database import get_db
from app.services.account_service import AccountService
from app.services.fetch_service import FetchService
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
