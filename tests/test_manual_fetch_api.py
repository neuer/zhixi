"""手动触发抓取 API 测试（US-027b）。"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun
from app.schemas.fetcher_types import FetchResult

# ── fixtures ──────────────────────────────────────────────


@pytest.fixture
def mock_fetch_service() -> AsyncMock:
    """Mock FetchService.run_daily_fetch。"""
    return AsyncMock(
        return_value=FetchResult(
            new_tweets_count=5,
            fail_count=0,
            total_accounts=3,
        )
    )


# ── 测试用例 ──────────────────────────────────────────────


@freeze_time("2026-03-20 08:00:00+08:00")
class TestManualFetchSuccess:
    """正常抓取。"""

    async def test_fetch_returns_200(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
        mock_fetch_service: AsyncMock,
    ) -> None:
        """成功抓取返回 200 + job_run_id + new_tweets。"""
        from app.models.config import SystemConfig

        db.add(SystemConfig(key="push_days", value="1,2,3,4,5,6,7"))
        await db.flush()

        with patch(
            "app.api.manual.FetchService",
            return_value=AsyncMock(run_daily_fetch=mock_fetch_service),
        ):
            resp = await authed_client.post("/api/manual/fetch")

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "抓取完成"
        assert data["new_tweets"] == 5
        assert "job_run_id" in data

        # 验证 job_run 记录
        job_run = (
            await db.execute(select(JobRun).where(JobRun.id == data["job_run_id"]))
        ).scalar_one()
        assert job_run.status == "completed"
        assert job_run.job_type == "fetch"
        assert job_run.trigger_source == "manual"


@freeze_time("2026-03-20 08:00:00+08:00")
class TestManualFetchFailure:
    """抓取失败。"""

    async def test_fetch_returns_500_on_error(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """FetchService 抛异常 → 500 + job_run failed。"""
        mock = AsyncMock(side_effect=RuntimeError("X API connection refused"))
        with patch(
            "app.api.manual.FetchService",
            return_value=AsyncMock(run_daily_fetch=mock),
        ):
            resp = await authed_client.post("/api/manual/fetch")

        assert resp.status_code == 500
        assert "抓取失败" in resp.json()["detail"]

        # job_run 应标记为 failed
        job_runs = (
            (await db.execute(select(JobRun).where(JobRun.status == "failed"))).scalars().all()
        )
        assert len(job_runs) == 1
        assert "X API connection refused" in (job_runs[0].error_message or "")


@freeze_time("2026-03-20 08:00:00+08:00")
class TestManualFetchPipelineLock:
    """pipeline running 时拒绝抓取。"""

    async def test_409_when_pipeline_running(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """同日有 running pipeline → 409。"""
        db.add(
            JobRun(
                job_type="pipeline",
                digest_date=date(2026, 3, 20),
                trigger_source="cron",
                status="running",
                started_at=datetime.now(UTC),
            )
        )
        await db.flush()

        resp = await authed_client.post("/api/manual/fetch")

        assert resp.status_code == 409
        assert "任务在运行中" in resp.json()["detail"]


@freeze_time("2026-03-20 08:00:00+08:00")
class TestManualFetchDuplicateLock:
    """同日 fetch running 时拒绝。"""

    async def test_409_when_fetch_running(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """同日有 running fetch → 409。"""
        db.add(
            JobRun(
                job_type="fetch",
                digest_date=date(2026, 3, 20),
                trigger_source="manual",
                status="running",
                started_at=datetime.now(UTC),
            )
        )
        await db.flush()

        with patch(
            "app.api.manual.FetchService",
            return_value=AsyncMock(run_daily_fetch=AsyncMock()),
        ):
            resp = await authed_client.post("/api/manual/fetch")

        assert resp.status_code == 409


class TestManualFetchNoAuth:
    """未登录拒绝。"""

    async def test_401_without_token(
        self,
        client: AsyncClient,
    ) -> None:
        """无 JWT → 401。"""
        resp = await client.post("/api/manual/fetch")
        assert resp.status_code == 401
