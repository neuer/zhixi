"""account_service — 大V账号管理编排层。"""

import logging

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.x_client import lookup_user
from app.config import get_secret_config
from app.models.account import TwitterAccount
from app.schemas.account_types import (
    AccountCreate,
    AccountListResponse,
    AccountResponse,
    AccountUpdate,
)

logger = logging.getLogger(__name__)


class AccountService:
    """大V账号 CRUD 业务逻辑。"""

    def __init__(self, db: AsyncSession) -> None:
        """注入异步数据库 Session。"""
        self._db = db

    async def list_accounts(
        self,
        page: int = 1,
        page_size: int = 20,
        include_inactive: bool = False,
    ) -> AccountListResponse:
        """分页查询账号列表。

        Args:
            page: 页码（从 1 开始）
            page_size: 每页条数
            include_inactive: 是否包含已停用账号
        """
        stmt = select(TwitterAccount)
        count_stmt = select(func.count()).select_from(TwitterAccount)

        if not include_inactive:
            stmt = stmt.where(TwitterAccount.is_active.is_(True))
            count_stmt = count_stmt.where(TwitterAccount.is_active.is_(True))

        # 总数
        total_result = await self._db.execute(count_stmt)
        total = total_result.scalar_one()

        # 分页
        offset = (page - 1) * page_size
        stmt = stmt.order_by(TwitterAccount.id).offset(offset).limit(page_size)
        result = await self._db.execute(stmt)
        accounts = list(result.scalars().all())

        return AccountListResponse(
            items=[AccountResponse.model_validate(a) for a in accounts],
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_account(self, data: AccountCreate) -> TwitterAccount:
        """创建大V账号。

        流程：handle 规范化 → 去重 → X API 查询或手动模式 → 入库。
        去重范围包含 inactive 账号。
        X API 失败时抛 XApiError，由路由层转 502。
        """
        # 1. handle 规范化：去除 @ 前缀
        handle = data.twitter_handle.lstrip("@").strip()

        # 2. 去重（含 inactive）
        stmt = select(TwitterAccount).where(TwitterAccount.twitter_handle == handle)
        result = await self._db.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing is not None:
            raise AccountDuplicateError(handle)

        # 3. 创建账号
        account = TwitterAccount(
            twitter_handle=handle,
            weight=data.weight,
        )

        if data.display_name is not None:
            # 手动模式：使用提交的字段
            account.display_name = data.display_name
            account.bio = data.bio
            account.avatar_url = data.avatar_url
        else:
            # 自动模式：调用 X API 拉取
            token = await get_secret_config(self._db, "x_api_bearer_token")
            profile = await lookup_user(token, handle)
            account.twitter_user_id = profile.twitter_user_id
            account.display_name = profile.display_name
            account.bio = profile.bio
            account.avatar_url = profile.avatar_url
            account.followers_count = profile.followers_count

        self._db.add(account)
        await self._db.flush()
        return account

    async def update_account(self, account_id: int, data: AccountUpdate) -> TwitterAccount:
        """部分更新账号。

        仅更新请求中非 None 的字段。
        """
        account = await self._get_or_raise(account_id)

        if data.weight is not None:
            account.weight = data.weight
        if data.is_active is not None:
            account.is_active = data.is_active

        await self._db.flush()
        return account

    async def delete_account(self, account_id: int) -> None:
        """软删除账号（设 is_active=false）。"""
        account = await self._get_or_raise(account_id)
        account.is_active = False
        await self._db.flush()

    async def _get_or_raise(self, account_id: int) -> TwitterAccount:
        """按 ID 查询账号，不存在抛 AccountNotFoundError。"""
        stmt = select(TwitterAccount).where(TwitterAccount.id == account_id)
        result = await self._db.execute(stmt)
        account = result.scalar_one_or_none()
        if account is None:
            raise AccountNotFoundError(account_id)
        return account


class AccountDuplicateError(Exception):
    """账号已存在。"""

    def __init__(self, handle: str) -> None:
        self.handle = handle
        super().__init__(f"账号已存在: {handle}")


class AccountNotFoundError(Exception):
    """账号不存在。"""

    def __init__(self, account_id: int) -> None:
        self.account_id = account_id
        super().__init__(f"账号不存在: id={account_id}")
