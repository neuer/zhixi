"""重新生成草稿 API 测试（US-035）。"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digest import DailyDigest
from app.models.job_run import JobRun

DIGEST_DATE = date(2026, 3, 20)


async def _seed_draft(
    db: AsyncSession,
    version: int = 1,
    status: str = "draft",
) -> DailyDigest:
    """创建测试 digest。"""
    digest = DailyDigest(
        digest_date=DIGEST_DATE,
        version=version,
        is_current=True,
        status=status,
        summary="摘要",
        item_count=2,
        content_markdown="# 旧版本",
    )
    db.add(digest)
    await db.flush()
    return digest


def _mock_regenerate_digest() -> AsyncMock:
    """Mock DigestService.regenerate_digest → 返回新 digest 对象。"""
    result = AsyncMock()
    result.id = 10
    result.version = 2
    result.item_count = 5
    return result


# ── 测试用例 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestRegenerateSuccess:
    """正常重新生成。"""

    async def test_regenerate_returns_200(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """POST /api/digest/regenerate → 200 + digest 信息。"""
        await _seed_draft(db)
        await db.commit()

        mock_digest = _mock_regenerate_digest()

        with (
            patch(
                "app.api.digest.get_claude_client",
                return_value=AsyncMock(),
            ),
            patch(
                "app.api.digest.DigestService",
                return_value=AsyncMock(regenerate_digest=AsyncMock(return_value=mock_digest)),
            ),
        ):
            resp = await authed_client.post("/api/digest/regenerate")

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "重新生成完成"
        assert data["version"] == 2
        assert data["item_count"] == 5
        assert "job_run_id" in data

        # 验证 job_run
        job_run = (
            await db.execute(select(JobRun).where(JobRun.id == data["job_run_id"]))
        ).scalar_one()
        assert job_run.status == "completed"
        assert job_run.job_type == "pipeline"
        assert job_run.trigger_source == "regenerate"


@freeze_time("2026-03-20 08:00:00+08:00")
class TestRegenerateLock:
    """增强锁。"""

    async def test_regenerate_409_pipeline_running(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """同日有 pipeline running → 409。"""
        # 创建 running pipeline job
        job_run = JobRun(
            job_type="pipeline",
            digest_date=DIGEST_DATE,
            trigger_source="cron",
            status="running",
            started_at=datetime.now(UTC),
        )
        db.add(job_run)
        await db.commit()

        resp = await authed_client.post("/api/digest/regenerate")
        assert resp.status_code == 409
        assert "任务在运行中" in resp.json()["detail"]


@freeze_time("2026-03-20 08:00:00+08:00")
class TestRegenerateFailure:
    """重新生成失败。"""

    async def test_regenerate_500_preserves_job_run(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """失败 → 500 + job_run 持久化为 failed。"""
        await _seed_draft(db)
        await db.commit()

        mock_svc = AsyncMock()
        mock_svc.regenerate_digest = AsyncMock(side_effect=RuntimeError("AI 超时"))

        with (
            patch("app.api.digest.get_claude_client", return_value=AsyncMock()),
            patch("app.api.digest.DigestService", return_value=mock_svc),
            patch("app.api.digest.send_alert", AsyncMock()),
        ):
            resp = await authed_client.post("/api/digest/regenerate")

        assert resp.status_code == 500
        assert "重新生成失败" in resp.json()["detail"]

        # job_run 仍持久化为 failed
        result = await db.execute(select(JobRun).where(JobRun.trigger_source == "regenerate"))
        job_run = result.scalar_one()
        assert job_run.status == "failed"
        assert "AI 超时" in (job_run.error_message or "")


class TestRegenerateAuth:
    """认证检查。"""

    async def test_regenerate_401_no_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """未认证 → 401。"""
        resp = await client.post("/api/digest/regenerate")
        assert resp.status_code == 401
