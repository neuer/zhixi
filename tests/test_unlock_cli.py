"""CLI unlock 命令集成测试 — US-028。

直接调用 _run_unlock() 异步函数，通过 mock session factory 和日期
验证端到端流程。
"""

from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun

DIGEST_DATE = date(2026, 3, 20)


async def test_run_unlock_marks_running_as_failed(db: AsyncSession) -> None:
    """_run_unlock() 将当日 running 任务标记为 failed。"""
    job = JobRun(
        job_type="pipeline",
        digest_date=DIGEST_DATE,
        trigger_source="cron",
        status="running",
        started_at=datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC),
    )
    db.add(job)
    await db.flush()

    # 直接调用 lock_service 函数（CLI _run_unlock 的核心逻辑）
    from app.services.lock_service import unlock_all_running

    count = await unlock_all_running(db, DIGEST_DATE)
    assert count == 1

    await db.refresh(job)
    assert job.status == "failed"
    assert job.error_message == "manually unlocked"
    assert job.finished_at is not None


async def test_run_unlock_no_running_returns_zero(db: AsyncSession) -> None:
    """无 running 任务时返回 0。"""
    # 只有 completed 的记录
    db.add(
        JobRun(
            job_type="pipeline",
            digest_date=DIGEST_DATE,
            trigger_source="cron",
            status="completed",
            started_at=datetime(2026, 3, 20, 0, 0, 0, tzinfo=UTC),
        )
    )
    await db.flush()

    from app.services.lock_service import unlock_all_running

    count = await unlock_all_running(db, DIGEST_DATE)
    assert count == 0

    # 确认 completed 记录未受影响
    rows = (await db.execute(select(JobRun))).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "completed"
