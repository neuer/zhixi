# US-040 + US-041 实施计划：Dashboard 首页 + 系统设置页

## Context

P2 阶段后端 API（US-007/008/023-034）和前端骨架（US-039）已完成。US-040 和 US-041 是 P2 最后两个必须 US（US-026 封面图为可选），需要实现 Dashboard 概览 API + 系统设置 CRUD API + 对应前端页面。

两个 US 均依赖 US-039（✅），无交叉依赖，后端可顺序实现后统一做前端。

---

## 实施范围

### US-040: Dashboard 首页
- **后端**: `GET /api/dashboard/overview`（pipeline 状态、digest 状态、今日成本、近 7 天推送记录、告警）
- **前端**: `Dashboard.vue`（状态卡片、成本卡片、「审核今日内容」按钮、告警、7 天记录）
- **不含**: US-043 的 `api-costs`/`api-costs/daily` 端点（P3）、US-044 的 `logs` 端点（P3）

### US-041: 系统设置页
- **后端**: `GET /api/settings`、`PUT /api/settings`、`GET /api/settings/api-status`
- **前端**: `Settings.vue`（配置表单、API 状态检测、DB 信息、保存）

---

## 后端实现

### 1. 新建 `app/schemas/dashboard_types.py`

```python
class ServiceCostItem(BaseModel):
    service: str
    call_count: int
    total_tokens: int
    estimated_cost: float

class CostSummary(BaseModel):
    total_cost: float
    by_service: list[ServiceCostItem]

class PipelineStatus(BaseModel):
    status: str | None          # running/completed/failed/skipped/None（今日无记录）
    started_at: datetime | None
    error_message: str | None

class DigestStatus(BaseModel):
    status: str | None          # draft/published/failed/None
    digest_id: int | None
    item_count: int
    version: int

class DigestDayRecord(BaseModel):
    date: date
    status: str                 # published/draft/failed
    item_count: int
    version: int

class AlertItem(BaseModel):
    job_type: str
    status: str
    error_message: str | None
    started_at: datetime

class DashboardOverviewResponse(BaseModel):
    pipeline_status: PipelineStatus
    digest_status: DigestStatus
    today_cost: CostSummary
    recent_7_days: list[DigestDayRecord]
    alerts: list[AlertItem]
```

### 2. 新建 `app/schemas/settings_types.py`

```python
class SettingsResponse(BaseModel):
    push_time: str
    push_days: list[int]
    top_n: int
    min_articles: int
    publish_mode: str
    enable_cover_generation: bool
    cover_generation_timeout: int
    notification_webhook_url: str
    db_size_mb: float
    last_backup_at: datetime | None

class SettingsUpdate(BaseModel):
    push_time: str | None = None
    push_days: list[int] | None = None
    top_n: int | None = None
    min_articles: int | None = None
    publish_mode: str | None = None
    enable_cover_generation: bool | None = None
    cover_generation_timeout: int | None = None
    notification_webhook_url: str | None = None

class ApiStatusItem(BaseModel):
    status: str                  # ok/error/unconfigured
    latency_ms: int | None = None

class ApiStatusResponse(BaseModel):
    x_api: ApiStatusItem
    claude_api: ApiStatusItem
    gemini_api: ApiStatusItem
    wechat_api: ApiStatusItem
```

### 3. 实现 `app/api/dashboard.py`

`GET /overview`：
- 直接在路由中查询（读取聚合，无需 Service 层，与 `GET /digest/today` 模式一致）
- 查 job_runs 获取今日 pipeline 最新状态
- 查 daily_digest 获取今日 current digest 状态
- 查 api_cost_log 聚合今日成本（SQL: SUM/COUNT/GROUP BY service）
- 查 daily_digest 近 7 天每天的代表性版本（published → is_current → max version）
- 查 job_runs 近 7 天 failed 记录作为 alerts

### 4. 实现 `app/api/settings.py`

`GET /`：
- 查 system_config 全部配置键，转换 push_days 为 int 数组、布尔值、整数等
- 读 SQLite 文件大小（`os.path.getsize`）
- 查 job_runs 最近一次 backup completed 的 finished_at

`PUT /`：
- 请求体 SettingsUpdate，所有字段可选
- 校验：push_days 非空数组（422）
- 逐键 upsert system_config
- push_days 转回逗号分隔字符串存储

`GET /api-status`：
- asyncio.gather 并发 ping（每个 5s 超时）
- X API: httpx GET `/2/users/me`
- Claude: `anthropic.AsyncAnthropic.models.list()`
- Gemini: key 为空 → unconfigured，否则尝试 list models
- WeChat: MVP 直接 unconfigured

### 5. 更新 `app/api/deps.py`

无需新增 Service 依赖工厂（dashboard 和 settings 直接在路由中操作 DB）。

### 6. 更新 OpenAPI 生成

后端新增端点后，运行 `make gen` 重新生成 TS 类型。

---

## 前端实现

### 7. `admin/src/views/Dashboard.vue`

布局（移动端优先，Vant 组件）：
- **顶部 NavBar**：「智曦管理后台」
- **Pipeline 状态卡片**（van-cell-group）：显示最近 pipeline 状态（completed/failed/running/无记录）
- **Digest 状态卡片**：草稿状态、条目数、版本号
- **API 成本卡片**：今日总费用（估算）
- **「审核今日内容」大按钮**（van-button type=primary block size=large）→ 路由跳转 `/digest`
- **告警区域**（失败时显示红色 van-notice-bar 或 van-cell）
- **近 7 天推送记录**（van-cell-group）：日期 + 状态 Badge

### 8. `admin/src/views/Settings.vue`

布局：
- **NavBar**：「系统设置」+ 返回按钮
- **推送配置**（van-cell-group）：
  - push_time：van-field（时间选择）
  - push_days：van-checkbox-group（周一~周日）
  - top_n：van-stepper
  - min_articles：van-stepper
- **发布配置**：
  - publish_mode：van-radio-group（manual/api）
  - enable_cover_generation：van-switch
  - cover_generation_timeout：van-stepper（秒）
- **通知配置**：
  - notification_webhook_url：van-field
- **API 状态**（van-cell-group + van-button 触发检测）：
  - 每个 API 显示 status + latency
  - API Key 只显示「已配置/未配置」
- **数据库信息**：
  - DB 大小（MB）
  - 最近备份时间
- **保存按钮**（van-button type=primary block）

---

## 测试

### 9. `tests/test_dashboard_api.py`

| 测试 | 验证点 |
|------|--------|
| test_overview_empty | 无数据时正常返回空/默认值 |
| test_overview_with_data | 有 job_run + digest + cost_log 时正确聚合 |
| test_overview_alerts | failed job_runs 出现在 alerts |
| test_overview_cost_aggregation | 多条 cost_log 正确 SUM/COUNT |
| test_overview_7day_records | 近 7 天 digest 记录正确返回 |
| test_overview_requires_auth | 无 JWT → 401 |

### 10. `tests/test_settings_api.py`

| 测试 | 验证点 |
|------|--------|
| test_get_settings | 返回全部配置（push_days 为数组） |
| test_update_settings_partial | 部分更新成功 |
| test_update_push_days_empty | 空数组 → 422 |
| test_update_push_days_valid | 合法数组写入 DB 为逗号字符串 |
| test_api_status_unconfigured | 所有 key 为空 → unconfigured |
| test_api_status_mock_ping | mock httpx/anthropic → ok + latency |
| test_settings_requires_auth | 无 JWT → 401 |
| test_get_settings_db_info | 返回 DB 大小和备份时间 |

---

## 文件变更清单

| 文件 | 操作 |
|------|------|
| `app/schemas/dashboard_types.py` | 新建 |
| `app/schemas/settings_types.py` | 新建 |
| `app/api/dashboard.py` | 修改（填充路由） |
| `app/api/settings.py` | 修改（填充路由） |
| `tests/test_dashboard_api.py` | 新建 |
| `tests/test_settings_api.py` | 新建 |
| `admin/src/views/Dashboard.vue` | 修改（实现页面） |
| `admin/src/views/Settings.vue` | 修改（实现页面） |
| `packages/openapi-client/src/gen/types.gen.ts` | 自动生成（make gen） |
| `openapi.json` | 自动生成 |

---

## 实施顺序

1. **schemas** → dashboard_types.py + settings_types.py
2. **测试（TDD 红灯）** → test_dashboard_api.py + test_settings_api.py
3. **后端路由** → dashboard.py（overview）→ settings.py（GET/PUT/api-status）
4. **测试绿灯** → 全部通过
5. **质量门禁** → ruff + pyright + pytest
6. **make gen** → 重新生成 TS 类型
7. **前端** → Dashboard.vue → Settings.vue
8. **前端门禁** → biome + vue-tsc + build

---

## 验证方式

1. `uv run pytest tests/test_dashboard_api.py tests/test_settings_api.py -v` — 全部通过
2. `uv run pytest` — 全量测试无新增失败
3. `uv run ruff check . && uv run ruff format --check .` — lint 通过
4. `uv run pyright` — 0 errors
5. `make gen && git diff --exit-code packages/` — 生成物一致
6. `cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build` — 前端门禁全通过

---

## 执行结果

### 交付物清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `app/schemas/dashboard_types.py` | 新建 | 64 |
| `app/schemas/settings_types.py` | 新建 | 53 |
| `app/api/dashboard.py` | 修改 | 191 |
| `app/api/settings.py` | 修改 | 199 |
| `tests/test_dashboard_api.py` | 新建 | 290 |
| `tests/test_settings_api.py` | 新建 | 227 |
| `admin/src/views/Dashboard.vue` | 修改 | 184 |
| `admin/src/views/Settings.vue` | 修改 | 307 |
| `admin/tsconfig.json` | 修改 | +1（路径别名） |
| `packages/openapi-client/src/gen/types.gen.ts` | 自动生成 | +116 |
| `docs/spec/user-stories.md` | 修改 | 2 行状态更新 |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | Dashboard overview 仅含 architecture.md 契约字段 | 扩展了 pipeline_status 和 digest_status 子结构 | US-040 验收标准要求"pipeline状态、digest状态"，architecture.md 的 overview 响应未包含这些，属于规范补充 |
| 2 | Gemini API 实际 ping list_models | 有 key 则直接返回 ok（latency=0） | MVP 阶段不引入 google-generativeai 依赖，等 US-026 封面图时再实际集成 |
| 3 | 无 tsconfig 路径别名计划 | 新增 `@zhixi/openapi-client` 路径别名 | admin 需要导入 packages/openapi-client 生成的类型，tsconfig paths 是必要配置 |

### 问题与修复

| 问题 | 解决 |
|------|------|
| total_tokens 测试断言错误（15000 vs 16500） | total_tokens = SUM(input + output)，修正测试期望值 |
| biome --unsafe 自动重命名模板引用变量 | 手动恢复 timeColumns/dayOptions 原名，biome 无法识别 Vue 模板引用属于已知限制 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 112 files formatted |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 334 passed (含 15 新测试) |
| biome check | ✅ 0 errors, 12 warnings（Vue 模板引用误报） |
| vue-tsc | ✅ 通过 |
| bun run build | ✅ 构建成功 |
| make gen | ✅ 生成物一致 |

### PR 链接

https://github.com/neuer/zhixi/pull/17
