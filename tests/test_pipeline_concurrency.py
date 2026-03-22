"""Pipeline 并发启动互斥测试（R-8）。"""

import asyncio
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.job_run import JobRun
from app.schemas.enums import JobStatus, JobType, TriggerSource
from app.schemas.fetcher_types import FetchResult
from app.schemas.processor_types import ProcessResult
from tests.factories import seed_config_keys

_MODULE = "app.services.pipeline_service"


def _make_service_class(method_mock: AsyncMock, method_name: str) -> type:
    """创建模拟 Service 类：构造函数接受任意参数，指定方法返回 mock。"""

    class MockService:
        def __init__(self, *args: object, **kwargs: object) -> None:
            pass

    setattr(MockService, method_name, method_mock)
    return MockService


@freeze_time("2026-03-20 08:00:00+08:00")  # 北京时间周五
class TestConcurrentPipeline:
    """两个 pipeline 同时启动，只有一个应该成功运行。"""

    async def test_concurrent_pipeline_only_one_runs(self, db_engine) -> None:
        """使用两个独立 session 并发启动 pipeline，验证锁互斥。

        策略：让第一个 pipeline 的 fetch 步骤等待一个 Event，
        确保第二个 pipeline 在第一个仍处于 RUNNING 状态时启动。
        """
        from app.services.pipeline_service import run_pipeline

        factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

        # ── 预置配置（用临时 session 写入后提交） ──
        async with factory() as setup_session:
            await seed_config_keys(setup_session, push_days="1,2,3,4,5,6,7")
            await setup_session.commit()

        # ── 同步原语：让 pipeline-1 的 fetch 阻塞到 pipeline-2 开始 ──
        fetch_started = asyncio.Event()  # pipeline-1 进入 fetch 后 set
        allow_proceed = asyncio.Event()  # pipeline-2 启动后 set，让 pipeline-1 继续

        async def slow_fetch(*args: object, **kwargs: object) -> FetchResult:
            """模拟耗时的 fetch 步骤。"""
            fetch_started.set()
            await allow_proceed.wait()
            return FetchResult(new_tweets_count=5, fail_count=0, total_accounts=3)

        fast_fetch = AsyncMock(
            return_value=FetchResult(new_tweets_count=5, fail_count=0, total_accounts=3)
        )
        mock_process = AsyncMock(
            return_value=ProcessResult(processed_count=3, filtered_count=1, topic_count=2)
        )
        mock_digest = AsyncMock(return_value=AsyncMock(id=1))
        mock_alert = AsyncMock()
        mock_claude = AsyncMock(return_value=AsyncMock())

        # ── 运行两个 pipeline ──
        async def run_first() -> object:
            """Pipeline-1：使用 slow_fetch，进入 fetch 后阻塞等待。"""
            async with factory() as session:
                with (
                    patch(
                        f"{_MODULE}.FetchService",
                        _make_service_class(AsyncMock(side_effect=slow_fetch), "run_daily_fetch"),
                    ),
                    patch(
                        f"{_MODULE}.ProcessService",
                        _make_service_class(mock_process, "run_daily_process"),
                    ),
                    patch(
                        f"{_MODULE}.DigestService",
                        _make_service_class(mock_digest, "generate_daily_digest"),
                    ),
                    patch(f"{_MODULE}.send_alert", mock_alert),
                    patch("app.clients.claude_client.get_claude_client", mock_claude),
                ):
                    result = await run_pipeline(session, trigger_source=TriggerSource.CRON)
                    await session.commit()
                    return result

        async def run_second() -> object:
            """Pipeline-2：等 pipeline-1 进入 fetch 后再启动，应被锁阻止。"""
            await fetch_started.wait()
            async with factory() as session:
                with (
                    patch(
                        f"{_MODULE}.FetchService",
                        _make_service_class(fast_fetch, "run_daily_fetch"),
                    ),
                    patch(
                        f"{_MODULE}.ProcessService",
                        _make_service_class(mock_process, "run_daily_process"),
                    ),
                    patch(
                        f"{_MODULE}.DigestService",
                        _make_service_class(mock_digest, "generate_daily_digest"),
                    ),
                    patch(f"{_MODULE}.send_alert", mock_alert),
                    patch("app.clients.claude_client.get_claude_client", mock_claude),
                ):
                    result = await run_pipeline(session, trigger_source=TriggerSource.CRON)
                    # 拿到结果后放行 pipeline-1
                    allow_proceed.set()
                    await session.commit()
                    return result

        results = await asyncio.gather(run_first(), run_second())

        # ── 断言 ──
        statuses = sorted([r.status for r in results])  # type: ignore[union-attr]
        assert statuses == ["completed", "skipped"], (
            f"期望一个 completed 一个 skipped，实际: {[r.status for r in results]}"  # type: ignore[union-attr]
        )

        # 被锁阻止的那个应有对应错误信息
        skipped = [r for r in results if r.status == "skipped"]  # type: ignore[union-attr]
        assert len(skipped) == 1
        assert "already running" in (skipped[0].error_message or "")  # type: ignore[union-attr]

        # 数据库中只有一条 COMPLETED 的 pipeline job_run
        async with factory() as verify_session:
            rows = (
                (
                    await verify_session.execute(
                        select(JobRun).where(
                            JobRun.job_type == JobType.PIPELINE,
                            JobRun.status == JobStatus.COMPLETED,
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert len(rows) == 1, f"期望 1 条 COMPLETED job_run，实际 {len(rows)}"

    async def test_sequential_pipeline_both_can_run(self, db_engine) -> None:
        """串行执行两次 pipeline：第一次 completed 后第二次也能成功。

        验证锁不会永久阻止后续执行（因为第一次结束后状态变为 COMPLETED）。
        """
        from app.services.pipeline_service import run_pipeline

        factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

        async with factory() as setup_session:
            await seed_config_keys(setup_session, push_days="1,2,3,4,5,6,7")
            await setup_session.commit()

        mock_fetch = AsyncMock(
            return_value=FetchResult(new_tweets_count=5, fail_count=0, total_accounts=3)
        )
        mock_process = AsyncMock(
            return_value=ProcessResult(processed_count=3, filtered_count=1, topic_count=2)
        )
        mock_digest = AsyncMock(return_value=AsyncMock(id=1))
        mock_alert = AsyncMock()
        mock_claude = AsyncMock(return_value=AsyncMock())

        results = []
        for _ in range(2):
            async with factory() as session:
                with (
                    patch(
                        f"{_MODULE}.FetchService",
                        _make_service_class(mock_fetch, "run_daily_fetch"),
                    ),
                    patch(
                        f"{_MODULE}.ProcessService",
                        _make_service_class(mock_process, "run_daily_process"),
                    ),
                    patch(
                        f"{_MODULE}.DigestService",
                        _make_service_class(mock_digest, "generate_daily_digest"),
                    ),
                    patch(f"{_MODULE}.send_alert", mock_alert),
                    patch("app.clients.claude_client.get_claude_client", mock_claude),
                ):
                    result = await run_pipeline(session, trigger_source=TriggerSource.CRON)
                    await session.commit()
                    results.append(result)

        assert results[0].status == "completed"
        assert results[1].status == "completed"
