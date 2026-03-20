"""digest 路由 — 日报查看与操作。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import get_system_config, get_today_digest_date
from app.database import get_db
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.schemas.digest_types import (
    DigestBriefResponse,
    DigestItemResponse,
    TodayResponse,
)

router = APIRouter()


@router.get("/today", response_model=TodayResponse)
async def get_today_digest(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> TodayResponse:
    """查看今日内容列表。

    "today" = get_today_digest_date() 北京时间自然日。
    查询 digest_date = today AND is_current = true。
    """
    digest_date = get_today_digest_date()

    # 查询当日 is_current=true 的草稿
    stmt = select(DailyDigest).where(
        DailyDigest.digest_date == digest_date,
        DailyDigest.is_current.is_(True),
    )
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()

    if digest is None:
        return TodayResponse(digest=None, items=[], low_content_warning=False)

    # 查询 items
    items_stmt = (
        select(DigestItem)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.display_order)
    )
    items_result = await db.execute(items_stmt)
    items = list(items_result.scalars().all())

    # low_content_warning
    min_articles = int(await get_system_config(db, "min_articles", "1"))
    low_content_warning = digest.item_count < min_articles

    return TodayResponse(
        digest=DigestBriefResponse.model_validate(digest),
        items=[DigestItemResponse.model_validate(item) for item in items],
        low_content_warning=low_content_warning,
    )
