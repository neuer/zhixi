# 后端深度审查修复实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复后端深度审查发现的全部 7 Critical + 14 Important + 15 Suggestion = 36 项问题

**Architecture:** 按依赖关系分 5 轮实施。第 1 轮修复阻塞 I/O 和异常链（零依赖），第 2 轮修复 Service 层错误处理，第 3 轮 ORM 枚举化（需 migration），第 4 轮重构消除重复代码，第 5 轮收尾小修。每轮独立可测试、可合并。

**Tech Stack:** FastAPI, SQLAlchemy 2.x async, Pydantic v2, Python 3.12+, anthropic SDK, httpx, bcrypt, Pillow

**分支命名**: `chore/backend-deep-review-fixes`

---

## 第 1 轮 — 阻塞 I/O + 异常链修复（Critical 快修）

> 目标：消除事件循环阻塞和异常链销毁问题。改动最小、收益最高。
> 包含问题：C-1, C-2, C-3, C-4, I-7, I-8

### Task 1: 日志文件异步读取 + 封面图异步写入

**Files:**
- Modify: `app/api/dashboard.py:140-141`
- Modify: `app/digest/cover_generator.py:123`

- [ ] **Step 1: 修改 dashboard.py 日志读取为异步**

```python
# app/api/dashboard.py:140 — 当前:
lines = LOG_FILE_PATH.read_text(encoding="utf-8").splitlines()

# 改为:
import asyncio
text = await asyncio.to_thread(LOG_FILE_PATH.read_text, encoding="utf-8")
lines = text.splitlines()
```

在文件顶部添加 `import asyncio`。

- [ ] **Step 2: 修改 cover_generator.py 文件写入为异步**

```python
# app/digest/cover_generator.py:123 — 当前:
cover_path.write_bytes(resized_bytes)

# 改为:
await asyncio.to_thread(cover_path.write_bytes, resized_bytes)
```

在文件顶部添加 `import asyncio`。

- [ ] **Step 3: 验证**

Run: `ruff check app/api/dashboard.py app/digest/cover_generator.py && pyright app/api/dashboard.py app/digest/cover_generator.py`
Expected: 0 errors

- [ ] **Step 4: 运行相关测试**

Run: `pytest tests/ -q --tb=short`
Expected: 537 passed

### Task 2: Claude/Gemini 客户端异常链修复 + 空响应检查

**Files:**
- Modify: `app/clients/claude_client.py:77-78, 89-91`
- Modify: `app/clients/gemini_client.py:64-67`

- [ ] **Step 1: claude_client.py — `from None` 改 `from e` + 空响应检查**

```python
# 行 77-78 — 当前:
except anthropic.APIError as e:
    raise ClaudeAPIError(str(e)) from None

# 改为:
except anthropic.APIError as e:
    raise ClaudeAPIError(str(e)) from e
```

```python
# 行 89-91 — 当前:
first_block = response.content[0]
content_text = first_block.text if isinstance(first_block, TextBlock) else str(first_block)

# 改为（在行 89 前插入）:
if not response.content:
    raise ClaudeAPIError("Claude API 返回空响应")
first_block = response.content[0]
content_text = first_block.text if isinstance(first_block, TextBlock) else str(first_block)
```

- [ ] **Step 2: gemini_client.py — 缩小 except 范围 + `from e`**

```python
# 行 64-67 — 当前:
except TimeoutError:
    raise GeminiAPIError(f"Gemini API 超时（{timeout}s）") from None
except Exception as e:
    raise GeminiAPIError(str(e)) from None

# 改为:
except TimeoutError:
    raise GeminiAPIError(f"Gemini API 超时（{timeout}s）") from None
except Exception as e:
    logger.error("Gemini API 调用异常", exc_info=True)
    raise GeminiAPIError(str(e)) from e
```

注意：gemini_client.py 已有 `import logging`（行 9）和 `logger`（行 17），无需重复添加。

- [ ] **Step 3: 验证**

Run: `ruff check app/clients/ && pyright app/clients/`
Expected: 0 errors

Run: `pytest tests/ -q --tb=short`
Expected: 537 passed

### Task 3: bcrypt 异步包装

**Files:**
- Modify: `app/auth.py:30-37`

- [ ] **Step 1: 将 bcrypt 操作包裹 asyncio.to_thread**

```python
# 行 30-37 — 当前:
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def verify_password(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

# 改为:
import asyncio

def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def _verify_password_sync(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())

async def hash_password(password: str) -> str:
    """bcrypt 哈希（异步包装，避免阻塞事件循环）。"""
    return await asyncio.to_thread(_hash_password_sync, password)

async def verify_password(password: str, hashed: str) -> bool:
    """bcrypt 验证（异步包装）。"""
    return await asyncio.to_thread(_verify_password_sync, password, hashed)
```

- [ ] **Step 2: 更新所有调用方添加 await**

全部调用方（需添加 `await`）：
- `app/api/auth.py:41` — `verify_password(body.password, password_hash)` → `await verify_password(...)`
- `app/api/setup.py:50` — `hash_password(body.password)` → `await hash_password(...)`

注意：测试文件中如果直接调用这两个函数也需改为 `await`。搜索确认：`grep -rn "hash_password\|verify_password" tests/`

- [ ] **Step 3: 验证**

Run: `ruff check app/auth.py app/api/auth.py app/api/setup.py && pyright app/auth.py app/api/auth.py app/api/setup.py`
Expected: 0 errors

Run: `pytest tests/test_auth.py tests/test_setup_api.py -v`
Expected: 全部 passed

### Task 4: lock_service type: ignore 消除

**Files:**
- Modify: `app/services/lock_service.py:55,58,79,82`

- [ ] **Step 1: 将 `result.rowcount # type: ignore` 改为显式 `int()` 转换**

```python
# 4 处 type: ignore 改为:
count: int = int(result.rowcount)
# 删除 return 处的 type: ignore
return count
```

- [ ] **Step 2: 验证**

Run: `pyright app/services/lock_service.py`
Expected: 0 errors

### 轮次验证

```bash
ruff check . && pyright && pytest tests/ -q --tb=short
```

---

## 第 2 轮 — Service 层错误处理增强

> 目标：修复异常处理不精确、配置解析不安全、重试逻辑缺陷。
> 包含问题：C-5, C-6, I-1, I-2, I-3, I-10, I-12, I-13

### Task 5: pipeline_service 异常处理区分业务/基础设施异常

**Files:**
- Modify: `app/services/pipeline_service.py:109-127`

- [ ] **Step 1: 在 except Exception 前增加 SQLAlchemy 异常分支**

```python
# 行 109 — 当前:
    except Exception as exc:
        failed_step = _determine_failed_step(fetch_result, process_result)
        error_msg = str(exc)[:500]
        job_run.status = "failed"
        ...

# 改为（在 except Exception 前插入一个新 except 分支）:
    except (sqlalchemy.exc.SQLAlchemyError, OSError) as exc:
        # 基础设施异常不可恢复，向上传播
        logger.critical("Pipeline 基础设施异常: %s", exc, exc_info=True)
        raise
    except Exception as exc:
        failed_step = _determine_failed_step(fetch_result, process_result)
        error_msg = str(exc)[:500]
        job_run.status = "failed"
        # ... 保持原有的 error_message/finished_at/logger/send_alert 逻辑不变
```

在文件顶部添加 `import sqlalchemy.exc`。

- [ ] **Step 2: 验证**

Run: `ruff check app/services/pipeline_service.py && pyright app/services/pipeline_service.py && pytest tests/ -q --tb=short`

### Task 6: x_api _request_with_retry 增强（网络异常重试 + rate limit header）

**Files:**
- Modify: `app/fetcher/x_api.py:197-212`

- [ ] **Step 1: 重构重试逻辑，将网络异常纳入**

```python
async def _request_with_retry(
    self,
    url: str,
    params: dict[str, str],
) -> httpx.Response:
    """发送 GET 请求，遇到 429 限流或网络异常时退避重试。"""
    backoff_delays = [2, 4, 8]
    last_error: Exception | None = None

    for attempt, delay in enumerate([0, *backoff_delays]):
        if delay > 0:
            logger.warning("X API 重试第 %d 次，等待 %ds", attempt, delay)
            await asyncio.sleep(delay)
        try:
            response = await self._client.get(url, params=params)
            if response.status_code != 429:
                response.raise_for_status()
                return response
            # 429: 尝试读取 rate limit reset header
            reset_ts = response.headers.get("x-rate-limit-reset")
            if reset_ts:
                wait = max(int(reset_ts) - int(time.time()), 1)
                if wait <= 60:
                    logger.warning("X API 429，等待 rate-limit-reset %ds", wait)
                    await asyncio.sleep(wait)
                    continue
            last_error = httpx.HTTPStatusError(
                "429 Too Many Requests",
                request=response.request,
                response=response,
            )
        except httpx.HTTPStatusError:
            raise
        except httpx.HTTPError as e:
            last_error = e
            logger.warning("X API 网络异常: %s", e)

    if last_error:
        raise last_error
    msg = "X API 请求异常"
    raise XApiError(msg)
```

在文件顶部添加 `import time`。

- [ ] **Step 2: 验证**

Run: `pyright app/fetcher/x_api.py && pytest tests/test_x_api_fetcher.py -v`

### Task 7: process_service `raise last_error` 安全化 + date.today() 修复

**Files:**
- Modify: `app/services/process_service.py:226, 245, 582, 597`

- [ ] **Step 1: `raise last_error` 前加 assert**

行 225-226 改为:
```python
logger.error("全局分析连续失败，中止 pipeline")
assert last_error is not None, "重试循环未执行"
raise last_error
```

行 244-245 同理（`_run_dedup_with_retry` 的 `raise last_error`）。

删除两处 `# type: ignore[misc]` 注释。

- [ ] **Step 2: `date.today()` 改为 `get_today_digest_date()`**

行 582 和 597 的 `date.today()` 改为:
```python
from app.config import get_today_digest_date
call_date=digest_date or get_today_digest_date(),
```

- [ ] **Step 3: 验证**

Run: `pyright app/services/process_service.py && pytest tests/ -q --tb=short`

### Task 8: ThirdPartyFetcher 补充抽象方法

**Files:**
- Modify: `app/fetcher/third_party.py`

- [ ] **Step 1: 补充 fetch_single_tweet**

```python
async def fetch_single_tweet(self, tweet_id: str) -> RawTweet:
    """第三方单条推文抓取（尚未实现）。

    签名需与 BaseFetcher.fetch_single_tweet(tweet_id: str) 保持一致。
    """
    raise NotImplementedError("第三方单条推文抓取功能将在 Phase 2 实现")
```

- [ ] **Step 2: 验证**

Run: `pyright app/fetcher/third_party.py`

### Task 9: fetch_service 401/403 立即中止

**Files:**
- Modify: `app/services/fetch_service.py:107-137`

- [ ] **Step 1: 在 except 块中区分 HTTP 状态码**

```python
except (httpx.HTTPError, XApiError) as e:
    # 401/403 说明 Bearer Token 失效，立即中止
    if isinstance(e, httpx.HTTPStatusError) and e.response.status_code in (401, 403):
        logger.error("X API 认证失败(%d)，中止全部账号抓取", e.response.status_code)
        raise
    logger.warning("抓取账号 %s 失败（API 错误）: %s", ...)
    fail_count += 1
    ...
```

- [ ] **Step 2: 验证**

Run: `pytest tests/test_fetch_service.py -v`

### Task 10: 安全配置读取函数

**Files:**
- Modify: `app/config.py` — 新增 `safe_int_config` 和 `safe_float_config`

- [ ] **Step 1: 在 config.py 中添加安全转换函数**

```python
async def safe_int_config(db: AsyncSession, key: str, default: int) -> int:
    """安全读取整数配置，转换失败时返回默认值。"""
    raw = await get_system_config(db, key, str(default))
    try:
        return int(raw)
    except (ValueError, TypeError):
        logger.warning("配置 %s 值 '%s' 无法转为 int，使用默认值 %d", key, raw, default)
        return default

async def safe_float_config(db: AsyncSession, key: str, default: float) -> float:
    """安全读取浮点配置，转换失败时返回默认值。"""
    raw = await get_system_config(db, key, str(default))
    try:
        return float(raw)
    except (ValueError, TypeError):
        logger.warning("配置 %s 值 '%s' 无法转为 float，使用默认值 %s", key, raw, default)
        return default
```

- [ ] **Step 2: 替换 digest_service.py 和 digest.py 中的不安全 int()/float() 调用**

`digest_service.py:127-128`:
```python
# 当前: cover_timeout = float(await get_system_config(..., "30"))
# 改为: cover_timeout = await safe_float_config(self._db, "cover_generation_timeout", 30.0)
```

`app/api/digest.py:84` 及其他 `int(await get_system_config(...))` 调用同理替换。

- [ ] **Step 3: 验证**

Run: `pyright app/config.py app/services/digest_service.py && pytest tests/ -q --tb=short`

### Task 11: summary_generator 降级标志传播

**Files:**
- Modify: `app/services/digest_service.py:110-115`

- [ ] **Step 1: 使用 _degraded 标志记录到日志**

```python
# 当前:
summary, cost_response, _degraded = await generate_summary(...)

# 改为:
summary, cost_response, degraded = await generate_summary(...)
if degraded:
    logger.warning("导读摘要使用了降级默认文本 (digest_date=%s)", digest_date)
```

- [ ] **Step 2: 验证**

Run: `pyright app/services/digest_service.py`

### 轮次验证

```bash
ruff check . && pyright && pytest tests/ -q --tb=short
```

---

## 第 3 轮 — ORM 枚举化 + Service 层枚举常量

> 目标：将 ORM 模型的裸 str 字段改用枚举，Service 层赋值处使用枚举常量替代字符串字面量。
> 包含问题：C-7, I-9 (settings type: ignore), S-11 (PipelineResult)

### Task 12: ORM 模型字段枚举化

**Files:**
- Modify: `app/models/digest.py:26-27`
- Modify: `app/models/job_run.py:17-20`
- Modify: `app/models/topic.py:18`
- Modify: `app/models/digest_item.py:21,36`
- Modify: `app/models/tweet.py:41`
- Modify: `app/models/api_cost_log.py:18`

- [ ] **Step 1: Service/API 层赋值处统一使用枚举常量替代字符串字面量**

> **重要**: ORM 字段保持 `Mapped[str]`（SQLite 不支持原生 ENUM），不改列类型。仅修改赋值处使用枚举常量，利用 StrEnum 的隐式 str 兼容性。

需要替换的完整清单（通过 grep 确认）：

| 文件 | 行 | 当前 | 改为 |
|------|------|------|------|
| `services/pipeline_service.py` | 99 | `job_run.status = "completed"` | `job_run.status = JobStatus.COMPLETED` |
| `services/pipeline_service.py` | 113 | `job_run.status = "failed"` | `job_run.status = JobStatus.FAILED` |
| `services/backup_service.py` | 76 | `job.status = "completed"` | `job.status = JobStatus.COMPLETED` |
| `services/backup_service.py` | 84 | `job.status = "failed"` | `job.status = JobStatus.FAILED` |
| `api/digest.py` | 328 | `job_run.status = "completed"` | `job_run.status = JobStatus.COMPLETED` |
| `api/digest.py` | 341 | `job_run.status = "failed"` | `job_run.status = JobStatus.FAILED` |
| `api/digest.py` | 410 | `digest.status = "published"` | `digest.status = DigestStatus.PUBLISHED` |
| `api/manual.py` | 64 | `job_run.status = "completed"` | `job_run.status = JobStatus.COMPLETED` |
| `api/manual.py` | 80 | `job_run.status = "failed"` | `job_run.status = JobStatus.FAILED` |
| `services/lock_service.py` | 24,50,72 | `JobRun.status == "running"` | `JobRun.status == JobStatus.RUNNING` |
| `services/lock_service.py` | 50,75 | `status="failed"` | `status=JobStatus.FAILED` |

每个文件顶部添加对应枚举 import：`from app.schemas.enums import JobStatus`、`DigestStatus` 等。

- [ ] **Step 3: 验证**

Run: `ruff check . && pyright && pytest tests/ -q --tb=short`
Expected: 0 errors, 537 passed

### Task 13: settings type: ignore 消除

**Files:**
- Modify: `app/api/settings.py:53-102`

- [ ] **Step 1: 拆分 `_parse_config_value` 为专用函数**

```python
def _parse_int(value: str, default: int) -> int:
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

def _parse_bool(value: str) -> bool:
    return value.lower() in ("true", "1", "yes")

def _parse_int_list(value: str) -> list[int]:
    return [int(x) for x in value.split(",") if x.strip()]
```

- [ ] **Step 2: 在 get_settings 中使用专用函数替代 `_parse_config_value`，删除全部 `type: ignore[arg-type]`**

- [ ] **Step 3: 验证**

Run: `pyright app/api/settings.py`
Expected: 0 errors, 0 type: ignore

### Task 14: PipelineResult.status 枚举化

**Files:**
- Modify: `app/schemas/pipeline_types.py:14,27`

- [ ] **Step 1: 使用 Literal 或枚举**

```python
from typing import Literal

class PipelineResult(BaseModel):
    status: Literal["completed", "failed", "skipped"]
    failed_step: Literal["fetch", "process", "digest"] | None = None
```

- [ ] **Step 2: 验证**

Run: `pyright app/schemas/pipeline_types.py app/services/pipeline_service.py`

### 轮次验证

```bash
ruff check . && pyright && pytest tests/ -q --tb=short
make gen && git diff --exit-code packages/openapi-client/
```

---

## 第 4 轮 — 重构消除重复代码

> 目标：提取公共函数、消除 N+1、简化冗余逻辑。
> 包含问题：I-4 (DI 绕过), I-6 (双重锁检查), I-14 (相对路径), S-1~S-5, S-7~S-10, S-12~S-15

### Task 15: 提取公共 cost_logger

**Files:**
- Create: `app/lib/cost_logger.py`
- Modify: `app/services/digest_service.py:354-365`
- Modify: `app/services/process_service.py:574-602`

- [ ] **Step 1: 创建 `app/lib/cost_logger.py`**

```python
"""API 调用成本记录公共函数。"""
from datetime import date
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.api_cost_log import ApiCostLog
from app.schemas.processor_types import ClaudeResponse
from app.config import get_today_digest_date

def record_api_cost(
    db: AsyncSession,
    response: ClaudeResponse,
    call_type: str,
    digest_date: date | None,
    service: str = "claude",
) -> None:
    db.add(ApiCostLog(
        call_date=digest_date or get_today_digest_date(),
        service=service,
        call_type=call_type,
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        estimated_cost=response.estimated_cost,
        success=True,
        duration_ms=response.duration_ms,
    ))

def record_api_cost_failure(
    db: AsyncSession,
    call_type: str,
    digest_date: date | None,
    service: str = "claude",
) -> None:
    db.add(ApiCostLog(
        call_date=digest_date or get_today_digest_date(),
        service=service,
        call_type=call_type,
        success=False,
    ))
```

- [ ] **Step 2: DigestService 和 ProcessService 的 `_record_cost` 改为调用公共函数**

- [ ] **Step 3: 验证**

Run: `pytest tests/ -q --tb=short`

### Task 16: 提取公共 `get_current_digest_with_items` + 注册全局异常处理器

**Files:**
- Modify: `app/services/digest_service.py` — 新增方法
- Modify: `app/api/digest.py` — 替换重复查询
- Modify: `app/main.py:66-73` — 注册 ClaudeAPIError/GeminiAPIError 处理器

- [ ] **Step 1: DigestService 中新增 `get_current_digest_with_items()`**

消除 `api/digest.py` 中 5 处重复的 "查 digest + 查 items" 查询。

- [ ] **Step 2: 在 main.py 中注册全局异常处理器**

```python
@app.exception_handler(ClaudeAPIError)
async def handle_claude_error(_request: Request, exc: ClaudeAPIError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": f"AI 服务暂不可用: {exc}"})

@app.exception_handler(GeminiAPIError)
async def handle_gemini_error(_request: Request, exc: GeminiAPIError) -> JSONResponse:
    return JSONResponse(status_code=502, content={"detail": f"图像服务暂不可用: {exc}"})
```

- [ ] **Step 3: 验证**

Run: `pytest tests/ -q --tb=short`

### Task 17: DI 一致性修复 + 双重锁删除

**Files:**
- Modify: `app/api/digest.py:161,324-325,430` — 使用 Depends 注入
- Modify: `app/api/digest.py:306` — 删除路由体内重复的 `has_running_job` 检查

- [ ] **Step 1: 三处手动构造 Service 改为 Depends**

`get_preview_by_token` 可以使用专用 DI 函数（不需要 admin 权限但需要 DigestService）。
`regenerate_digest` 和 `add_tweet` 改为使用 `Depends(get_digest_service)`。

- [ ] **Step 2: 删除 regenerate_digest 第 306 行的重复锁检查**

`require_no_pipeline_lock` 已经检查过，路由体内不再需要 `has_running_job`。

- [ ] **Step 3: 验证**

Run: `pytest tests/test_digest_api.py -v`

### Task 18: 其他小修

**Files:**
- Modify: `app/config.py:53` — `ZoneInfo("UTC")` 改用 `UTC` 常量
- Modify: `app/services/pipeline_service.py:157-158` — `object | None` 改为具体类型
- Modify: `app/auth.py:95-105` — 简化冗余条件判断
- Modify: `app/processor/heat_calculator.py:13-14` — 重复的 `BEIJING_TZ`/`UTC` 改为从 config 导入
- Modify: `app/processor/token_estimator.py:12` + `app/processor/batch_strategy.py:13` — `_PROMPT_OVERHEAD_TOKENS` 去下划线前缀（两个文件同步改名）
- Modify: `app/fetcher/x_api.py:33-39` — 删除冗余的 `__aenter__`/`__aexit__` 重写（基类已有默认实现）

- [ ] **Step 1: 逐项修改**

每项都是 1-3 行的改动：
1. `config.py:53`: `utc = ZoneInfo("UTC")` → 直接用已导入的 `UTC`：`return bj_since.astimezone(UTC), bj_until.astimezone(UTC)`
2. `pipeline_service.py:157-158`: `fetch_result: object | None` → `fetch_result: FetchResult | None`（import FetchResult）
3. `auth.py:102-104`: 删除冗余的第二个 `if attempt.locked_until` 分支，只保留 `_login_attempts.pop(username, None)`
4. `heat_calculator.py:13-14`: 删除 `BEIJING_TZ = ZoneInfo(...)` 和 `UTC = ZoneInfo(...)`，改为 `from app.config import BEIJING_TZ` + `from datetime import UTC`
5. `token_estimator.py:12`: `_PROMPT_OVERHEAD_TOKENS` → `PROMPT_OVERHEAD_TOKENS`；`batch_strategy.py:13`: 导入同步更名
6. `x_api.py:33-39`: 删除 `__aenter__` 和 `__aexit__` 方法（继承基类 BaseFetcher 的实现）

- [ ] **Step 2: 验证**

Run: `ruff check . && pyright && pytest tests/ -q --tb=short`

### 轮次验证

```bash
ruff check . && ruff format --check . && pyright && pytest tests/ -q --tb=short
```

---

## 第 5 轮 — 收尾 + 全量验证

> 包含问题：S-15 (空占位文件标注), 全局验证

### Task 19: 空占位文件标注

**Files:**
- Modify: `app/crud.py`, `app/services/notification_service.py`, `app/services/publish_service.py`, `app/schemas/report_types.py`

- [ ] **Step 1: 各文件 docstring 后添加 Phase 2 标注**

```python
# TODO: Phase 2 实现
```

### Task 20: 最终全量验证 + 生成物一致性

- [ ] **Step 1: 后端全量门禁**

```bash
ruff check .
ruff format --check .
pyright
pytest tests/ -q --tb=short
```

- [ ] **Step 2: 生成物一致性**

```bash
make gen && git diff --exit-code
```

- [ ] **Step 3: 前端类型检查（确认后端变更未破坏前端）**

```bash
cd admin && bunx vue-tsc --noEmit && bunx biome check .
```

---

## 问题到 Task 映射

| 问题 | Task | 严重性 | 主要文件 |
|------|------|--------|----------|
| C-1 | 1 | Critical | api/dashboard.py |
| C-2 | 1 | Critical | digest/cover_generator.py |
| C-3 | 2 | Critical | clients/claude_client.py |
| C-4 | 2 | Critical | clients/gemini_client.py |
| C-5 | 5 | Critical | services/pipeline_service.py |
| C-6 | 6 | Critical | fetcher/x_api.py |
| C-7 | 12 | Critical | models/ (10 个字段) |
| I-1 | 7 | Important | services/process_service.py |
| I-2 | 7 | Important | services/process_service.py |
| I-3 | 8 | Important | fetcher/third_party.py |
| I-4 | 17 | Important | api/digest.py |
| I-5 | — | Important | clients/ 单例（评估后不修复：当前单例模式在单进程 uvicorn 下可接受，测试通过 mock.patch 替换） |
| I-6 | 17 | Important | api/digest.py |
| I-7 | 3 | Important | auth.py |
| I-8 | 2 | Important | clients/claude_client.py |
| I-9 | 13 | Important | api/settings.py |
| I-10 | 9 | Important | services/fetch_service.py |
| I-11 | — | Important | processor/json_validator.py（评估后不修复：当前用 `dict[str, object]` 替代 Any 已符合规范，TypedDict 改造需同步改 5+ 个 prompt 模板，投入产出比低） |
| I-12 | 10 | Important | config.py |
| I-13 | 11 | Important | digest_service.py |
| I-14 | 18 | Important | 多处相对路径 |
| S-1 | 16 | Suggestion | api/digest.py |
| S-2 | 16 | Suggestion | api/digest.py 异常映射 |
| S-3 | 15 | Suggestion | 公共 cost_logger |
| S-4 | 18 | Suggestion | process_service 重试逻辑 |
| S-5 | 15 | Suggestion | _get_accounts_map（提取到 cost_logger.py 同层的公共查询模块） |
| S-6 | 18 | Suggestion | config.py UTC |
| S-7 | 16 | Suggestion | digest_service N+1 |
| S-8 | 16 | Suggestion | reorder_items 循环查询 |
| S-9 | 18 | Suggestion | fetch_service 去重范围 |
| S-10 | 18 | Suggestion | dashboard _get_recent_7_days |
| S-11 | 14 | Suggestion | PipelineResult.status |
| S-12 | 17 | Suggestion | reorder_items 签名 |
| S-13 | 16 | Suggestion | main.py 全局处理器 |
| S-14 | 18 | Suggestion | analyzer/batch_merger 重复 |
| S-15 | 19 | Suggestion | 空占位文件 |

---

## 执行结果（待回填）

### 交付物清单
_待回填_

### 偏离项表格
_待回填_

### 问题与修复
_待回填_

### 质量门禁详表
_待回填_

### PR 链接
_待回填_
