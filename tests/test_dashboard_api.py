"""Dashboard API 测试 — US-040/US-043/US-044。"""

import json
import tempfile
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
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


# ══════════════════════════════════════════
# US-043: API 成本监控
# ══════════════════════════════════════════


@pytest.mark.asyncio
async def test_api_costs_requires_auth(client: AsyncClient) -> None:
    """未认证 → 401。"""
    resp = await client.get("/api/dashboard/api-costs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_costs_daily_requires_auth(client: AsyncClient) -> None:
    """未认证 → 401。"""
    resp = await client.get("/api/dashboard/api-costs/daily")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_costs_empty(authed_client: AsyncClient) -> None:
    """无数据时返回 0。"""
    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/api-costs")
    assert resp.status_code == 200

    data = resp.json()
    assert data["today"]["total_cost"] == 0
    assert data["today"]["by_service"] == []
    assert data["this_month"]["total_cost"] == 0
    assert data["this_month"]["by_service"] == []


@pytest.mark.asyncio
async def test_api_costs_with_data(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """今日 + 本月各有数据，正确聚合。"""
    # 今日成本
    db.add(
        ApiCostLog(
            call_date=TODAY,
            service="claude",
            call_type="global_analysis",
            input_tokens=50000,
            output_tokens=2000,
            estimated_cost=0.18,
            duration_ms=3000,
        )
    )
    # 本月早些时候
    db.add(
        ApiCostLog(
            call_date=date(2026, 3, 5),
            service="claude",
            call_type="single_process",
            input_tokens=10000,
            output_tokens=500,
            estimated_cost=0.04,
            duration_ms=1500,
        )
    )
    # 上个月 — 不计入本月
    db.add(
        ApiCostLog(
            call_date=date(2026, 2, 28),
            service="claude",
            call_type="global_analysis",
            input_tokens=50000,
            output_tokens=2000,
            estimated_cost=0.18,
            duration_ms=3000,
        )
    )
    await db.commit()

    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/api-costs")
    assert resp.status_code == 200

    data = resp.json()
    # 今日只有一条 0.18
    assert data["today"]["total_cost"] == pytest.approx(0.18, abs=0.01)
    assert len(data["today"]["by_service"]) == 1

    # 本月包含今日 + 3月5日 = 0.18 + 0.04 = 0.22
    assert data["this_month"]["total_cost"] == pytest.approx(0.22, abs=0.01)


@pytest.mark.asyncio
async def test_api_costs_daily_empty(authed_client: AsyncClient) -> None:
    """无数据返回空 days。"""
    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/api-costs/daily")
    assert resp.status_code == 200
    assert resp.json()["days"] == []


@pytest.mark.asyncio
async def test_api_costs_daily_with_data(
    authed_client: AsyncClient,
    db: AsyncSession,
) -> None:
    """多天多 service 正确聚合。"""
    for day_offset in range(3):
        d = TODAY - timedelta(days=day_offset)
        db.add(
            ApiCostLog(
                call_date=d,
                service="claude",
                call_type="global_analysis",
                input_tokens=50000,
                output_tokens=2000,
                estimated_cost=0.18,
                duration_ms=3000,
            )
        )
        db.add(
            ApiCostLog(
                call_date=d,
                service="x",
                call_type="fetch_tweets",
                input_tokens=0,
                output_tokens=0,
                estimated_cost=0.01,
                duration_ms=800,
            )
        )
    await db.commit()

    with patch("app.api.dashboard.get_today_digest_date", return_value=TODAY):
        resp = await authed_client.get("/api/dashboard/api-costs/daily")
    assert resp.status_code == 200

    days = resp.json()["days"]
    assert len(days) == 3

    # 按日期降序
    dates = [d["date"] for d in days]
    assert dates == sorted(dates, reverse=True)

    # 每天 claude=0.18, x=0.01, total=0.19
    for day in days:
        assert day["claude_cost"] == pytest.approx(0.18, abs=0.01)
        assert day["x_cost"] == pytest.approx(0.01, abs=0.01)
        assert day["total_cost"] == pytest.approx(0.19, abs=0.01)
        assert day["gemini_cost"] == 0.0


# ══════════════════════════════════════════
# US-044: Dashboard 日志展示
# ══════════════════════════════════════════


@pytest.mark.asyncio
async def test_logs_requires_auth(client: AsyncClient) -> None:
    """未认证 → 401。"""
    resp = await client.get("/api/dashboard/logs")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_logs_empty(authed_client: AsyncClient) -> None:
    """日志文件不存在时返回空列表。"""
    with patch("app.api.dashboard.LOG_FILE_PATH", Path("/nonexistent/app.log")):
        resp = await authed_client.get("/api/dashboard/logs")
    assert resp.status_code == 200
    assert resp.json()["logs"] == []


@pytest.mark.asyncio
async def test_logs_default(authed_client: AsyncClient) -> None:
    """默认返回 INFO 及以上级别的日志。"""
    lines = []
    for i in range(5):
        lines.append(
            json.dumps(
                {
                    "timestamp": f"2026-03-20T10:00:{i:02d}Z",
                    "level": "INFO",
                    "message": f"测试消息 {i}",
                    "module": "test",
                    "request_id": None,
                }
            )
        )
    lines.append(
        json.dumps(
            {
                "timestamp": "2026-03-20T10:00:05Z",
                "level": "DEBUG",
                "message": "调试消息",
                "module": "test",
                "request_id": None,
            }
        )
    )

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        tmp_path = Path(f.name)

    try:
        with patch("app.api.dashboard.LOG_FILE_PATH", tmp_path):
            resp = await authed_client.get("/api/dashboard/logs")
        assert resp.status_code == 200

        logs = resp.json()["logs"]
        # 默认 INFO 级别，不包含 DEBUG
        assert len(logs) == 5
        assert all(log["level"] != "DEBUG" for log in logs)
        # 最新的在前（倒序）
        assert logs[0]["message"] == "测试消息 4"
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_logs_filter_error(authed_client: AsyncClient) -> None:
    """level=ERROR 只返回 ERROR 及以上。"""
    lines = [
        json.dumps(
            {
                "timestamp": "2026-03-20T10:00:00Z",
                "level": "INFO",
                "message": "信息",
                "module": "test",
                "request_id": None,
            }
        ),
        json.dumps(
            {
                "timestamp": "2026-03-20T10:00:01Z",
                "level": "WARNING",
                "message": "警告",
                "module": "test",
                "request_id": None,
            }
        ),
        json.dumps(
            {
                "timestamp": "2026-03-20T10:00:02Z",
                "level": "ERROR",
                "message": "错误",
                "module": "test",
                "request_id": None,
            }
        ),
        json.dumps(
            {
                "timestamp": "2026-03-20T10:00:03Z",
                "level": "CRITICAL",
                "message": "致命",
                "module": "test",
                "request_id": None,
            }
        ),
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        tmp_path = Path(f.name)

    try:
        with patch("app.api.dashboard.LOG_FILE_PATH", tmp_path):
            resp = await authed_client.get("/api/dashboard/logs?level=ERROR")
        assert resp.status_code == 200

        logs = resp.json()["logs"]
        assert len(logs) == 2
        levels = {log["level"] for log in logs}
        assert levels == {"ERROR", "CRITICAL"}
    finally:
        tmp_path.unlink()


@pytest.mark.asyncio
async def test_logs_limit(authed_client: AsyncClient) -> None:
    """limit 参数限制返回条数。"""
    lines = [
        json.dumps(
            {
                "timestamp": f"2026-03-20T10:00:{i:02d}Z",
                "level": "INFO",
                "message": f"消息 {i}",
                "module": "test",
                "request_id": None,
            }
        )
        for i in range(20)
    ]

    with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
        f.write("\n".join(lines) + "\n")
        tmp_path = Path(f.name)

    try:
        with patch("app.api.dashboard.LOG_FILE_PATH", tmp_path):
            resp = await authed_client.get("/api/dashboard/logs?limit=5")
        assert resp.status_code == 200

        logs = resp.json()["logs"]
        assert len(logs) == 5
        # 最新在前
        assert logs[0]["message"] == "消息 19"
    finally:
        tmp_path.unlink()
