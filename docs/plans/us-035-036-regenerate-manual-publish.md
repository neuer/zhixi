# US-035 + US-036: 重新生成草稿 + 手动发布模式

## Context

P3 阶段，US-027/027b/028/029 已完成。US-035（重新生成草稿）是 regenerate 核心功能，解锁 US-051（状态流转测试）。US-036（手动发布模式）是 MVP 发布流程。两者互不依赖，可并行实现。

## 文件变更清单

### 修改文件
| 文件 | 变更 |
|------|------|
| `app/services/digest_service.py` | 新增 `regenerate_digest()` 方法 + 修改 `generate_daily_digest()` 增加 version 参数 + 修改 `_get_topics_with_members()` 过滤空成员话题 |
| `app/api/digest.py` | 新增 3 个路由: `POST /regenerate`, `GET /markdown`, `POST /mark-published` |
| `app/schemas/digest_types.py` | 新增 `MarkdownResponse` schema |

### 新增文件
| 文件 | 内容 |
|------|------|
| `tests/test_regenerate_api.py` | US-035 API 集成测试 |
| `tests/test_regenerate_service.py` | US-035 DigestService.regenerate_digest() 单元测试 |
| `tests/test_publish_api.py` | US-036 GET /markdown + POST /mark-published 测试 |

---

## US-035: 重新生成草稿

### 1. DigestService 变更 (`app/services/digest_service.py`)

#### 1a. `generate_daily_digest()` 增加 version 参数

```python
async def generate_daily_digest(self, digest_date: date | None = None, *, version: int = 1) -> DailyDigest:
```

DailyDigest 构造时使用 `version=version`。现有调用方（pipeline_service）不传此参数，默认 version=1，行为不变。

#### 1b. `_get_topics_with_members()` 过滤空成员话题

regenerate 时旧 topics 仍在 DB 中但其成员 tweet 已指向新 topic，导致旧 topic 成员为空。需过滤：

```python
# 过滤掉无成员的话题（regenerate 后旧话题无成员）
result = [(topic, members) for topic, members in result if members]
```

此改动对首次生成无影响（所有 topic 都有成员）。

#### 1c. 新增 `regenerate_digest()` 方法

核心流程：
1. 查询旧版本 (is_current=true，不校验 status)
2. 重置推文状态 (is_processed=false, is_ai_relevant=true, topic_id=null)
3. 旧版本 is_current=false
4. M2 (ProcessService.run_daily_process) + M3 (generate_daily_digest)
5. 失败回滚：恢复旧版本 is_current=true

当日无草稿时：等价于首次生成 v1（old_version=0），跳过 is_current=false 步骤。

#### 1d. 辅助方法
- `_get_current_digest_or_none(digest_date)` — 查询 is_current=true 的 digest，不校验 status
- `_reset_tweets_for_reprocess(digest_date)` — 批量 update 重置推文 AI 字段

### 2. 路由 (`app/api/digest.py`)

`POST /api/digest/regenerate`:
- 依赖: `require_no_pipeline_lock`（增强锁）+ `get_current_admin`
- 基本锁: `has_running_job(db, "pipeline", digest_date)` → 409
- 创建 job_run: job_type="pipeline", trigger_source="regenerate", status="running"
- 成功: 返回 `{message, digest_id, version, item_count, job_run_id}`
- 失败: JSONResponse(500) + job_run 标记 failed + webhook 通知
- job_type="pipeline" 确保与 pipeline 互斥共享增强锁

### 3. 测试

#### test_regenerate_service.py（8 个用例）
1. regenerate v1→v2, is_current 切换正确
2. 首次生成 v1（无旧 digest）
3. 推文 is_processed/is_ai_relevant/topic_id 重置
4. published v1 → draft v2
5. failed v1 → draft v2
6. M3 失败时旧版本 is_current 恢复
7. 旧版本 snapshot 不受影响
8. 旧 topics 无成员不产生 digest_item

#### test_regenerate_api.py（4 个用例）
1. 正常 regenerate → 200
2. 增强锁 → 409
3. 失败 → 500 + job_run 持久化
4. 未认证 → 401

---

## US-036: 手动发布模式

### 4. 路由 (`app/api/digest.py`)

#### `GET /api/digest/markdown`
- 直接读取 is_current=true 的 digest.content_markdown
- 无 digest → 404

#### `POST /api/digest/mark-published`
- 依赖: `require_no_pipeline_lock` + `get_current_admin`
- is_current=true 的 digest，status=published → 409
- draft/failed → published, published_at=now(UTC)

### 5. Schema (`app/schemas/digest_types.py`)

```python
class MarkdownResponse(BaseModel):
    content_markdown: str
```

### 6. 测试

#### test_publish_api.py（7 个用例）
1. GET /markdown → 200 + content_markdown
2. GET /markdown 无 digest → 404
3. POST /mark-published draft → published
4. POST /mark-published 已发布 → 409
5. POST /mark-published 无 digest → 404
6. POST /mark-published failed → published
7. 未认证 → 401

---

## 实施顺序

1. Schema 类型 → `digest_types.py` 新增 MarkdownResponse
2. Service 层 → `digest_service.py` 修改 + 新增
3. 测试 Service → `test_regenerate_service.py`（红灯→绿灯）
4. 路由层 → `digest.py` 新增 3 个路由
5. 测试 API → `test_regenerate_api.py` + `test_publish_api.py`（红灯→绿灯）
6. 质量门禁 → ruff + pyright + pytest 全量

## 验证

```bash
uv run pytest tests/test_regenerate_service.py tests/test_regenerate_api.py tests/test_publish_api.py -v
uv run pytest
uv run ruff check . && uv run ruff format --check . && uv run pyright
```
