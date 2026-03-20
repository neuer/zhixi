# US-027 + US-027b 实施计划：Pipeline 主流程编排 + 手动触发抓取

## Context

P3 阶段 US-028（幂等锁）和 US-029（Webhook 通知）已完成。US-027 是关键路径节点，解锁 US-035（重新生成草稿）和 US-051（状态流转测试）。当前 `app/cli.py` 中 `_run_pipeline()` 是 TODO 占位；`app/api/manual.py` 是空路由。

## 关键设计决策

### 1. pipeline_service 采用模块级函数（非 class）
与 lock_service 模式一致：`run_pipeline(db, trigger_source)` 内部创建 FetchService/ProcessService/DigestService。原因：pipeline 是跨 service 编排，不属于任何单一模块。

### 2. Pipeline 失败不抛异常，返回 PipelineResult
`run_pipeline()` 内部 catch 所有业务异常，更新 job_run 为 failed，发送 webhook，返回 result。调用方（CLI）根据 result.status 决定退出码。这样 CLI 的 `db.commit()` 总是执行，保证 job_run 持久化（无论成功失败）。

### 3. 手动抓取 API 用 JSONResponse 替代 HTTPException 处理失败
`get_db()` 在异常时 rollback。若抓取失败后 raise HTTPException，job_run 的 failed 状态会被回滚。改用 `return JSONResponse(status_code=500, ...)` 确保正常 commit。

### 4. push_days 检查
`system_config.push_days` 存为 "1,2,3,4,5,6,7"（1=周一）。Python `date.isoweekday()` 返回 1-7（周一-周日），直接匹配。

## 文件变更清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/services/pipeline_service.py` | Pipeline 主流程编排 |
| `app/schemas/pipeline_types.py` | PipelineResult 类型 |
| `tests/test_pipeline_service.py` | Pipeline 单元测试 |
| `tests/test_manual_fetch_api.py` | 手动抓取 API 测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `app/cli.py` | 实现 `_run_pipeline()` |
| `app/api/manual.py` | 添加 `POST /fetch` 路由 |

## 详细实现

### 1. `app/schemas/pipeline_types.py`（新增）

```python
class PipelineResult(BaseModel):
    status: str  # "completed" | "failed" | "skipped"
    digest_date: date
    job_run_id: int | None = None
    error_message: str | None = None
    failed_step: str | None = None  # "fetch" | "process" | "digest"
    fetch_result: FetchResult | None = None
    process_result: ProcessResult | None = None
```

### 2. `app/services/pipeline_service.py`（新增）

核心函数：`async def run_pipeline(db, trigger_source="cron") -> PipelineResult`

流程：
1. `digest_date = get_today_digest_date()`
2. 读取 `push_days`，检查今日是否推送日
   - 否 → 创建 job_run(status=skipped)，返回 skipped
3. `clean_stale_jobs(db, digest_date)` 清理超时任务
4. `has_running_job(db, "pipeline", digest_date)` 检查锁
   - 是 → 返回 skipped(reason="pipeline already running")，不创建 job_run
5. 创建 job_run(pipeline, running, trigger_source)，`flush()` 获取 ID
6. try:
   - `FetchService(db).run_daily_fetch(digest_date)`
   - `ProcessService(db, claude_client).run_daily_process(digest_date)`
   - `DigestService(db, claude_client).generate_daily_digest(digest_date)`
   - 更新 job_run → completed
7. except Exception:
   - 更新 job_run → failed + error_message
   - `send_alert("Pipeline 失败", 错误详情, db)`（try-except 包裹，失败仅日志）
   - 返回 PipelineResult(status="failed", ...)

**关键复用**：
- `app/services/lock_service.py:clean_stale_jobs()` — 清理超时任务
- `app/services/lock_service.py:has_running_job()` — 基本锁检查
- `app/clients/notifier.py:send_alert()` — Webhook 通知
- `app/clients/claude_client.py:get_claude_client()` — Claude 客户端单例
- `app/config.py:get_today_digest_date()` — 北京时间今日日期
- `app/config.py:get_system_config()` — 读取 push_days

### 3. `app/cli.py`（修改 `_run_pipeline`）

```python
async def _run_pipeline() -> None:
    from app.database import async_session_factory
    from app.services.pipeline_service import run_pipeline

    async with async_session_factory() as db:
        try:
            result = await run_pipeline(db, trigger_source="cron")
            await db.commit()

            if result.status == "skipped":
                typer.echo(f"Pipeline skipped: {result.error_message or 'not a push day'}")
            elif result.status == "completed":
                typer.echo("Pipeline completed successfully")
            elif result.status == "failed":
                typer.echo(f"Pipeline failed at [{result.failed_step}]: {result.error_message}", err=True)
                raise typer.Exit(code=1)
        except typer.Exit:
            raise
        except Exception:
            await db.rollback()
            raise
```

### 4. `app/api/manual.py`（修改，添加 POST /fetch）

```python
@router.post("/fetch")
async def manual_fetch(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
    _lock: None = Depends(require_no_pipeline_lock),  # 增强锁
):
    digest_date = get_today_digest_date()

    # 基本锁：同日 fetch 已 running → 409
    if await has_running_job(db, "fetch", digest_date):
        raise HTTPException(409, "当前有任务在运行中，请稍后再试")

    # 创建 job_run
    job_run = JobRun(job_type="fetch", digest_date=digest_date,
                     trigger_source="manual", status="running")
    db.add(job_run)
    await db.flush()

    try:
        fetch_svc = FetchService(db)
        result = await fetch_svc.run_daily_fetch(digest_date)
        job_run.status = "completed"
        job_run.finished_at = datetime.now(UTC)
        return {"message": "抓取完成", "job_run_id": job_run.id, "new_tweets": result.new_tweets_count}
    except Exception as e:
        job_run.status = "failed"
        job_run.error_message = str(e)[:500]
        job_run.finished_at = datetime.now(UTC)
        # 用 JSONResponse 而非 HTTPException，保证 get_db() 正常 commit
        return JSONResponse(status_code=500, content={"detail": f"抓取失败: {str(e)[:200]}"})
```

## 测试策略

### `tests/test_pipeline_service.py`

Mock 策略：
- `FetchService.run_daily_fetch` → AsyncMock(return_value=FetchResult(...))
- `ProcessService.run_daily_process` → AsyncMock(return_value=ProcessResult(...))
- `DigestService.generate_daily_digest` → AsyncMock(return_value=DailyDigest mock)
- `send_alert` → AsyncMock
- `freezegun.freeze_time` 固定北京时间

测试用例（TDD 红灯→绿灯）：

| # | 用例 | 断言 |
|---|------|------|
| 1 | 全流程成功 | status=completed, job_run 记录正确, 三个 service 都被调用 |
| 2 | 非推送日 | status=skipped, job_run.status=skipped, service 均未调用 |
| 3 | fetch 步骤失败 | status=failed, failed_step="fetch", webhook 被调用 |
| 4 | process 步骤失败 | status=failed, failed_step="process", fetch 已调用 |
| 5 | digest 步骤失败 | status=failed, failed_step="digest" |
| 6 | 已有 running pipeline | 返回 skipped, 不创建新 job_run |
| 7 | 清理超时 running 后正常执行 | stale job 被清理, 新 pipeline 正常运行 |
| 8 | webhook 发送失败不影响结果 | status=failed, 无异常抛出 |

### `tests/test_manual_fetch_api.py`

使用 httpx AsyncClient + dependency_overrides。

| # | 用例 | 断言 |
|---|------|------|
| 1 | 正常抓取 | 200, message="抓取完成", job_run_id/new_tweets 存在 |
| 2 | 抓取失败 | 500, detail 含错误信息, job_run.status=failed |
| 3 | pipeline running 时抓取 | 409 (require_no_pipeline_lock) |
| 4 | 同日 fetch running | 409 (has_running_job) |
| 5 | 未登录 | 401 |

## 验证步骤

```bash
# 1. 运行本轮新增测试
uv run pytest tests/test_pipeline_service.py tests/test_manual_fetch_api.py -v

# 2. 全量测试
uv run pytest

# 3. 质量门禁
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
```

## 执行结果

### 交付物清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/schemas/pipeline_types.py` | 新增 | PipelineResult 类型定义 |
| `app/services/pipeline_service.py` | 新增 | Pipeline 主流程编排（模块级函数） |
| `app/cli.py` | 修改 | 实现 `_run_pipeline()` 调用 pipeline_service |
| `app/api/manual.py` | 修改 | 添加 `POST /api/manual/fetch` 路由 |
| `tests/test_pipeline_service.py` | 新增 | 8 个 pipeline 测试用例 |
| `tests/test_manual_fetch_api.py` | 新增 | 5 个手动抓取 API 测试用例 |
| `docs/spec/user-stories.md` | 修改 | US-027/027b 状态 → ✅ |
| `docs/plans/us-027-027b-pipeline-manual-fetch.md` | 新增+回填 | 实施计划 + 执行结果 |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | 使用 `patch.multiple` mock | 改用 `ExitStack` + 独立 `patch` | pyright 无法推断 `patch.multiple(**dict)` 的类型参数 |
| 2 | `freeze_time` 用 `tz_offset=8` | 改用 `+08:00` 时区字符串 | 项目已有 freeze_time 用法均使用显式时区字符串，`tz_offset` 导致 `get_today_digest_date()` 返回错误日期 |
| 3 | 路由返回 `dict \| JSONResponse` | 添加 `response_model=None` | FastAPI 不支持 `Union[dict, Response]` 返回类型推断 |

### 问题与修复

| 问题 | 解决 |
|------|------|
| `freeze_time("...", tz_offset=8)` 导致 `get_today_digest_date()` 返回 +1 天 | 改为 `freeze_time("2026-03-20 08:00:00+08:00")` 显式时区 |
| `patch.multiple` 导致 24 个 pyright 错误 | 改用 `ExitStack` + 独立 `patch` 调用 |
| FastAPI 路由 `Union[dict, JSONResponse]` 返回类型解析失败 | 添加 `response_model=None` 装饰器参数 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format --check | ✅ 120 files already formatted |
| lint-imports | ✅ 4 contracts kept, 0 broken |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 373 passed (含新增 13 个) |

### PR 链接

https://github.com/neuer/zhixi/pull/19
