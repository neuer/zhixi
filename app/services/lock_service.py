"""任务幂等锁服务 — 防止同日同类型任务重复执行（US-028）。"""

import logging
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun

logger = logging.getLogger(__name__)

STALE_THRESHOLD_HOURS = 2
"""running 超过此时长视为残留，自动标记 failed。"""


async def has_running_job(db: AsyncSession, job_type: str, digest_date: date) -> bool:
    """基本锁：检查当日指定 job_type 是否存在 running 的任务。"""
    result = await db.execute(
        select(JobRun.id)
        .where(
            JobRun.job_type == job_type,
            JobRun.digest_date == digest_date,
            JobRun.status == "running",
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def has_running_pipeline(db: AsyncSession, digest_date: date) -> bool:
    """增强锁：检查当日是否存在 running 的 pipeline 任务。"""
    return await has_running_job(db, "pipeline", digest_date)


async def clean_stale_jobs(db: AsyncSession, digest_date: date) -> int:
    """自动清理：将当日 running 超过阈值的任务标记为 failed。

    在 pipeline 启动时调用。返回清理的记录数。
    """
    cutoff = datetime.now(UTC) - timedelta(hours=STALE_THRESHOLD_HOURS)
    result = await db.execute(
        update(JobRun)
        .where(
            JobRun.digest_date == digest_date,
            JobRun.status == "running",
            JobRun.started_at < cutoff,
        )
        .values(
            status="failed",
            error_message=f"超时自动清理(>{STALE_THRESHOLD_HOURS}h)",
            finished_at=datetime.now(UTC),
        )
    )
    count = result.rowcount  # type: ignore[assignment]
    if count > 0:
        logger.info("清理了 %d 个超时 running 任务（digest_date=%s）", count, digest_date)
    return count  # type: ignore[return-value]


async def unlock_all_running(db: AsyncSession, digest_date: date) -> int:
    """解锁当日所有 running 任务（CLI unlock 命令调用）。

    将 status 改为 failed，error_message 设为 'manually unlocked'。
    返回解锁的记录数。
    """
    result = await db.execute(
        update(JobRun)
        .where(
            JobRun.digest_date == digest_date,
            JobRun.status == "running",
        )
        .values(
            status="failed",
            error_message="manually unlocked",
            finished_at=datetime.now(UTC),
        )
    )
    count = result.rowcount  # type: ignore[assignment]
    if count > 0:
        logger.info("手动解锁了 %d 个 running 任务（digest_date=%s）", count, digest_date)
    return count  # type: ignore[return-value]
