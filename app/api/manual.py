"""手动操作路由 — 手动触发抓取等（US-027b）。"""

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin, require_no_pipeline_lock
from app.config import get_today_digest_date
from app.database import get_db
from app.models.job_run import JobRun
from app.services.fetch_service import FetchService
from app.services.lock_service import has_running_job

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/fetch", response_model=None)
async def manual_fetch(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
    _lock: None = Depends(require_no_pipeline_lock),
) -> dict[str, object] | JSONResponse:
    """手动触发抓取（仅 fetch，不触发 process/digest）。

    成功: 200 {"message": "抓取完成", "job_run_id": N, "new_tweets": N}
    增强锁: 同日有 pipeline running → 409（由 require_no_pipeline_lock 处理）
    基本锁: 同日有 fetch running → 409
    失败: 500 {"detail": "抓取失败: ..."}（用 JSONResponse 保证 job_run 持久化）
    """
    digest_date = get_today_digest_date()

    # 基本锁：同日 fetch 已 running → 409
    if await has_running_job(db, "fetch", digest_date):
        raise HTTPException(
            status_code=409,
            detail="当前有任务在运行中，请稍后再试",
        ) from None

    # 创建 job_run
    job_run = JobRun(
        job_type="fetch",
        digest_date=digest_date,
        trigger_source="manual",
        status="running",
        started_at=datetime.now(UTC),
    )
    db.add(job_run)
    await db.flush()

    try:
        fetch_svc = FetchService(db)
        result = await fetch_svc.run_daily_fetch(digest_date)

        job_run.status = "completed"
        job_run.finished_at = datetime.now(UTC)

        logger.info(
            "手动抓取完成: new_tweets=%d, job_run_id=%d",
            result.new_tweets_count,
            job_run.id,
        )
        return {
            "message": "抓取完成",
            "job_run_id": job_run.id,
            "new_tweets": result.new_tweets_count,
        }

    except Exception as exc:
        error_msg = str(exc)[:500]
        job_run.status = "failed"
        job_run.error_message = error_msg
        job_run.finished_at = datetime.now(UTC)

        logger.error("手动抓取失败: %s", error_msg, exc_info=True)

        # 用 JSONResponse 而非 HTTPException，保证 get_db() 正常 commit
        return JSONResponse(
            status_code=500,
            content={"detail": f"抓取失败: {str(exc)[:200]}"},
        )
