# US-028 + US-029 实施计划：任务幂等锁 + 通知服务 Webhook

## Context

P2 全部必须 US 已完成，进入 P3。US-028（任务幂等锁）和 US-029（通知服务 Webhook）是 US-027（Pipeline 主流程编排）的直接前置依赖，互不依赖可并行实现。

**目标**：
- US-028：防止同日同类型任务重复执行，提供 CLI 解锁和自动过期清理
- US-029：Pipeline 失败时发送企业微信 Webhook 告警

## 文件清单

### 新建文件

| 文件 | 用途 |
|------|------|
| `app/services/lock_service.py` | 锁服务：基本锁、增强锁查询、过期清理、批量解锁 |
| `tests/test_lock_service.py` | 锁服务单元测试 + 增强锁依赖测试 |
| `tests/test_notifier.py` | 通知服务测试 |
| `tests/test_unlock_cli.py` | CLI unlock 命令集成测试 |

### 修改文件

| 文件 | 修改内容 |
|------|---------|
| `app/clients/notifier.py` | 填充 `send_alert()` 实现（现为空壳） |
| `app/api/deps.py` | 新增 `require_no_pipeline_lock` 依赖函数 |
| `app/cli.py:77-79` | 实现 `_run_unlock()` 函数体 |

## 实现设计

### 1. `app/services/lock_service.py` — 纯异步函数模块

设计决策：用纯函数而非类，因为锁检查是无状态 DB 查询，不需要构造函数注入。

```python
async def has_running_job(db: AsyncSession, job_type: str, digest_date: date) -> bool:
    """基本锁：同日+同job_type有running → True"""

async def has_running_pipeline(db: AsyncSession, digest_date: date) -> bool:
    """增强锁：同日有pipeline running → True（委托 has_running_job）"""

async def clean_stale_jobs(db: AsyncSession, digest_date: date) -> int:
    """自动清理：started_at > 2h 前的 running → failed，返回清理数"""

async def unlock_all_running(db: AsyncSession, digest_date: date) -> int:
    """批量解锁：当日所有 running → failed + 'manually unlocked'，返回解锁数"""
```

- `has_running_job`: `select(JobRun).where(job_type==?, digest_date==?, status=='running').limit(1)`
- `clean_stale_jobs`: 批量 `update()` + `started_at < now - 2h` 条件
- `unlock_all_running`: 批量 `update()` + `error_message='manually unlocked'`

### 2. `app/clients/notifier.py` — 企业微信 Webhook

```python
async def send_alert(title: str, message: str, db: AsyncSession) -> None:
    """发送告警。URL 为空跳过，失败仅记录日志不抛异常。"""
```

- 从 `get_system_config(db, "notification_webhook_url")` 读取 URL
- 消息格式：`{"msgtype":"text","text":{"content":"【智曦告警】{title}\n时间: {now}\n{message}"}}`
- 使用临时 `httpx.AsyncClient(timeout=10.0)` — 与 x_client.py 模式一致
- 全部异常捕获 + `logger.warning()`，绝不向上抛出

### 3. `app/api/deps.py` — 增强锁依赖

```python
async def require_no_pipeline_lock(db: AsyncSession = Depends(get_db)) -> None:
    """当日有 pipeline running → HTTPException(409, '当前有任务在运行中，请稍后再试')"""
```

未来 US-027b/035/036 路由直接 `Depends(require_no_pipeline_lock)` 即可。当前无需修改路由。

### 4. `app/cli.py` — unlock 实现

模式与 `_run_backup()` 一致：`async_session_factory() → try/commit/except rollback`。
调用 `lock_service.unlock_all_running(db, get_today_digest_date())`。

## 模块隔离验证

- `lock_service` 在 `app/services/`（编排层），仅 import `app.models.job_run` ✅
- `notifier` 在 `app/clients/`（基础设施层），仅 import `app.config` + `httpx` ✅
- import-linter 合约仅约束 feature 模块（fetcher/processor/digest/publisher），不涉及 services/clients ✅

## TDD 实施顺序

### Phase 1: 锁服务核心（US-028）

1. **红灯** — 写 `tests/test_lock_service.py`：基本锁 4 个测试
2. **绿灯** — 实现 `lock_service.py`：`has_running_job` + `has_running_pipeline`
3. **红灯** — 追加过期清理 3 个测试（freezegun 固定时间）
4. **绿灯** — 实现 `clean_stale_jobs`
5. **红灯** — 追加 unlock 4 个测试
6. **绿灯** — 实现 `unlock_all_running`

### Phase 2: 增强锁依赖 + CLI（US-028）

7. **红灯** — 追加增强锁依赖测试 2 个
8. **绿灯** — 实现 `deps.py` 中 `require_no_pipeline_lock`
9. **红灯** — 写 `tests/test_unlock_cli.py` 2 个测试
10. **绿灯** — 实现 `cli.py` 中 `_run_unlock()`

### Phase 3: 通知服务（US-029）

11. **红灯** — 写 `tests/test_notifier.py` 7 个测试（respx mock）
12. **绿灯** — 实现 `notifier.py` 中 `send_alert`

### Phase 4: 质量门禁

```bash
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
uv run pytest
```

## 测试计划

### test_lock_service.py（~12 用例）

| 测试 | 验证 |
|------|------|
| `test_has_running_job_true_when_running_exists` | 同日同类型有 running → True |
| `test_has_running_job_false_when_no_running` | 无 running（空/completed/failed）→ False |
| `test_has_running_job_false_different_date` | 不同日期 running 不影响 → False |
| `test_has_running_job_false_different_type` | 不同 job_type running 不影响 → False |
| `test_has_running_pipeline` | 仅检查 job_type="pipeline" |
| `test_clean_stale_jobs_marks_old_as_failed` | >2h 的 running → failed（freezegun） |
| `test_clean_stale_jobs_keeps_recent` | <2h 的 running 保留 |
| `test_clean_stale_jobs_returns_count` | 返回清理数 |
| `test_unlock_all_marks_running_failed` | 全部 running → failed + "manually unlocked" |
| `test_unlock_preserves_non_running` | completed/failed 不受影响 |
| `test_unlock_returns_count` | 返回解锁数 |
| `test_unlock_sets_finished_at` | finished_at 被填充 |
| `test_require_no_pipeline_lock_raises_409` | 有 running pipeline → HTTPException(409) |
| `test_require_no_pipeline_lock_passes` | 无 running pipeline → 正常 |

### test_notifier.py（~7 用例）

| 测试 | 验证 |
|------|------|
| `test_send_alert_posts_to_webhook` | 正确发送 POST 请求 |
| `test_send_alert_payload_format` | msgtype=text + 【智曦告警】前缀 |
| `test_send_alert_skips_empty_url` | URL 空 → 不发送 |
| `test_send_alert_skips_no_config` | 无配置 → 不发送 |
| `test_send_alert_logs_on_http_error` | 500 → 仅记录日志 |
| `test_send_alert_logs_on_timeout` | 超时 → 仅记录日志 |
| `test_send_alert_includes_timestamp` | content 含时间信息 |

### test_unlock_cli.py（~2 用例）

| 测试 | 验证 |
|------|------|
| `test_unlock_marks_running_as_failed` | DB 有 running → 变 failed |
| `test_unlock_no_running_prints_message` | 无 running → 输出提示 |

## 验证方式

1. `uv run pytest tests/test_lock_service.py tests/test_notifier.py tests/test_unlock_cli.py -v` — 新测试全过
2. `uv run pytest` — 全量测试无回归
3. `uv run pyright` — 0 errors
4. `uv run ruff check . && uv run ruff format --check .` — lint 通过
5. `uv run lint-imports` — 模块边界无违规
