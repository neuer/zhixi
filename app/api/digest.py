"""digest 路由 — 日报查看与操作。"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, get_digest_service, require_no_pipeline_lock
from app.clients.claude_client import get_claude_client
from app.clients.notifier import send_alert
from app.config import get_system_config, get_today_digest_date
from app.database import get_db
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.job_run import JobRun
from app.schemas.digest_types import (
    AddTweetRequest,
    AddTweetResponse,
    DigestBriefResponse,
    DigestItemResponse,
    EditItemRequest,
    EditSummaryRequest,
    MarkdownResponse,
    MessageResponse,
    PreviewLinkResponse,
    PreviewResponse,
    ReorderRequest,
    TodayResponse,
)
from app.services.digest_service import (
    DigestItemNotFoundError,
    DigestNotEditableError,
    DigestNotFoundError,
    DigestService,
    PreviewTokenInvalidError,
)
from app.services.fetch_service import FetchService, TweetAlreadyExistsError
from app.services.lock_service import has_running_job
from app.services.process_service import ProcessService

logger = logging.getLogger(__name__)

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


# ── US-038: 预览功能（登录态） ──


@router.get("/preview", response_model=PreviewResponse)
async def get_preview(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> PreviewResponse:
    """预览当日日报（登录态）。

    返回当日 is_current=true 的 digest + items + Markdown。
    """
    digest_date = get_today_digest_date()

    stmt = select(DailyDigest).where(
        DailyDigest.digest_date == digest_date,
        DailyDigest.is_current.is_(True),
    )
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()

    if digest is None:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None

    items_stmt = (
        select(DigestItem)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.display_order)
    )
    items_result = await db.execute(items_stmt)
    items = list(items_result.scalars().all())

    return PreviewResponse(
        digest=DigestBriefResponse.model_validate(digest),
        items=[DigestItemResponse.model_validate(item) for item in items],
        content_markdown=digest.content_markdown or "",
    )


# ── US-009: 预览签名链接 ──


@router.post("/preview-link", response_model=PreviewLinkResponse)
async def create_preview_link(
    svc: DigestService = Depends(get_digest_service),
    _admin: str = Depends(get_current_admin),
) -> PreviewLinkResponse:
    """生成预览签名链接（管理员操作）。

    token 有效期 24h，同一 digest 只允许一个有效 token。
    """
    try:
        token, expires_at = await svc.generate_preview_link()
    except DigestNotFoundError:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    return PreviewLinkResponse(token=token, expires_at=expires_at)


@router.get("/preview/{token}", response_model=PreviewResponse)
async def get_preview_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> PreviewResponse:
    """根据签名 token 获取预览内容（匿名访问）。

    无效/过期/版本失效 token 返回 403。
    """
    svc = DigestService(db, claude_client=get_claude_client())
    try:
        digest, items = await svc.get_preview_by_token(token)
    except PreviewTokenInvalidError:
        raise HTTPException(status_code=403, detail="链接已失效或过期") from None
    return PreviewResponse(
        digest=DigestBriefResponse.model_validate(digest),
        items=[DigestItemResponse.model_validate(item) for item in items],
        content_markdown=digest.content_markdown or "",
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


# ── US-035: 重新生成草稿 ──


@router.post("/regenerate", response_model=None)
async def regenerate_digest(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
    _lock: None = Depends(require_no_pipeline_lock),
) -> dict[str, object] | JSONResponse:
    """重新生成草稿（同步执行，可能耗时数分钟）。

    流程：重置推文 → M2 全量重跑 → M3 新版本。
    增强锁：同日有 pipeline running → 409。
    """
    digest_date = get_today_digest_date()

    # 基本锁：同日 pipeline 已 running → 409
    if await has_running_job(db, "pipeline", digest_date):
        raise HTTPException(
            status_code=409,
            detail="当前有任务在运行中，请稍后再试",
        ) from None

    # 创建 job_run
    job_run = JobRun(
        job_type="pipeline",
        digest_date=digest_date,
        trigger_source="regenerate",
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(job_run)
    await db.flush()

    try:
        claude = get_claude_client()
        svc = DigestService(db, claude_client=claude)
        new_digest = await svc.regenerate_digest(digest_date)

        job_run.status = "completed"
        job_run.finished_at = datetime.now(UTC)

        return {
            "message": "重新生成完成",
            "digest_id": new_digest.id,
            "version": new_digest.version,
            "item_count": new_digest.item_count,
            "job_run_id": job_run.id,
        }

    except Exception as exc:
        error_msg = str(exc)[:500]
        job_run.status = "failed"
        job_run.error_message = error_msg
        job_run.finished_at = datetime.now(UTC)

        logger.error("重新生成失败: %s", error_msg, exc_info=True)

        try:
            await send_alert("重新生成失败", f"错误: {error_msg}", db)
        except Exception:
            logger.warning("重新生成失败通知发送也失败", exc_info=True)

        # JSONResponse 保证 job_run 持久化
        return JSONResponse(
            status_code=500,
            content={"detail": f"重新生成失败: {str(exc)[:200]}"},
        )


# ── US-036: 手动发布模式 ──


@router.get("/markdown", response_model=MarkdownResponse)
async def get_markdown(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> MarkdownResponse:
    """获取当日 Markdown 内容（供一键复制）。"""
    digest_date = get_today_digest_date()
    stmt = select(DailyDigest).where(
        DailyDigest.digest_date == digest_date,
        DailyDigest.is_current.is_(True),
    )
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()

    if digest is None:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None

    return MarkdownResponse(content_markdown=digest.content_markdown or "")


@router.post("/mark-published", response_model=None)
async def mark_published(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
    _lock: None = Depends(require_no_pipeline_lock),
) -> MessageResponse | JSONResponse:
    """标记当前草稿为已发布。根据 publish_mode 分支：manual 直接标记，api 返回 501。"""
    # 检查 publish_mode
    publish_mode = await get_system_config(db, "publish_mode", "manual")
    if publish_mode == "api":
        return JSONResponse(
            status_code=501,
            content={"detail": "微信API自动发布功能将在公众号认证后实现"},
        )

    digest_date = get_today_digest_date()
    stmt = select(DailyDigest).where(
        DailyDigest.digest_date == digest_date,
        DailyDigest.is_current.is_(True),
    )
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()

    if digest is None:
        raise HTTPException(status_code=404, detail="今日草稿不存在") from None
    if digest.status == "published":
        raise HTTPException(status_code=409, detail="该版本已发布") from None

    digest.status = "published"
    digest.published_at = datetime.now(UTC)

    return MessageResponse(message="发布成功")


# ── US-016: 手动补录推文 ──


@router.post("/add-tweet", response_model=None)
async def add_tweet(
    body: AddTweetRequest,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> AddTweetResponse | JSONResponse:
    """手动补录推文 — M1 抓取 → 入库 → M2 AI 加工 → M3 热度计算 + 建 item。"""
    digest_date = get_today_digest_date()
    claude = get_claude_client()

    # 前置检查：当日必须有可编辑草稿
    digest_svc = DigestService(db, claude_client=claude)
    try:
        await digest_svc._get_current_draft(digest_date)  # noqa: SLF001
    except DigestNotFoundError:
        raise HTTPException(
            status_code=409,
            detail="今日草稿尚未生成，请等待 pipeline 完成或手动触发后再补录",
        ) from None
    except DigestNotEditableError:
        raise HTTPException(
            status_code=409,
            detail="当前版本不可编辑",
        ) from None

    # M1: 抓取 + 入库
    fetch_svc = FetchService(db)
    try:
        tweet = await fetch_svc.fetch_single_tweet(body.tweet_url, digest_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的推文URL") from None
    except TweetAlreadyExistsError:
        raise HTTPException(status_code=409, detail="该推文已存在") from None
    except Exception:
        raise HTTPException(status_code=502, detail="推文抓取失败") from None

    # M2: AI 加工（失败时推文保留但不建 item）
    process_svc = ProcessService(db, claude_client=claude)
    try:
        await process_svc.process_single_tweet_by_id(tweet.id)
    except Exception as exc:
        logger.warning("手动补录 AI 加工失败: %s", exc)
        return JSONResponse(
            status_code=502,
            content={"detail": "推文已入库但AI加工失败，将在下次重新生成时处理"},
        )

    # M3: 热度计算 + 建 digest_item
    try:
        item = await digest_svc.add_manual_tweet_item(tweet, digest_date)
    except DigestNotFoundError:
        raise HTTPException(
            status_code=409,
            detail="今日草稿尚未生成，请等待 pipeline 完成或手动触发后再补录",
        ) from None
    except DigestNotEditableError:
        raise HTTPException(status_code=409, detail="当前版本不可编辑") from None

    return AddTweetResponse(
        message="补录成功",
        item=DigestItemResponse.model_validate(item),
    )
