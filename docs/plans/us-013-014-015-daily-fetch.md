# US-013 + US-014 + US-015 实施计划

## Context

P0 最后一组任务。当前 fetcher 模块已有 `BaseFetcher`/`XApiFetcher`（US-011）和推文分类器（US-012），但 `FetchService` 只有空壳。本轮实现每日自动抓取全流程，包含容错和限流，完成后 P0 全部结束。

## 分支

```
us-013-014-015-daily-fetch
```

## 修改文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/services/fetch_service.py` | 重写 | 核心：`run_daily_fetch()` 全流程 |
| `app/fetcher/x_api.py` | 修改 | 添加 `_request_with_retry()` 限流重试（US-015） |
| `app/api/deps.py` | 修改 | 添加 `get_fetch_service` 依赖工厂 |
| `tests/test_fetch_service.py` | 新建 | 完整测试覆盖 |

不需要新模型、不需要迁移。

---

## 1. XApiFetcher 限流增强（US-015）

**文件**: `app/fetcher/x_api.py`

在 `XApiFetcher` 中添加 `_request_with_retry()` 私有方法，替换 `fetch_user_tweets` 中的 `self._client.get()` 调用：

```python
async def _request_with_retry(self, url: str, params: dict[str, str]) -> httpx.Response:
    """发送请求，429 时指数退避重试（2s→4s→8s，最多 3 次）。"""
    _BACKOFF_DELAYS = [2, 4, 8]
    response = await self._client.get(url, params=params)
    for delay in _BACKOFF_DELAYS:
        if response.status_code != 429:
            break
        logger.warning("X API 429 限流，%ds 后重试", delay)
        await asyncio.sleep(delay)
        response = await self._client.get(url, params=params)
    response.raise_for_status()
    return response
```

**改动点**：`fetch_user_tweets` 中 `response = await self._client.get(...)` → `response = await self._request_with_retry(...)`

需要添加 `import asyncio`。

---

## 2. FetchService 实现（US-013 + US-014）

**文件**: `app/services/fetch_service.py`

### 类结构

```python
class FetchService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def run_daily_fetch(self, digest_date: date | None = None) -> FetchResult:
        """每日自动抓取所有活跃账号推文。"""
```

### `run_daily_fetch()` 流程

1. **确定日期**: `digest_date = digest_date or get_today_digest_date()`
2. **计算时间窗口**: `since, until = get_fetch_window(digest_date)`
3. **查询活跃账号**: `SELECT * FROM twitter_accounts WHERE is_active=True`
4. **创建 fetcher**: `fetcher = get_fetcher(settings.X_API_BEARER_TOKEN)`
5. **记录开始时间**: `started_at = datetime.now(UTC)`
6. **逐账号抓取**（`for account in accounts`）:
   - **请求间隔**: 第二个账号起 `await asyncio.sleep(1.0)`（US-015 正常间隔 ≥1s）
   - **try 块** (US-014):
     - `raw_tweets = await fetcher.fetch_user_tweets(user_id, since, until)`
     - 逐条分类 → 过滤 KEEP_TYPES
     - 基于 `tweet_id` 去重（查 DB 已有 + 本批次内去重）
     - 映射 `RawTweet → Tweet` 模型并保存
     - 记录 `api_cost_log`（service='x', call_type='fetch_tweets'）
     - 更新 `account.last_fetch_at`
     - `success_count += 1`
   - **except 块** (US-014):
     - 捕获 `Exception`，记录 logger.error
     - 将失败信息追加到 `errors: list[dict]`
     - `fail_count += 1`
     - 继续下一个账号
7. **关闭 fetcher**: `await fetcher.close()`
8. **写入 fetch_log**: 包含 `error_details = json.dumps(errors)` 如有失败
9. **flush + 返回 FetchResult**

### RawTweet → Tweet 字段映射

| RawTweet | Tweet 模型 | 说明 |
|----------|-----------|------|
| `tweet_id` | `tweet_id` | 唯一标识 |
| `author_id` | — | 用于查找 `account_id` |
| `text` | `original_text` | 原文 |
| `created_at` | `tweet_time` | UTC 时间 |
| `public_metrics.*` | `likes/retweets/replies` | 互动指标 |
| `media_urls` | `media_urls` | `json.dumps(list)` |
| — | `tweet_url` | `f"https://x.com/{handle}/status/{tweet_id}"` 覆盖原值 |
| — | `account_id` | 从 TwitterAccount.id 获取 |
| — | `digest_date` | 参数传入 |
| — | `is_quote_tweet` | `classify() == QUOTE` |
| — | `is_self_thread_reply` | `classify() == SELF_REPLY` |
| — | `source` | `"auto"` |

### 去重策略

1. **DB 去重**: 一次性查询当日已有的 `tweet_id` 集合 → `existing_tweet_ids: set[str]`
2. **批次内去重**: 维护 `seen_ids: set[str]`，跨账号去重

---

## 3. 依赖注入（deps.py）

```python
async def get_fetch_service(db: AsyncSession = Depends(get_db)) -> FetchService:
    return FetchService(db)
```

---

## 4. 测试计划（TDD）

**文件**: `tests/test_fetch_service.py`

Mock 策略：
- X API 调用 → `respx` mock
- 时间 → `freezegun`
- DB → 内存 SQLite（conftest `db` fixture）

### 测试用例

| # | 用例 | 覆盖 |
|---|------|------|
| 1 | 正常抓取 2 账号各返回推文 → tweets 表有数据 | US-013 |
| 2 | 推文分类过滤：混合 5 类型 → 只保留 ORIGINAL/SELF_REPLY/QUOTE | US-013 |
| 3 | tweet_id 去重：跨账号重复 → 只保存 1 条 | US-013 |
| 4 | DB 已有推文 → 不重复插入 | US-013 |
| 5 | 无活跃账号 → FetchResult(0,0,0) | US-013 |
| 6 | 账号返回空列表 → new_tweets=0，不报错 | US-013 |
| 7 | 单账号异常 → 记录错误，继续其他 | US-014 |
| 8 | 全部账号失败 → fail_count == total | US-014 |
| 9 | error_details JSON 格式正确 | US-014 |
| 10 | HTTP 429 → 退避重试成功 | US-015 |
| 11 | 429 超过 3 次重试 → 账号失败 | US-015 |
| 12 | fetch_log 字段完整正确 | US-013 |
| 13 | api_cost_log 写入（service=x） | US-013 |
| 14 | last_fetch_at 更新 | US-013 |
| 15 | tweet_url 使用 twitter_handle 构建 | US-013 |
| 16 | is_quote_tweet / is_self_thread_reply 正确设置 | US-013 |

### 测试辅助函数

- `_seed_accounts(db, n)`: 预置 n 个活跃账号
- `_mock_x_api(user_id, tweets, ...)`: 构造 respx mock 响应
- 复用 `test_fetcher.py` 中的 `make_tweet_data()` / `make_api_response()` 模式

---

## 5. 实施顺序（TDD）

1. 编写 `tests/test_fetch_service.py` 全部测试（预期全部失败）
2. 修改 `app/fetcher/x_api.py` 添加限流重试
3. 实现 `app/services/fetch_service.py`
4. 修改 `app/api/deps.py`
5. 运行测试 → 全部通过
6. 运行质量门禁：`ruff check . && ruff format --check . && uv run lint-imports && pyright && pytest`

---

## 6. 验证方式

```bash
# 单元测试
pytest tests/test_fetch_service.py -v

# 全量测试（确保无回归）
pytest

# 质量门禁
ruff check .
ruff format --check .
uv run lint-imports
pyright
```

---

## 7. 边界条件处理

| 场景 | 处理 |
|------|------|
| 推文缺少必要字段 | XApiFetcher._parse_tweet() 已处理：log warning + 跳过 |
| 账号无 twitter_user_id | 跳过该账号，记录 warning |
| 该账号无新推文 | 正常继续，new_tweets=0 |
| 0 条推文通过过滤 | 正常结束，空结果 |
| 全部账号失败 | FetchResult.fail_count == total_accounts |

---

## 执行结果

### 交付物清单

| 文件 | 状态 | 说明 |
|------|------|------|
| `app/services/fetch_service.py` | 新实现 | FetchService.run_daily_fetch() 全流程 |
| `app/fetcher/x_api.py` | 修改 | 添加 _request_with_retry() 限流重试 |
| `app/fetcher/base.py` | 修改 | 添加 close() 默认方法（pyright 类型安全） |
| `app/api/deps.py` | 修改 | 添加 get_fetch_service 依赖工厂 |
| `tests/test_fetch_service.py` | 新建 | 17 个测试用例 |
| `docs/spec/user-stories.md` | 更新 | US-013/014/015 标记已完成 |

### 偏离项

| 计划项 | 实际 | 原因 |
|--------|------|------|
| 16 个测试 | 17 个测试 | 增加了"无 twitter_user_id 的账号跳过"边界测试 |
| 仅修改 4 个文件 | 修改 5 个文件 | BaseFetcher 需要添加 close() 方法以满足 pyright 类型检查 |
| 去重查询限定 digest_date | 全表去重 | tweet_id 是全局唯一（UNIQUE 约束），按全表去重更安全 |

### 问题与修复

1. **pyright 报错 BaseFetcher 无 close()**：FetchService 通过 BaseFetcher 类型引用 fetcher，但 close() 仅在 XApiFetcher 子类定义。解决：在 BaseFetcher 添加空的 close() 默认实现。
2. **ruff 未使用导入**：测试文件中 `timedelta`、`pytest` 未使用，已移除。
3. **ruff 未使用变量**：`_seed_accounts` 返回值在部分测试中不需要，改为不赋值。

### 质量门禁

| 检查项 | 结果 |
|--------|------|
| `ruff check .` | 通过 |
| `ruff format --check .` | 通过 |
| `lint-imports` | 通过（4 contracts kept, 0 broken） |
| `pyright` | 通过（0 errors） |
| `pytest` | 通过（80 tests, 0 failed） |

### PR 链接

https://github.com/neuer/zhixi/pull/4
