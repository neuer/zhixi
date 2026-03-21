"""手动操作路由 — 手动触发抓取、封面图生成等。"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, require_no_pipeline_lock
from app.clients.gemini_client import get_gemini_client
from app.config import get_system_config, get_today_digest_date
from app.database import get_db
from app.digest.cover_generator import generate_cover_image
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.job_run import JobRun
from app.schemas.enums import JobStatus, JobType, TriggerSource
from app.schemas.pipeline_types import ManualCoverResponse, ManualFetchResponse
from app.services.fetch_service import FetchService
from app.services.lock_service import has_running_job

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/fetch", response_model=ManualFetchResponse)
async def manual_fetch(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
    _lock: None = Depends(require_no_pipeline_lock),
) -> ManualFetchResponse | JSONResponse:
    """手动触发抓取（仅 fetch，不触发 process/digest）。

    成功: 200 {"message": "抓取完成", "job_run_id": N, "new_tweets": N}
    增强锁: 同日有 pipeline running → 409（由 require_no_pipeline_lock 处理）
    基本锁: 同日有 fetch running → 409
    失败: 500 {"detail": "抓取失败: ..."}（用 JSONResponse 保证 job_run 持久化）
    """
    digest_date = get_today_digest_date()

    # 基本锁：同日 fetch 已 running → 409
    if await has_running_job(db, JobType.FETCH, digest_date):
        raise HTTPException(
            status_code=409,
            detail="当前有任务在运行中，请稍后再试",
        )

    # 创建 job_run
    job_run = JobRun(
        job_type=JobType.FETCH,
        digest_date=digest_date,
        trigger_source=TriggerSource.MANUAL,
        status=JobStatus.RUNNING,
        started_at=datetime.now(UTC),
    )
    db.add(job_run)
    await db.flush()

    try:
        fetch_svc = FetchService(db)
        result = await fetch_svc.run_daily_fetch(digest_date)

        job_run.status = JobStatus.COMPLETED
        job_run.finished_at = datetime.now(UTC)

        logger.info(
            "手动抓取完成: new_tweets=%d, job_run_id=%d",
            result.new_tweets_count,
            job_run.id,
        )
        return ManualFetchResponse(
            message="抓取完成",
            job_run_id=job_run.id,
            new_tweets=result.new_tweets_count,
        )

    except Exception as exc:
        error_msg = str(exc)[:500]
        job_run.status = JobStatus.FAILED
        job_run.error_message = error_msg
        job_run.finished_at = datetime.now(UTC)

        logger.error("手动抓取失败: %s", error_msg, exc_info=True)

        # 用 JSONResponse 而非 HTTPException，保证 get_db() 正常 commit
        return JSONResponse(
            status_code=500,
            content={"detail": "抓取失败，请稍后重试"},
        )


@router.post("/generate-cover", response_model=ManualCoverResponse)
async def manual_generate_cover(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> ManualCoverResponse | JSONResponse:
    """手动触发封面图生成（US-026）。

    成功: 200 {"message": "封面图生成成功", "cover_path": "..."}
    功能未开启: 400 "封面图功能未开启"
    Key 未配置: 400 "Gemini API Key 未配置"
    无草稿: 404 "当日无可编辑草稿"
    生成失败: 500 "封面图生成失败"
    """
    # 检查功能开关
    enable_cover = await get_system_config(db, "enable_cover_generation", "false")
    if enable_cover.lower() != "true":
        raise HTTPException(status_code=400, detail="封面图功能未开启")

    # 检查 Gemini API Key
    gemini_client = get_gemini_client()
    if gemini_client is None:
        raise HTTPException(status_code=400, detail="Gemini API Key 未配置")

    # 查找当日草稿
    digest_date = get_today_digest_date()
    stmt = select(DailyDigest).where(
        DailyDigest.digest_date == digest_date,
        DailyDigest.is_current.is_(True),
    )
    result = await db.execute(stmt)
    digest = result.scalar_one_or_none()
    if digest is None:
        raise HTTPException(status_code=404, detail="当日无可编辑草稿")

    # 查询 digest_items
    items_stmt = (
        select(DigestItem)
        .where(
            DigestItem.digest_id == digest.id,
            DigestItem.is_excluded.is_(False),
        )
        .order_by(DigestItem.display_order)
    )
    items_result = await db.execute(items_stmt)
    items = list(items_result.scalars())

    # 生成封面图
    cover_timeout = float(await get_system_config(db, "cover_generation_timeout", "30"))
    cover_path = await generate_cover_image(
        gemini_client=gemini_client,
        top_items=items[:5],
        digest_date=digest_date,
        timeout=cover_timeout,
        db=db,
    )

    if cover_path is None:
        return JSONResponse(
            status_code=500,
            content={"detail": "封面图生成失败"},
        )

    digest.cover_image_path = cover_path
    logger.info("手动封面图生成成功: %s", cover_path)
    return ManualCoverResponse(message="封面图生成成功", cover_path=cover_path)
