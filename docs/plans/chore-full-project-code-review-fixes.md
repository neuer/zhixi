# 全项目代码审查修复实施计划

## Context

基于 5 个并行审查 Agent 的深度分析（Spec/Plan 对齐、后端代码质量、前端代码质量、测试覆盖、安全与错误处理），共发现 1 个 Critical、17 个 Important、30+ 个 Minor 问题。本计划将全部修复项按优先级和耦合度组织为 5 个实施轮次，每轮独立可测试。

**不包含**：4 个前端 stub 页面实现（Login/Setup/Accounts/DigestEdit）——这些是独立功能开发，非本次审查修复范围。

---

## Round 1: P0 — Critical 修复 + 快速安全修复

> 目标：消除唯一 Critical 和最紧迫的输入校验/安全问题。改动最小，收益最高。

### 1.1 XApiFetcher 实现异步上下文管理器
- **文件**: `app/fetcher/x_api.py`
- **变更**: 添加 `__aenter__`/`__aexit__` 方法，支持 `async with XApiFetcher(...) as fetcher:` 用法
- **同步更新**: `app/services/fetch_service.py` 中改用 `async with` 替代手动 `try/finally/close()`

### 1.2 SettingsUpdate 值域校验增强
- **文件**: `app/schemas/settings_types.py:23-42`
- **变更**:
  - `push_time`: 添加 `field_validator` 校验 HH:MM 格式
  - `publish_mode`: 改为 `Literal["manual", "api"]`
  - `top_n`: 添加 `Field(ge=1, le=50)`
  - `min_articles`: 添加 `Field(ge=0, le=50)`
  - `push_days` 列表项: 添加 `field_validator` 校验值域 1-7
  - `cover_generation_timeout`: 添加 `Field(ge=5, le=300)`

### 1.3 EditItemRequest 字段长度限制
- **文件**: `app/schemas/digest_types.py:70-77`
- **变更**: 各字段添加 `max_length`（title=200, translation=5000, summary=2000, perspectives=5000, comment=2000）

### 1.4 LoginRequest/SetupInitRequest password 长度限制
- **文件**: `app/schemas/auth_types.py`
- **变更**: `password` 字段添加 `max_length=128`

### 1.5 ArticlePreview 安全修复
- **文件**: `admin/src/components/ArticlePreview.vue`
- **变更**:
  - 行 106, 121: 添加 `rel="noopener noreferrer"`
  - 行 105, 119: 添加 URL 协议校验工具函数 `safeHref(url)`，非 http/https 协议返回 `#`

### 测试验证
```bash
# 后端
pytest tests/test_settings_api.py tests/test_auth.py tests/test_digest_edit_api.py -v
ruff check app/schemas/ app/fetcher/
pyright app/schemas/ app/fetcher/

# 前端
cd admin && bunx vue-tsc --noEmit
```

---

## Round 2: P1 — 后端类型安全与 DRY

> 目标：消除 `object` 类型滥用、重复代码、封装违规。

### 2.1 dashboard.py `object` → 具体类型
- **文件**: `app/api/dashboard.py`
- **变更**:
  - `_get_pipeline_status(db, today: object)` → `today: date`
  - `_get_digest_status(db, today: object)` → `today: date`
  - `_get_today_cost(db, today: object)` → `today: date`
  - `_get_recent_7_days(db, today: object)` → `today: date`
  - 删除所有 `assert isinstance(today, date_type)` 断言
  - `_aggregate_cost` 的 `where_clause: object` → 使用 `sqlalchemy.sql.elements.ColumnElement[bool]` 或保留并添加注释说明
  - `by_date: dict[object, DailyDigest]` → `dict[date, DailyDigest]`
  - 删除不再需要的 `# type: ignore` 注释

### 2.2 `_ensure_utc` 提取为共享工具
- **目标文件**: `app/config.py`（已有 `get_today_digest_date` 等时间工具）
- **变更**:
  - 在 `app/config.py` 末尾添加 `_ensure_utc(dt: datetime) -> datetime`
  - `app/services/digest_service.py:37-41`: 删除本地定义，改为 `from app.config import _ensure_utc`
  - `app/services/process_service.py:676-680`: 删除本地定义，改为 `from app.config import _ensure_utc`

### 2.3 路由层调用私有方法 → 公共方法
- **文件**: `app/services/digest_service.py`
  - 新增公共方法 `async def check_draft_editable(self, digest_date: date) -> DailyDigest`，内部委托 `_get_current_draft`
- **文件**: `app/api/digest.py:430`
  - 改为调用 `digest_svc.check_draft_editable(digest_date)`，删除 `# noqa: SLF001`

### 2.4 settings.py `object` 类型修复
- **文件**: `app/api/settings.py:52,63`
- **变更**:
  - `_parse_config_value` 返回类型 `object` → `int | bool | str | list[int]`
  - `_serialize_config_value` 参数类型 `object` → `int | bool | str | list[int]`

### 2.5 cover_generator 成本记录代码去重
- **文件**: `app/digest/cover_generator.py`
- **变更**: 提取 `_record_cost_log(db, digest_date, model, prompt_tokens, ..., success, error_message)` 辅助函数，三处调用统一

### 2.6 json_validator 类型标注完善
- **文件**: `app/processor/json_validator.py:34`
- **变更**: `def validate_and_fix(raw_text: str, schema: dict)` → `schema: dict[str, object]` 和 `-> dict[str, object]`

### 测试验证
```bash
pytest -x
ruff check .
pyright
```

---

## Round 3: P2 — 前端代码质量

> 目标：消除重复代码、修复类型安全、统一代码风格。

### 3.1 提取共享工具模块
- **新文件**: `admin/src/utils/status.ts`
  ```typescript
  type TagType = "primary" | "success" | "warning" | "danger" | "default";
  interface StatusInfo { text: string; type: TagType; color: string }
  const statusMap: Record<string, StatusInfo> = { ... }
  export function getStatus(status: string | null | undefined): StatusInfo
  ```
- **新文件**: `admin/src/utils/format.ts`
  ```typescript
  export function formatDate(dateStr: string, withYear?: boolean): string
  export function safeHref(url: string): string  // 协议校验
  ```
- **更新文件**:
  - `Dashboard.vue`: 删除本地 statusMap/getStatus，从 utils 导入
  - `Digest.vue`: 删除本地 statusMap/getStatus，从 utils 导入
  - `History.vue`: 删除本地 statusMap/getStatus 和 formatDate，从 utils 导入
  - `ArticlePreview.vue`: 删除本地 formatDate，从 utils 导入

### 3.2 Dashboard 嵌套三元表达式重构
- **文件**: `admin/src/views/Dashboard.vue`
- **变更**: 将行 78-108 的颜色→tag type 映射移入 statusMap（统一返回 `type` 字段），模板中直接用 `getStatus(xxx).type`

### 3.3 Preview.vue 类型安全修复
- **文件**: `admin/src/views/Preview.vue`
- **变更**:
  - 行 18: `route.query.token as string` → `Array.isArray(raw) ? raw[0] : raw`
  - 行 29: `e as AxiosError` → `axios.isAxiosError(e)` 类型守卫
  - 行 41-46: 删除冗余的前端 token 检查（让拦截器处理）

### 3.4 ArticlePreview.vue 类型断言修复
- **文件**: `admin/src/components/ArticlePreview.vue`
- **变更**:
  - 行 13: `visibleItems()` → `computed(() => ...)`
  - 行 30, 44: 添加运行时类型校验替代 `as` 断言

### 3.5 路由风格统一
- **文件**: `Settings.vue:139`, `ApiCosts.vue:39`, `Logs.vue:61`
- **变更**: 在 `<script setup>` 中添加 `const router = useRouter()`，模板中 `$router.back()` → `router.back()`

### 3.6 Logs.vue v-for key 修复
- **文件**: `admin/src/views/Logs.vue:78`
- **变更**: `:key="idx"` → `:key="log.timestamp + '-' + idx"`

### 测试验证
```bash
cd admin && bunx vue-tsc --noEmit && bunx biome check .
```

---

## Round 4: P3 — 测试基础设施

> 目标：消除测试辅助函数的跨文件重复，集中到 conftest。

### 4.1 创建共享测试工厂
- **文件**: `tests/conftest.py` 扩展（不新建文件，保持简单）
- **添加以下工厂函数**:

```python
# --- 工厂函数（非 fixture，直接 import 使用）---

def mock_claude_response(content: str = "摘要") -> ClaudeResponse:
    """构造 Claude API mock 响应"""

async def seed_account(db: AsyncSession, *, handle: str = "testuser",
                       display_name: str = "Test User",
                       **overrides: object) -> TwitterAccount:
    """创建测试用 TwitterAccount"""

async def seed_config(db: AsyncSession, *,
                      cover_enabled: bool = True,
                      **overrides: object) -> None:
    """创建测试用 SystemConfig 默认配置"""

def make_tweet_data(tweet_id: str = "1001", author_id: str = "u1",
                    text: str = "测试推文", **overrides: object) -> dict[str, object]:
    """构造 X API 推文数据"""

def make_api_response(tweets: list[dict[str, object]],
                      next_token: str | None = None) -> dict[str, object]:
    """构造 X API 响应"""
```

### 4.2 迁移所有测试文件
- 以下文件删除本地重复定义，改为从 `tests.conftest` 导入：

| 函数 | 需更新的文件 |
|------|-------------|
| `_mock_claude_response` | test_process_service, test_summary_generator, test_digest_service, test_batch_merger, test_analyzer, test_translator, test_add_tweet_api, test_regenerate_service（8 个） |
| `_seed_account` | test_process_service, test_accounts, test_digest_service, test_regenerate_service, test_history_api, test_fetch_service（6 个） |
| `_seed_config` | test_state_transition, test_api, test_digest_edit_api, test_dashboard_api, test_manual_generate_cover_api, test_digest_api（6 个） |
| `_make_tweet_data/_make_api_response` | test_fetch_service（1 个） |

### 测试验证
```bash
pytest -x  # 全部 537+ 测试必须通过
```

---

## Round 5: P4 — 可观测性与杂项

> 目标：增强降级场景可观测性，修复剩余 Minor 问题。

### 5.1 摘要/封面图降级告警
- **文件**: `app/digest/summary_generator.py:67-72`
  - 在 except 分支调用 `send_alert("摘要生成降级", ...)`
  - 返回元组增加 `degraded: bool` 标志
- **文件**: `app/digest/cover_generator.py:119-153`
  - 在 except 分支调用 `send_alert("封面图生成失败", ...)`

### 5.2 错误消息脱敏
- **文件**: `app/api/digest.py:353`, `app/api/manual.py:89`
- **变更**: `str(exc)[:200]` → 返回通用消息 `"操作失败，请稍后重试"`，详细错误仅 logger.error

### 5.3 digest.py add-tweet 异常收窄
- **文件**: `app/api/digest.py:450-451`
- **变更**: `except Exception` → `except (httpx.HTTPError, XApiError)`，其他异常交给默认 500 handler

### 5.4 非 except 块 `from None` 清理
- **文件**: `app/api/manual.py:47,109` 等
- **变更**: 非 `except` 块中的 `raise HTTPException(...) from None` 去掉 `from None`

### 5.5 WechatClient 占位方法改 async
- **文件**: `app/publisher/wechat_client.py:16-26`
- **变更**: `def get_access_token/upload_article/send_mass` → `async def`

### 5.6 logging_config 统一 pathlib
- **文件**: `app/logging_config.py:66-72`
- **变更**: `os.path.dirname/join` → `Path` 风格

### 测试验证
```bash
pytest -x
ruff check .
pyright
cd admin && bunx vue-tsc --noEmit
```

---

## 文件变更汇总

| 轮次 | 新建文件 | 修改文件数 | 预估改动行数 |
|------|---------|-----------|-------------|
| R1 | 0 | 5 | ~80 |
| R2 | 0 | 8 | ~120 |
| R3 | 2 | 8 | ~150 |
| R4 | 0 | 15（conftest + 14 个测试文件） | ~300 |
| R5 | 0 | 7 | ~60 |
| **合计** | **2** | **~35（去重后）** | **~710** |

## 质量门禁

每轮完成后必须通过：
```bash
# 后端
ruff check .
ruff format --check .
pyright
pytest -x

# 前端
cd admin && bunx biome check .
cd admin && bunx vue-tsc --noEmit
```

---

## 执行结果（完成后回填）

> 待实施完成后回填：交付物清单、偏离项表格、问题与修复、质量门禁详表、PR 链接
