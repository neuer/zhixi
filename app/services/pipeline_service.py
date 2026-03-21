"""pipeline_service — 每日主流程编排（US-027）。

编排 fetch → process → digest 三步流水线。
采用模块级函数（非 class），内部创建各 Service 实例。
"""

import logging
from datetime import UTC, date, datetime
from typing import Literal

import sqlalchemy.exc
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import get_claude_client
from app.clients.notifier import send_alert
from app.config import get_system_config, get_today_digest_date
from app.models.job_run import JobRun
from app.schemas.enums import JobStatus
from app.schemas.fetcher_types import FetchResult
from app.schemas.pipeline_types import PipelineResult
from app.schemas.processor_types import ProcessResult
from app.services.digest_service import DigestService
from app.services.fetch_service import FetchService
from app.services.lock_service import clean_stale_jobs, has_running_job
from app.services.process_service import ProcessService

logger = logging.getLogger(__name__)


async def run_pipeline(
    db: AsyncSession,
    trigger_source: str = "cron",
) -> PipelineResult:
    """执行每日 Pipeline 主流程：fetch → process → digest。

    不在推送日或已有 running pipeline 时返回 skipped。
    业务异常在内部捕获，更新 job_run 状态后返回 PipelineResult。
    调用方只需 commit 即可。
    """
    digest_date = get_today_digest_date()

    # ── 1. 检查推送日 ──────────────────────────────────────
    push_days_str = await get_system_config(db, "push_days", "1,2,3,4,5,6,7")
    today_weekday = str(digest_date.isoweekday())
    if today_weekday not in push_days_str.split(","):
        job_run = _create_job_run(digest_date, trigger_source, status="skipped")
        db.add(job_run)
        await db.flush()
        logger.info(
            "非推送日（weekday=%s, push_days=%s），跳过 pipeline", today_weekday, push_days_str
        )
        return PipelineResult(
            status="skipped",
            digest_date=digest_date,
            job_run_id=job_run.id,
            error_message="非推送日",
        )

    # ── 2. 清理超时 running 任务 ──────────────────────────
    cleaned = await clean_stale_jobs(db, digest_date)
    if cleaned > 0:
        logger.info("已清理 %d 个超时 running 任务", cleaned)

    # ── 3. 检查锁 ────────────────────────────────────────
    if await has_running_job(db, "pipeline", digest_date):
        logger.warning("同日已有 running pipeline，跳过")
        return PipelineResult(
            status="skipped",
            digest_date=digest_date,
            error_message="pipeline already running",
        )

    # ── 4. 创建 job_run ──────────────────────────────────
    job_run = _create_job_run(digest_date, trigger_source)
    db.add(job_run)
    await db.flush()

    # ── 5. 执行三步流水线 ────────────────────────────────
    fetch_result = None
    process_result = None

    try:
        # Step A: Fetch
        fetch_svc = FetchService(db)
        fetch_result = await fetch_svc.run_daily_fetch(digest_date)
        logger.info("Fetch 完成: new_tweets=%d", fetch_result.new_tweets_count)

        # Step B: Process
        claude = get_claude_client()
        process_svc = ProcessService(db, claude_client=claude)
        process_result = await process_svc.run_daily_process(digest_date)
        logger.info(
            "Process 完成: processed=%d, topics=%d",
            process_result.processed_count,
            process_result.topic_count,
        )

        # Step C: Digest
        digest_svc = DigestService(db, claude_client=claude)
        await digest_svc.generate_daily_digest(digest_date)
        logger.info("Digest 生成完成")

        # ── 成功 ──
        job_run.status = JobStatus.COMPLETED
        job_run.finished_at = datetime.now(UTC)
        return PipelineResult(
            status="completed",
            digest_date=digest_date,
            job_run_id=job_run.id,
            fetch_result=fetch_result,
            process_result=process_result,
        )

    except (sqlalchemy.exc.SQLAlchemyError, OSError) as exc:
        # 基础设施异常不可恢复，向上传播
        logger.critical("Pipeline 基础设施异常: %s", exc, exc_info=True)
        raise
    except Exception as exc:
        failed_step = _determine_failed_step(fetch_result, process_result)
        error_msg = str(exc)[:500]

        job_run.status = JobStatus.FAILED
        job_run.error_message = error_msg
        job_run.finished_at = datetime.now(UTC)

        logger.error("Pipeline 在 [%s] 步骤失败: %s", failed_step, error_msg, exc_info=True)

        # 发送 webhook 通知（失败仅日志，不影响返回）
        try:
            await send_alert(
                "Pipeline 失败",
                f"环节: {failed_step}\n错误: {error_msg}",
                db,
            )
        except Exception:
            logger.warning("Pipeline 失败通知发送也失败", exc_info=True)

        return PipelineResult(
            status="failed",
            digest_date=digest_date,
            job_run_id=job_run.id,
            error_message=error_msg,
            failed_step=failed_step,
            fetch_result=fetch_result,
            process_result=process_result,
        )


def _create_job_run(
    digest_date: date,
    trigger_source: str,
    status: str = "running",
) -> JobRun:
    """创建 job_run 记录。"""
    return JobRun(
        job_type="pipeline",
        digest_date=digest_date,
        trigger_source=trigger_source,
        status=status,
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC) if status == "skipped" else None,
    )


def _determine_failed_step(
    fetch_result: FetchResult | None,
    process_result: ProcessResult | None,
) -> Literal["fetch", "process", "digest"]:
    """根据已完成的步骤判断失败的步骤。"""
    if fetch_result is None:
        return "fetch"
    if process_result is None:
        return "process"
    return "digest"
