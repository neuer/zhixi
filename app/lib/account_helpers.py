"""共享账号查询辅助函数。"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import TwitterAccount
from app.models.tweet import Tweet


async def get_accounts_map(db: AsyncSession, tweets: list[Tweet]) -> dict[int, TwitterAccount]:
    """构建 account_id -> TwitterAccount 映射。

    从推文列表中提取唯一 account_id，批量查询账号信息。

    Args:
        db: 异步数据库会话
        tweets: 推文列表

    Returns:
        account_id -> TwitterAccount 映射字典
    """
    account_ids = {t.account_id for t in tweets}
    return await get_accounts_map_by_ids(db, account_ids)


async def get_accounts_map_by_ids(
    db: AsyncSession, account_ids: set[int]
) -> dict[int, TwitterAccount]:
    """根据 account_id 集合批量查询账号信息。

    Args:
        db: 异步数据库会话
        account_ids: 账号 ID 集合

    Returns:
        account_id -> TwitterAccount 映射字典
    """
    if not account_ids:
        return {}
    stmt = select(TwitterAccount).where(TwitterAccount.id.in_(account_ids))
    accounts = (await db.execute(stmt)).scalars().all()
    return {a.id: a for a in accounts}
