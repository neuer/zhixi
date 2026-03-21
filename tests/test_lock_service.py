"""锁服务单元测试 — US-028 任务幂等锁。"""

from datetime import UTC, date, datetime

import pytest
from fastapi import HTTPException
from freezegun import freeze_time
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun
from app.schemas.enums import JobType
from app.services.lock_service import (
    clean_stale_jobs,
    has_running_job,
    has_running_pipeline,
    unlock_all_running,
)

DIGEST_DATE = date(2026, 3, 20)
OTHER_DATE = date(2026, 3, 19)


# ── 辅助函数 ──────────────────────────────────────────────


def _make_job(
    job_type: str = "pipeline",
    digest_date: date = DIGEST_DATE,
    status: str = "running",
    trigger_source: str = "cron",
    started_at: datetime | None = None,
) -> JobRun:
    """构造 JobRun 测试对象。"""
    return JobRun(
        job_type=job_type,
        digest_date=digest_date,
        trigger_source=trigger_source,
        status=status,
        started_at=started_at or datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC),
    )


# ── has_running_job 基本锁 ──────────────────────────────────


async def test_has_running_job_true_when_running_exists(db: AsyncSession) -> None:
    """同日同 job_type 有 running 记录 → True。"""
    db.add(_make_job(job_type="pipeline", status="running"))
    await db.flush()

    result = await has_running_job(db, JobType.PIPELINE, DIGEST_DATE)
    assert result is True


async def test_has_running_job_false_when_no_running(db: AsyncSession) -> None:
    """同日同 job_type 无 running（completed/failed）→ False。"""
    db.add(_make_job(job_type="pipeline", status="completed"))
    db.add(_make_job(job_type="pipeline", status="failed"))
    await db.flush()

    result = await has_running_job(db, JobType.PIPELINE, DIGEST_DATE)
    assert result is False


async def test_has_running_job_false_different_date(db: AsyncSession) -> None:
    """不同日期的 running 不影响当日检查。"""
    db.add(_make_job(job_type="pipeline", digest_date=OTHER_DATE, status="running"))
    await db.flush()

    result = await has_running_job(db, JobType.PIPELINE, DIGEST_DATE)
    assert result is False


async def test_has_running_job_false_different_type(db: AsyncSession) -> None:
    """不同 job_type 的 running 不影响当日检查。"""
    db.add(_make_job(job_type="fetch", status="running"))
    await db.flush()

    result = await has_running_job(db, JobType.PIPELINE, DIGEST_DATE)
    assert result is False


async def test_has_running_job_false_empty_table(db: AsyncSession) -> None:
    """空表 → False。"""
    result = await has_running_job(db, JobType.PIPELINE, DIGEST_DATE)
    assert result is False


# ── has_running_pipeline 增强锁 ─────────────────────────────


async def test_has_running_pipeline_true(db: AsyncSession) -> None:
    """当日有 pipeline running → True。"""
    db.add(_make_job(job_type="pipeline", status="running"))
    await db.flush()

    result = await has_running_pipeline(db, DIGEST_DATE)
    assert result is True


async def test_has_running_pipeline_false_non_pipeline(db: AsyncSession) -> None:
    """当日有 fetch running 但无 pipeline running → False。"""
    db.add(_make_job(job_type="fetch", status="running"))
    await db.flush()

    result = await has_running_pipeline(db, DIGEST_DATE)
    assert result is False


# ── clean_stale_jobs 过期清理 ────────────────────────────────


@freeze_time("2026-03-20T06:00:00+00:00")
async def test_clean_stale_jobs_marks_old_as_failed(db: AsyncSession) -> None:
    """>2h 的 running → failed + error_message。"""
    old_job = _make_job(
        status="running",
        started_at=datetime(2026, 3, 20, 3, 0, 0, tzinfo=UTC),  # 3h 前
    )
    db.add(old_job)
    await db.flush()

    count = await clean_stale_jobs(db, DIGEST_DATE)
    assert count == 1

    await db.refresh(old_job)
    assert old_job.status == "failed"
    assert old_job.error_message is not None
    assert "超时" in old_job.error_message
    assert old_job.finished_at is not None


@freeze_time("2026-03-20T06:00:00+00:00")
async def test_clean_stale_jobs_keeps_recent(db: AsyncSession) -> None:
    """<2h 的 running 不被清理。"""
    recent_job = _make_job(
        status="running",
        started_at=datetime(2026, 3, 20, 5, 0, 0, tzinfo=UTC),  # 1h 前
    )
    db.add(recent_job)
    await db.flush()

    count = await clean_stale_jobs(db, DIGEST_DATE)
    assert count == 0

    await db.refresh(recent_job)
    assert recent_job.status == "running"


@freeze_time("2026-03-20T06:00:00+00:00")
async def test_clean_stale_jobs_returns_count(db: AsyncSession) -> None:
    """返回清理的记录数。"""
    # 两条过期 + 一条新鲜
    db.add(_make_job(status="running", started_at=datetime(2026, 3, 20, 2, 0, 0, tzinfo=UTC)))
    db.add(
        _make_job(
            job_type="fetch",
            status="running",
            started_at=datetime(2026, 3, 20, 1, 0, 0, tzinfo=UTC),
        )
    )
    db.add(
        _make_job(
            job_type="digest",
            status="running",
            started_at=datetime(2026, 3, 20, 5, 30, 0, tzinfo=UTC),
        )
    )
    await db.flush()

    count = await clean_stale_jobs(db, DIGEST_DATE)
    assert count == 2


# ── unlock_all_running 批量解锁 ──────────────────────────────


async def test_unlock_all_marks_running_failed(db: AsyncSession) -> None:
    """当日所有 running → failed + 'manually unlocked'。"""
    job = _make_job(status="running")
    db.add(job)
    await db.flush()

    count = await unlock_all_running(db, DIGEST_DATE)
    assert count == 1

    await db.refresh(job)
    assert job.status == "failed"
    assert job.error_message == "manually unlocked"


async def test_unlock_preserves_non_running(db: AsyncSession) -> None:
    """completed/failed 记录不受影响。"""
    completed_job = _make_job(status="completed")
    failed_job = _make_job(status="failed")
    db.add(completed_job)
    db.add(failed_job)
    await db.flush()

    count = await unlock_all_running(db, DIGEST_DATE)
    assert count == 0

    await db.refresh(completed_job)
    await db.refresh(failed_job)
    assert completed_job.status == "completed"
    assert failed_job.status == "failed"


async def test_unlock_returns_count(db: AsyncSession) -> None:
    """返回解锁的记录数。"""
    db.add(_make_job(job_type="pipeline", status="running"))
    db.add(_make_job(job_type="fetch", status="running"))
    db.add(_make_job(job_type="digest", status="completed"))
    await db.flush()

    count = await unlock_all_running(db, DIGEST_DATE)
    assert count == 2


async def test_unlock_sets_finished_at(db: AsyncSession) -> None:
    """解锁后 finished_at 被填充。"""
    job = _make_job(status="running")
    db.add(job)
    await db.flush()
    assert job.finished_at is None

    await unlock_all_running(db, DIGEST_DATE)
    await db.refresh(job)
    assert job.finished_at is not None


# ── require_no_pipeline_lock 增强锁依赖 ──────────────────────


@freeze_time("2026-03-20 08:00:00+08:00")
async def test_require_no_pipeline_lock_raises_409(db: AsyncSession) -> None:
    """当日有 pipeline running → HTTPException(409)。"""
    from app.api.deps import require_no_pipeline_lock

    db.add(_make_job(job_type="pipeline", status="running"))
    await db.flush()

    with pytest.raises(HTTPException) as exc_info:
        await require_no_pipeline_lock(db)
    assert exc_info.value.status_code == 409
    assert "当前有任务在运行中" in str(exc_info.value.detail)


async def test_require_no_pipeline_lock_passes(db: AsyncSession) -> None:
    """当日无 pipeline running → 正常通过。"""
    from app.api.deps import require_no_pipeline_lock

    # 无任何 job，不应抛异常
    await require_no_pipeline_lock(db)


async def test_require_no_pipeline_lock_ignores_completed(db: AsyncSession) -> None:
    """已完成的 pipeline 不触发锁。"""
    from app.api.deps import require_no_pipeline_lock

    db.add(_make_job(job_type="pipeline", status="completed"))
    await db.flush()

    await require_no_pipeline_lock(db)
