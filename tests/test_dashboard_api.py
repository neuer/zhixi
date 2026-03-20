"""Dashboard API 测试 — US-040。"""

from datetime import UTC, date, datetime, timedelta
from unittest.mock import patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.api_cost_log import ApiCostLog
from app.models.config import SystemConfig
from app.models.digest import DailyDigest
from app.models.job_run import JobRun

TODAY = date(2026, 3, 20)


async def _seed_config(db: AsyncSession) -> None:
    """预置 system_config。"""
    db.add_all(
        [
            SystemConfig(key="top_n", value="10"),
            SystemConfig(key="min_articles", value="1"),
        ]
    )
    await db.flush()


# ── 认证 ──


@pytest.mark.asyncio
async def test_overview_requires_auth(client: AsyncClient) -> None:
    """未认证 → 401。"""
    resp = await client.get("/api/dashboard/overview")
    assert resp.status_code == 401


# ── 空数据 ──


@pytest.mark.asyncio
async def test_overview_empty(
    authed_client: AsyncClient,
) -> None:
    """无任何数据时返回空/默认值。"""
    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/overview")
    assert resp.status_code == 200

    data = resp.json()
    # pipeline 状态
    assert data["pipeline_status"]["status"] is None
    # digest 状态
    assert data["digest_status"]["status"] is None
    assert data["digest_status"]["item_count"] == 0
    # 成本
    assert data["today_cost"]["total_cost"] == 0
    assert data["today_cost"]["by_service"] == []
    # 7 天记录
    assert data["recent_7_days"] == []
    # 告警
    assert data["alerts"] == []


# ── 有数据 ──


@pytest.mark.asyncio
async def test_overview_with_data(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """有 job_run + digest + cost_log 时正确聚合。"""
    await _seed_config(db)

    # 今日 pipeline completed
    job = JobRun(
        job_type="pipeline",
        digest_date=TODAY,
        trigger_source="cron",
        status="completed",
        started_at=datetime(2026, 3, 19, 22, 0, 0, tzinfo=UTC),
        finished_at=datetime(2026, 3, 19, 22, 5, 0, tzinfo=UTC),
    )
    db.add(job)

    # 今日 digest
    digest = DailyDigest(
        digest_date=TODAY,
        version=1,
        is_current=True,
        status="draft",
        item_count=8,
        summary="测试摘要",
    )
    db.add(digest)

    # 今日成本记录
    cost1 = ApiCostLog(
        call_date=TODAY,
        service="claude",
        call_type="global_analysis",
        input_tokens=50000,
        output_tokens=2000,
        estimated_cost=0.18,
        duration_ms=3000,
    )
    cost2 = ApiCostLog(
        call_date=TODAY,
        service="claude",
        call_type="single_process",
        input_tokens=10000,
        output_tokens=500,
        estimated_cost=0.04,
        duration_ms=1500,
    )
    cost3 = ApiCostLog(
        call_date=TODAY,
        service="x",
        call_type="fetch_tweets",
        input_tokens=0,
        output_tokens=0,
        estimated_cost=0.0,
        duration_ms=800,
    )
    db.add_all([cost1, cost2, cost3])
    await db.commit()

    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/overview")
    assert resp.status_code == 200

    data = resp.json()

    # pipeline
    assert data["pipeline_status"]["status"] == "completed"

    # digest
    assert data["digest_status"]["status"] == "draft"
    assert data["digest_status"]["item_count"] == 8

    # 成本
    assert data["today_cost"]["total_cost"] == pytest.approx(0.22, abs=0.01)
    services = {s["service"]: s for s in data["today_cost"]["by_service"]}
    assert "claude" in services
    assert services["claude"]["call_count"] == 2
    assert services["claude"]["total_tokens"] == 62500
    assert "x" in services


# ── 告警 ──


@pytest.mark.asyncio
async def test_overview_alerts(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """failed job_runs 出现在 alerts 中。"""
    # 近 7 天内 failed
    job_failed = JobRun(
        job_type="pipeline",
        digest_date=TODAY - timedelta(days=1),
        trigger_source="cron",
        status="failed",
        error_message="Claude API 超时",
        started_at=datetime(2026, 3, 18, 22, 0, 0, tzinfo=UTC),
    )
    # 超过 7 天的不计入
    job_old = JobRun(
        job_type="pipeline",
        digest_date=TODAY - timedelta(days=10),
        trigger_source="cron",
        status="failed",
        error_message="旧错误",
        started_at=datetime(2026, 3, 9, 22, 0, 0, tzinfo=UTC),
    )
    db.add_all([job_failed, job_old])
    await db.commit()

    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/overview")
    assert resp.status_code == 200

    alerts = resp.json()["alerts"]
    assert len(alerts) == 1
    assert alerts[0]["job_type"] == "pipeline"
    assert alerts[0]["error_message"] == "Claude API 超时"


# ── 成本聚合 ──


@pytest.mark.asyncio
async def test_overview_cost_aggregation(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """多条 cost_log 正确 SUM/COUNT。"""
    for i in range(5):
        db.add(
            ApiCostLog(
                call_date=TODAY,
                service="claude",
                call_type=f"call_{i}",
                input_tokens=1000 * (i + 1),
                output_tokens=100 * (i + 1),
                estimated_cost=0.01 * (i + 1),
                duration_ms=500,
            )
        )
    await db.commit()

    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/overview")
    assert resp.status_code == 200

    cost = resp.json()["today_cost"]
    # SUM(0.01 + 0.02 + 0.03 + 0.04 + 0.05) = 0.15
    assert cost["total_cost"] == pytest.approx(0.15, abs=0.01)
    assert cost["by_service"][0]["call_count"] == 5
    # SUM((1000+100)+(2000+200)+...+(5000+500)) = 16500
    assert cost["by_service"][0]["total_tokens"] == 16500


# ── 近 7 天记录 ──


@pytest.mark.asyncio
async def test_overview_7day_records(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """近 7 天 digest 记录正确返回（优先级: published > is_current > max version）。"""
    # 3 天前 published
    db.add(
        DailyDigest(
            digest_date=TODAY - timedelta(days=3),
            version=2,
            is_current=False,
            status="published",
            item_count=10,
        )
    )
    # 3 天前 v1 draft（应被 published 覆盖）
    db.add(
        DailyDigest(
            digest_date=TODAY - timedelta(days=3),
            version=1,
            is_current=False,
            status="draft",
            item_count=8,
        )
    )
    # 1 天前 current draft
    db.add(
        DailyDigest(
            digest_date=TODAY - timedelta(days=1),
            version=1,
            is_current=True,
            status="draft",
            item_count=6,
        )
    )
    # 超过 7 天 — 不应返回
    db.add(
        DailyDigest(
            digest_date=TODAY - timedelta(days=10),
            version=1,
            is_current=True,
            status="published",
            item_count=5,
        )
    )
    await db.commit()

    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/overview")
    assert resp.status_code == 200

    records = resp.json()["recent_7_days"]
    assert len(records) == 2

    # 按日期降序
    dates = [r["date"] for r in records]
    assert dates == sorted(dates, reverse=True)

    # 3 天前应选 published 版本
    day3 = next(r for r in records if r["date"] == str(TODAY - timedelta(days=3)))
    assert day3["status"] == "published"
    assert day3["item_count"] == 10
