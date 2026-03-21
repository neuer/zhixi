"""pipeline_service 单元测试（US-027）。"""

from contextlib import ExitStack
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun
from app.schemas.enums import TriggerSource
from app.schemas.fetcher_types import FetchResult
from app.schemas.processor_types import ProcessResult

# ── fixtures ──────────────────────────────────────────────


@pytest.fixture
def mock_fetch() -> AsyncMock:
    """Mock FetchService.run_daily_fetch。"""
    return AsyncMock(
        return_value=FetchResult(
            new_tweets_count=10,
            fail_count=0,
            total_accounts=5,
        )
    )


@pytest.fixture
def mock_process() -> AsyncMock:
    """Mock ProcessService.run_daily_process。"""
    return AsyncMock(
        return_value=ProcessResult(
            processed_count=8,
            filtered_count=2,
            topic_count=3,
        )
    )


@pytest.fixture
def mock_digest() -> AsyncMock:
    """Mock DigestService.generate_daily_digest — 返回简单对象。"""
    mock = AsyncMock()
    mock.return_value = AsyncMock(id=1)
    return mock


@pytest.fixture
def mock_alert() -> AsyncMock:
    """Mock send_alert。"""
    return AsyncMock()


def _seed_push_days(db_add_fn: AsyncSession, push_days: str = "1,2,3,4,5,6,7") -> None:
    """向 system_config 写入 push_days。"""
    from app.models.config import SystemConfig

    db_add_fn.add(SystemConfig(key="push_days", value=push_days))


_MODULE = "app.services.pipeline_service"


def _patch_pipeline(
    mock_fetch: AsyncMock,
    mock_process: AsyncMock,
    mock_digest: AsyncMock,
    mock_alert: AsyncMock,
) -> ExitStack:
    """用 ExitStack + patch 替代 patch.multiple，避免 pyright 类型推断问题。"""
    stack = ExitStack()
    stack.enter_context(
        patch(f"{_MODULE}.FetchService", _make_service_class(mock_fetch, "run_daily_fetch"))
    )
    stack.enter_context(
        patch(f"{_MODULE}.ProcessService", _make_service_class(mock_process, "run_daily_process"))
    )
    stack.enter_context(
        patch(f"{_MODULE}.DigestService", _make_service_class(mock_digest, "generate_daily_digest"))
    )
    stack.enter_context(patch(f"{_MODULE}.send_alert", mock_alert))
    stack.enter_context(
        patch("app.clients.claude_client.get_claude_client", AsyncMock(return_value=AsyncMock()))
    )
    return stack


def _make_service_class(method_mock: AsyncMock, method_name: str) -> type:
    """创建模拟 Service 类：构造函数接受任意参数，指定方法返回 mock。"""

    class MockService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    setattr(MockService, method_name, method_mock)
    return MockService


# ── 测试用例 ──────────────────────────────────────────────


@freeze_time("2026-03-20 08:00:00+08:00")  # 北京时间周五
class TestPipelineHappyPath:
    """全流程成功。"""

    async def test_pipeline_completed(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """fetch → process → digest 全部成功，job_run 状态为 completed。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        await db.flush()

        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "completed"
        assert result.digest_date == date(2026, 3, 20)
        assert result.job_run_id is not None
        assert result.fetch_result is not None
        assert result.process_result is not None

        # 验证 job_run 记录
        job_run = (
            await db.execute(select(JobRun).where(JobRun.id == result.job_run_id))
        ).scalar_one()
        assert job_run.status == "completed"
        assert job_run.job_type == "pipeline"
        assert job_run.trigger_source == "cron"
        assert job_run.finished_at is not None

        # 三个 service 都被调用
        mock_fetch.assert_awaited_once()
        mock_process.assert_awaited_once()
        mock_digest.assert_awaited_once()

        # 成功不发通知
        mock_alert.assert_not_awaited()


@freeze_time("2026-03-22 08:00:00+08:00")  # 北京时间周日 isoweekday=7
class TestPipelineNotPushDay:
    """非推送日跳过。"""

    async def test_skipped_not_push_day(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """push_days 不含周日 → skipped。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db, "1,2,3,4,5")  # 周一~周五
        await db.flush()

        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "skipped"

        # job_run 记录 status=skipped
        rows = (await db.execute(select(JobRun).where(JobRun.status == "skipped"))).scalars().all()
        assert len(rows) == 1
        assert rows[0].job_type == "pipeline"

        # service 均未调用
        mock_fetch.assert_not_awaited()


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPipelineFetchFails:
    """fetch 步骤失败。"""

    async def test_failed_at_fetch(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """fetch 抛异常 → failed + webhook。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        await db.flush()

        mock_fetch.side_effect = RuntimeError("X API timeout")
        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "failed"
        assert result.failed_step == "fetch"
        assert "X API timeout" in (result.error_message or "")

        # job_run 记录
        job_run = (
            await db.execute(select(JobRun).where(JobRun.id == result.job_run_id))
        ).scalar_one()
        assert job_run.status == "failed"

        # webhook 被调用
        mock_alert.assert_awaited_once()

        # process/digest 未调用
        mock_process.assert_not_awaited()
        mock_digest.assert_not_awaited()


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPipelineProcessFails:
    """process 步骤失败。"""

    async def test_failed_at_process(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """process 抛异常 → failed，fetch 已调用。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        await db.flush()

        mock_process.side_effect = RuntimeError("Claude API error")
        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "failed"
        assert result.failed_step == "process"
        assert result.fetch_result is not None  # fetch 已完成
        mock_fetch.assert_awaited_once()
        mock_digest.assert_not_awaited()


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPipelineDigestFails:
    """digest 步骤失败。"""

    async def test_failed_at_digest(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """digest 抛异常 → failed。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        await db.flush()

        mock_digest.side_effect = RuntimeError("Digest creation error")
        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "failed"
        assert result.failed_step == "digest"
        assert result.fetch_result is not None
        assert result.process_result is not None


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPipelineAlreadyRunning:
    """已有 running pipeline 时跳过。"""

    async def test_skip_if_running(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """同日有 running pipeline → skipped，不创建新 job_run。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        # 预插入一个 running pipeline
        existing = JobRun(
            job_type="pipeline",
            digest_date=date(2026, 3, 20),
            trigger_source=TriggerSource.CRON,
            status="running",
            started_at=datetime.now(UTC),
        )
        db.add(existing)
        await db.flush()

        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "skipped"
        assert "already running" in (result.error_message or "").lower()

        # 不应创建新 job_run
        all_runs = (await db.execute(select(JobRun))).scalars().all()
        assert len(all_runs) == 1  # 只有预插入的那条

        mock_fetch.assert_not_awaited()


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPipelineStaleCleanup:
    """清理超时 running 后正常执行。"""

    async def test_stale_cleaned_then_runs(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """超时 running job 被清理后，新 pipeline 正常运行。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        # 3 小时前的 running pipeline（超过 2h 阈值）
        stale = JobRun(
            job_type="pipeline",
            digest_date=date(2026, 3, 20),
            trigger_source=TriggerSource.CRON,
            status="running",
            started_at=datetime.now(UTC) - timedelta(hours=3),
        )
        db.add(stale)
        await db.flush()

        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        # stale job 被清理
        await db.refresh(stale)
        assert stale.status == "failed"

        # 新 pipeline 正常完成
        assert result.status == "completed"


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPipelineWebhookFailure:
    """webhook 发送失败不影响结果。"""

    async def test_alert_failure_ignored(
        self,
        db: AsyncSession,
        mock_fetch: AsyncMock,
        mock_process: AsyncMock,
        mock_digest: AsyncMock,
        mock_alert: AsyncMock,
    ) -> None:
        """pipeline 失败 + webhook 也失败 → 返回 failed，无异常。"""
        from app.services.pipeline_service import run_pipeline

        _seed_push_days(db)
        await db.flush()

        mock_fetch.side_effect = RuntimeError("fetch error")
        mock_alert.side_effect = RuntimeError("webhook down")
        with _patch_pipeline(mock_fetch, mock_process, mock_digest, mock_alert):
            result = await run_pipeline(db, trigger_source=TriggerSource.CRON)

        assert result.status == "failed"
        assert result.failed_step == "fetch"
        # 无异常抛出，函数正常返回
