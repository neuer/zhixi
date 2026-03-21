"""Dashboard 路由 — US-040/US-043/US-044。"""

import json
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, Query
from sqlalchemy import ColumnElement, and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import get_system_config, get_today_digest_date
from app.database import get_db
from app.models.api_cost_log import ApiCostLog
from app.models.digest import DailyDigest
from app.models.job_run import JobRun
from app.schemas.dashboard_types import (
    AlertItem,
    ApiCostsResponse,
    CostSummary,
    DailyCostItem,
    DailyCostsResponse,
    DashboardOverviewResponse,
    DigestDayRecord,
    DigestStatus,
    LogEntry,
    LogsResponse,
    PipelineStatus,
    ServiceCostItem,
)

router = APIRouter()

LOG_FILE_PATH = Path("data/logs/app.log")

LEVEL_SEVERITY = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}


@router.get("/overview", response_model=DashboardOverviewResponse)
async def get_overview(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> DashboardOverviewResponse:
    """Dashboard 概览：pipeline 状态、digest 状态、成本、7 天记录、告警。"""
    today = get_today_digest_date()

    pipeline_status = await _get_pipeline_status(db, today)
    digest_status = await _get_digest_status(db, today)
    today_cost = await _get_today_cost(db, today)
    recent_7_days = await _get_recent_7_days(db, today)
    alerts = await _get_alerts(db, today)

    return DashboardOverviewResponse(
        pipeline_status=pipeline_status,
        digest_status=digest_status,
        today_cost=today_cost,
        recent_7_days=recent_7_days,
        alerts=alerts,
    )


# ── US-043: API 成本监控 ──


@router.get("/api-costs", response_model=ApiCostsResponse)
async def get_api_costs(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> ApiCostsResponse:
    """API 成本汇总：今日 + 本月。"""
    today = get_today_digest_date()
    today_cost = await _get_today_cost(db, today)
    month_cost = await _get_month_cost(db, today)
    return ApiCostsResponse(today=today_cost, this_month=month_cost)


@router.get("/api-costs/daily", response_model=DailyCostsResponse)
async def get_api_costs_daily(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> DailyCostsResponse:
    """最近 30 天按日成本趋势。"""
    today = get_today_digest_date()
    since = today - timedelta(days=30)

    result = await db.execute(
        select(
            ApiCostLog.call_date,
            ApiCostLog.service,
            func.sum(ApiCostLog.estimated_cost).label("cost"),
        )
        .where(and_(ApiCostLog.call_date > since, ApiCostLog.call_date <= today))
        .group_by(ApiCostLog.call_date, ApiCostLog.service)
    )
    rows = result.all()

    by_date: dict[date, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    for row in rows:
        by_date[row.call_date][row.service] = round(float(row.cost or 0), 6)

    days = []
    for d in sorted(by_date.keys(), reverse=True):
        services = by_date[d]
        claude_cost = services.get("claude", 0.0)
        x_cost = services.get("x", 0.0)
        gemini_cost = services.get("gemini", 0.0)
        total = round(sum(services.values()), 6)
        days.append(
            DailyCostItem(
                date=d,
                total_cost=total,
                claude_cost=claude_cost,
                x_cost=x_cost,
                gemini_cost=gemini_cost,
            )
        )

    return DailyCostsResponse(days=days)


# ── US-044: 日志展示 ──


@router.get("/logs", response_model=LogsResponse)
async def get_logs(
    level: str = Query(default="INFO"),
    limit: int = Query(default=100, ge=1, le=500),
    _admin: str = Depends(get_current_admin),
) -> LogsResponse:
    """读取最新日志，按级别过滤。"""
    min_severity = LEVEL_SEVERITY.get(level.upper(), 20)

    if not LOG_FILE_PATH.exists():
        return LogsResponse(logs=[])

    entries: list[LogEntry] = []
    lines = LOG_FILE_PATH.read_text(encoding="utf-8").splitlines()

    # 倒序遍历获取最新日志
    for line in reversed(lines):
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue

        entry_level = obj.get("level", "INFO")
        entry_severity = LEVEL_SEVERITY.get(entry_level, 20)
        if entry_severity < min_severity:
            continue

        entries.append(
            LogEntry(
                timestamp=obj.get("timestamp", ""),
                level=entry_level,
                message=obj.get("message", ""),
                module=obj.get("module", ""),
                request_id=obj.get("request_id"),
                exception=obj.get("exception"),
            )
        )

        if len(entries) >= limit:
            break

    return LogsResponse(logs=entries)


# ── 内部辅助函数 ──


async def _get_pipeline_status(db: AsyncSession, today: date) -> PipelineStatus:
    """获取今日最新 pipeline 状态。"""
    result = await db.execute(
        select(JobRun)
        .where(and_(JobRun.job_type == "pipeline", JobRun.digest_date == today))
        .order_by(desc(JobRun.started_at))
        .limit(1)
    )
    job = result.scalar_one_or_none()
    if not job:
        return PipelineStatus()
    return PipelineStatus(
        status=job.status,
        started_at=job.started_at,
        error_message=job.error_message,
    )


async def _get_digest_status(db: AsyncSession, today: date) -> DigestStatus:
    """获取今日 current digest 状态。"""
    result = await db.execute(
        select(DailyDigest)
        .where(and_(DailyDigest.digest_date == today, DailyDigest.is_current.is_(True)))
        .limit(1)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        return DigestStatus()
    min_articles = int(await get_system_config(db, "min_articles", "1"))
    return DigestStatus(
        status=digest.status,
        digest_id=digest.id,
        item_count=digest.item_count,
        version=digest.version,
        low_content_warning=digest.item_count < min_articles,
    )


async def _get_today_cost(db: AsyncSession, today: date) -> CostSummary:
    """聚合今日 API 成本。"""
    return await _aggregate_cost(db, ApiCostLog.call_date == today)


async def _get_month_cost(db: AsyncSession, today: date) -> CostSummary:
    """聚合本月 API 成本。"""
    month_start = today.replace(day=1)
    return await _aggregate_cost(
        db,
        and_(ApiCostLog.call_date >= month_start, ApiCostLog.call_date <= today),
    )


async def _aggregate_cost(db: AsyncSession, where_clause: ColumnElement[bool]) -> CostSummary:
    """按 service 聚合成本的通用函数。"""
    result = await db.execute(
        select(
            ApiCostLog.service,
            func.count().label("call_count"),
            func.sum(ApiCostLog.input_tokens + ApiCostLog.output_tokens).label("total_tokens"),
            func.sum(ApiCostLog.estimated_cost).label("estimated_cost"),
        )
        .where(where_clause)
        .group_by(ApiCostLog.service)
    )
    rows = result.all()

    by_service = [
        ServiceCostItem(
            service=row.service,
            call_count=row.call_count,
            total_tokens=int(row.total_tokens or 0),
            estimated_cost=round(float(row.estimated_cost or 0), 6),
        )
        for row in rows
    ]
    total_cost = round(sum(s.estimated_cost for s in by_service), 6)

    return CostSummary(total_cost=total_cost, by_service=by_service)


async def _get_recent_7_days(db: AsyncSession, today: date) -> list[DigestDayRecord]:
    """获取近 7 天推送记录（每天选一条代表版本）。

    优先级: published > is_current > max version。
    """
    since = today - timedelta(days=7)

    result = await db.execute(
        select(DailyDigest)
        .where(and_(DailyDigest.digest_date > since, DailyDigest.digest_date < today))
        .order_by(DailyDigest.digest_date, desc(DailyDigest.version))
    )
    all_digests = result.scalars().all()

    # 按日期分组，每天选最优
    by_date: dict[date, DailyDigest] = {}
    for d in all_digests:
        existing = by_date.get(d.digest_date)
        if existing is None:
            by_date[d.digest_date] = d
        else:
            # published 优先
            if d.status == "published" and existing.status != "published":
                by_date[d.digest_date] = d
            elif d.status != "published" and existing.status == "published":
                pass  # 保留 existing
            elif d.is_current and not existing.is_current:
                by_date[d.digest_date] = d
            elif not d.is_current and existing.is_current:
                pass  # 保留 existing
            elif d.version > existing.version:
                by_date[d.digest_date] = d

    records = [
        DigestDayRecord(
            date=d.digest_date,
            status=d.status,
            item_count=d.item_count,
            version=d.version,
        )
        for d in by_date.values()
    ]
    records.sort(key=lambda r: r.date, reverse=True)
    return records


async def _get_alerts(db: AsyncSession, today: date) -> list[AlertItem]:
    """近 7 天 failed 的 pipeline/fetch job_runs。"""
    since = today - timedelta(days=7)

    result = await db.execute(
        select(JobRun)
        .where(
            and_(
                JobRun.status == "failed",
                JobRun.job_type.in_(["pipeline", "fetch"]),
                JobRun.started_at >= since,
            )
        )
        .order_by(desc(JobRun.started_at))
    )
    jobs = result.scalars().all()

    return [
        AlertItem(
            job_type=j.job_type,
            status=j.status,
            error_message=j.error_message,
            started_at=j.started_at,
        )
        for j in jobs
    ]
