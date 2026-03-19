"""依赖工厂 — 集中管理 Service/Client 注入。"""

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.account_service import AccountService


async def get_account_service(
    db: AsyncSession = Depends(get_db),
) -> AccountService:
    """构造 AccountService 并注入 DB Session。"""
    return AccountService(db)
