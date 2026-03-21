# US-043 + US-044: API 成本监控 + Dashboard 日志展示

## Context

P3 阶段接近尾声，Dashboard overview 已实现（US-040），包含今日成本概要。US-043 需要增加更详细的成本分析（今日/本月汇总 + 30 天趋势），US-044 需要读取 `data/logs/` 下的 JSON 日志文件并返回给前端展示。

两个 US 互不依赖，后端各增加 1-2 个 API 端点，前端各增加一个新页面。

## 关键文件

**后端修改：**
- `app/api/dashboard.py` — 新增 3 个路由
- `app/schemas/dashboard_types.py` — 新增响应模型

**前端新增：**
- `admin/src/views/ApiCosts.vue` — 成本监控页面
- `admin/src/views/Logs.vue` — 日志展示页面
- `admin/src/router/index.ts` — 新增路由

**测试：**
- `tests/test_dashboard_api.py` — 补充测试

**生成链路：**
- `packages/openapi-client/src/gen/types.gen.ts` — 自动更新

## US-043: API 成本监控

### API 设计（来自 architecture.md）

**1. `GET /api/dashboard/api-costs`** → 今日 + 本月汇总

响应：
```json
{
  "today": {"total_cost": 0.85, "by_service": [{"service": "claude", "call_count": 25, "total_tokens": 150000, "estimated_cost": 0.82}]},
  "this_month": {"total_cost": 18.50, "by_service": [...]}
}
```

实现：复用 `_get_today_cost()` 逻辑，新增 `_get_month_cost()` 按 `call_date` 范围筛选（本月 1 号 ~ 今天）。

**2. `GET /api/dashboard/api-costs/daily`** → 最近 30 天按日趋势

响应：
```json
{
  "days": [{"date": "2026-03-21", "total_cost": 1.20, "claude_cost": 1.15, "x_cost": 0.05}]
}
```

实现：GROUP BY call_date, service，Python 端合并每日多 service 到一行。按 date 降序。

### Schema 新增

```python
class ApiCostsResponse(BaseModel):
    today: CostSummary       # 复用已有
    this_month: CostSummary  # 复用已有

class DailyCostItem(BaseModel):
    date: date
    total_cost: float
    claude_cost: float
    x_cost: float
    gemini_cost: float

class DailyCostsResponse(BaseModel):
    days: list[DailyCostItem]
```

### 前端

新建 `ApiCosts.vue` 页面，从 Dashboard 的成本卡片跳转。展示：
- 今日/本月两个 Tab 切换汇总
- 30 天趋势列表（日期、各服务费用、总计）
- estimated_cost 标注 "估算值"

## US-044: Dashboard 日志展示

### API 设计（来自 architecture.md）

**`GET /api/dashboard/logs?level=INFO&limit=100`**

响应：
```json
{
  "logs": [{"timestamp": "...", "level": "INFO", "message": "...", "module": "...", "request_id": "..."}]
}
```

实现：读取 `data/logs/app.log`（当前主日志文件），逐行解析 JSON，按 level 过滤，返回最新 N 条（倒序读取）。

- level 过滤：传入 INFO → 返回 INFO/WARNING/ERROR/CRITICAL
- 默认 limit=100，上限 500
- 文件不存在返回空 `[]`

### Schema 新增

```python
class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    module: str
    request_id: str | None = None
    exception: str | None = None

class LogsResponse(BaseModel):
    logs: list[LogEntry]
```

### 前端

新建 `Logs.vue` 页面：
- 顶部 level 过滤下拉（ALL/INFO/WARNING/ERROR）
- 代码风格字体展示日志列表
- ERROR 红色高亮
- 可滚动列表
- 从 Dashboard 或 Settings 跳转

## 实施步骤

### 1. Schema 定义
新增 `ApiCostsResponse`、`DailyCostItem`、`DailyCostsResponse`、`LogEntry`、`LogsResponse` 到 `app/schemas/dashboard_types.py`

### 2. 后端路由（dashboard.py）
- `GET /api/dashboard/api-costs` → `get_api_costs()`
- `GET /api/dashboard/api-costs/daily` → `get_api_costs_daily()`
- `GET /api/dashboard/logs` → `get_logs(level, limit)`

### 3. 测试（TDD）
- `test_api_costs_requires_auth` — 401
- `test_api_costs_empty` — 无数据时返回 0
- `test_api_costs_with_data` — 今日+本月各有数据
- `test_api_costs_daily_empty` — 无数据返回空
- `test_api_costs_daily_with_data` — 多天多 service
- `test_logs_requires_auth` — 401
- `test_logs_empty` — 无日志文件
- `test_logs_default` — 默认 100 条 INFO+
- `test_logs_filter_error` — 只返回 ERROR+
- `test_logs_limit` — 限制条数

### 4. 前端页面
- `ApiCosts.vue` — 成本监控
- `Logs.vue` — 日志展示
- 更新 `router/index.ts` 新增 `/costs` 和 `/logs` 路由
- Dashboard.vue 添加跳转入口

### 5. 生成链路
- `make gen` 更新 TS 类型

## 验证方式

```bash
# 后端
uv run pytest tests/test_dashboard_api.py -v
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest  # 全量

# 前端
cd admin && bunx biome check .
cd admin && bunx vue-tsc --noEmit
cd admin && bun run build

# 生成物
make gen && git diff --exit-code
```
