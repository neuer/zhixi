"""digest 路由 — 日报查看与操作。"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_digest_service
from app.config import get_system_config, get_today_digest_date
from app.database import get_db
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.schemas.digest_types import (
    DigestBriefResponse,
    DigestItemResponse,
    EditItemRequest,
    EditSummaryRequest,
    MessageResponse,
    ReorderRequest,
    TodayResponse,
)
from app.services.digest_service import (
    DigestItemNotFoundError,
    DigestNotEditableError,
    DigestNotFoundError,
    DigestService,
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


# ── US-031: 编辑单条内容 ──


@router.put("/item/{item_type}/{item_ref_id}", response_model=DigestItemResponse)
async def edit_item(
    item_type: str,
    item_ref_id: int,
    body: EditItemRequest,
    svc: DigestService = Depends(get_digest_service),
    _admin: str = Depends(get_current_admin),
) -> DigestItemResponse:
    """编辑单条内容的 snapshot 字段。"""
    updates = body.model_dump(exclude_none=True)
    try:
        item = await svc.edit_item(item_type, item_ref_id, updates)
    except DigestNotFoundError:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    except DigestNotEditableError:
        raise HTTPException(
            status_code=409, detail="当前版本不可编辑，请先重新生成新版本"
        ) from None
    except DigestItemNotFoundError:
        raise HTTPException(status_code=404, detail="条目不存在") from None
    return DigestItemResponse.model_validate(item)


# ── US-032: 编辑导读摘要 ──


@router.put("/summary", response_model=MessageResponse)
async def edit_summary(
    body: EditSummaryRequest,
    svc: DigestService = Depends(get_digest_service),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """编辑导读摘要并重渲染 Markdown。"""
    try:
        await svc.edit_summary(body.summary)
    except DigestNotFoundError:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    except DigestNotEditableError:
        raise HTTPException(
            status_code=409, detail="当前版本不可编辑，请先重新生成新版本"
        ) from None
    return MessageResponse(message="导读摘要已更新")


# ── US-033: 调整排序与置顶 ──


@router.put("/reorder", response_model=MessageResponse)
async def reorder_items(
    body: ReorderRequest,
    svc: DigestService = Depends(get_digest_service),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """调整排序与置顶。"""
    items_input = [item.model_dump() for item in body.items]
    try:
        await svc.reorder_items(items_input)
    except DigestNotFoundError:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    except DigestNotEditableError:
        raise HTTPException(
            status_code=409, detail="当前版本不可编辑，请先重新生成新版本"
        ) from None
    except DigestItemNotFoundError:
        raise HTTPException(status_code=404, detail="条目不存在") from None
    return MessageResponse(message="排序已更新")


# ── US-034: 剔除与恢复条目 ──


@router.post("/exclude/{item_type}/{item_ref_id}", response_model=MessageResponse)
async def exclude_item(
    item_type: str,
    item_ref_id: int,
    svc: DigestService = Depends(get_digest_service),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """剔除条目。"""
    try:
        await svc.exclude_item(item_type, item_ref_id)
    except DigestNotFoundError:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    except DigestNotEditableError:
        raise HTTPException(
            status_code=409, detail="当前版本不可编辑，请先重新生成新版本"
        ) from None
    except DigestItemNotFoundError:
        raise HTTPException(status_code=404, detail="条目不存在") from None
    return MessageResponse(message="条目已剔除")


@router.post("/restore/{item_type}/{item_ref_id}", response_model=MessageResponse)
async def restore_item(
    item_type: str,
    item_ref_id: int,
    svc: DigestService = Depends(get_digest_service),
    _admin: str = Depends(get_current_admin),
) -> MessageResponse:
    """恢复条目。"""
    try:
        await svc.restore_item(item_type, item_ref_id)
    except DigestNotFoundError:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    except DigestNotEditableError:
        raise HTTPException(
            status_code=409, detail="当前版本不可编辑，请先重新生成新版本"
        ) from None
    except DigestItemNotFoundError:
        raise HTTPException(status_code=404, detail="条目不存在") from None
    return MessageResponse(message="条目已恢复")
