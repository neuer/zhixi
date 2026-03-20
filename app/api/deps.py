"""依赖工厂 — 集中管理 Service/Client 注入。"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import get_claude_client
from app.database import get_db
from app.services.account_service import AccountService
from app.services.fetch_service import FetchService
from app.services.process_service import ProcessService


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
