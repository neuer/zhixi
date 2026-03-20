"""history 路由 — 推送历史查看。"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.database import get_db
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.schemas.digest_types import (
    DigestBriefResponse,
    DigestItemResponse,
    HistoryDetailResponse,
    HistoryListItem,
    HistoryListResponse,
)

router = APIRouter()


@router.get("", response_model=HistoryListResponse)
async def list_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> HistoryListResponse:
    """推送历史列表（分页，每日期一条）。

    版本选择优先级：published → is_current=true → version 最大。
    """
    # 使用 ROW_NUMBER 窗口函数，每个 digest_date 选出优先级最高的版本
    priority_published = case(
        (DailyDigest.status == "published", 0),
        else_=1,
    )
    priority_current = case(
        (DailyDigest.is_current.is_(True), 0),
        else_=1,
    )

    ranked = select(
        DailyDigest.id,
        func.row_number()
        .over(
            partition_by=DailyDigest.digest_date,
            order_by=[
                priority_published,
                priority_current,
                DailyDigest.version.desc(),
            ],
        )
        .label("rn"),
    ).subquery()

    # 查询总数（distinct dates）
    count_stmt = select(func.count(func.distinct(DailyDigest.digest_date)))
    count_result = await db.execute(count_stmt)
    total = count_result.scalar() or 0

    # 查询分页数据
    stmt = (
        select(DailyDigest)
        .join(ranked, DailyDigest.id == ranked.c.id)
        .where(ranked.c.rn == 1)
        .order_by(DailyDigest.digest_date.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(stmt)
    digests = list(result.scalars().all())

    return HistoryListResponse(
        items=[HistoryListItem.model_validate(d) for d in digests],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{digest_id}", response_model=HistoryDetailResponse)
async def get_history_detail(
    digest_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> HistoryDetailResponse:
    """历史详情（完整信息 + items 快照）。"""
    stmt = select(DailyDigest).where(DailyDigest.id == digest_id)
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()

    if digest is None:
        raise HTTPException(status_code=404, detail="记录不存在") from None

    items_stmt = (
        select(DigestItem)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.display_order)
    )
    items_result = await db.execute(items_stmt)
    items = list(items_result.scalars().all())

    return HistoryDetailResponse(
        digest=DigestBriefResponse.model_validate(digest),
        items=[DigestItemResponse.model_validate(item) for item in items],
    )
