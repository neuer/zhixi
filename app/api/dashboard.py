"""Dashboard 路由 — US-040。"""

from datetime import timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import get_today_digest_date
from app.database import get_db
from app.models.api_cost_log import ApiCostLog
from app.models.digest import DailyDigest
from app.models.job_run import JobRun
from app.schemas.dashboard_types import (
    AlertItem,
    CostSummary,
    DashboardOverviewResponse,
    DigestDayRecord,
    DigestStatus,
    PipelineStatus,
    ServiceCostItem,
)

router = APIRouter()


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


async def _get_pipeline_status(db: AsyncSession, today: object) -> PipelineStatus:
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


async def _get_digest_status(db: AsyncSession, today: object) -> DigestStatus:
    """获取今日 current digest 状态。"""
    result = await db.execute(
        select(DailyDigest)
        .where(and_(DailyDigest.digest_date == today, DailyDigest.is_current.is_(True)))
        .limit(1)
    )
    digest = result.scalar_one_or_none()
    if not digest:
        return DigestStatus()
    return DigestStatus(
        status=digest.status,
        digest_id=digest.id,
        item_count=digest.item_count,
        version=digest.version,
    )


async def _get_today_cost(db: AsyncSession, today: object) -> CostSummary:
    """聚合今日 API 成本。"""
    result = await db.execute(
        select(
            ApiCostLog.service,
            func.count().label("call_count"),
            func.sum(ApiCostLog.input_tokens + ApiCostLog.output_tokens).label("total_tokens"),
            func.sum(ApiCostLog.estimated_cost).label("estimated_cost"),
        )
        .where(ApiCostLog.call_date == today)
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


async def _get_recent_7_days(db: AsyncSession, today: object) -> list[DigestDayRecord]:
    """获取近 7 天推送记录（每天选一条代表版本）。

    优先级: published > is_current > max version。
    """
    from datetime import date as date_type

    assert isinstance(today, date_type)
    since = today - timedelta(days=7)

    result = await db.execute(
        select(DailyDigest)
        .where(and_(DailyDigest.digest_date > since, DailyDigest.digest_date < today))
        .order_by(DailyDigest.digest_date, desc(DailyDigest.version))
    )
    all_digests = result.scalars().all()

    # 按日期分组，每天选最优
    by_date: dict[object, DailyDigest] = {}
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


async def _get_alerts(db: AsyncSession, today: object) -> list[AlertItem]:
    """近 7 天 failed 的 pipeline/fetch job_runs。"""
    from datetime import date as date_type

    assert isinstance(today, date_type)
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
