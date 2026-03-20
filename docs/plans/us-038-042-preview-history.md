# US-038 + US-042 实施计划：预览功能 + 推送历史页

## Context

P3 阶段进行中，核心编辑→发布闭环已完成（US-035/036）。本轮实现两个展示类功能：
- **US-038**：管理员预览当日草稿的只读渲染页面
- **US-042**：推送历史列表 + 详情页，供管理员回顾往期日报

两者均为"后端 API + 前端页面"组合，互不依赖。

---

## US-038：预览功能（登录态）

### 后端

**新增 API**：`GET /api/digest/preview`（JWT 保护）

- 文件：`app/api/digest.py`（追加路由）
- 查询当日 `is_current=true` 的 digest + items（复用 get_today_digest 的查询逻辑）
- 返回 `PreviewResponse`（digest + items + content_markdown）
- 无 current digest 时返回 404

**新增 Schema**：`app/schemas/digest_types.py`

```python
class PreviewResponse(BaseModel):
    digest: DigestBriefResponse
    items: list[DigestItemResponse]
    content_markdown: str
```

### 前端

**Preview.vue**（`admin/src/views/Preview.vue`）：
- 路由 `/preview` 已在白名单，无需 JWT 守卫
- onMounted 时检查 localStorage JWT：
  - 有 JWT → 调用 `GET /api/digest/preview`（JWT header）→ 渲染 ArticlePreview
  - 无 JWT → 显示"请先登录后访问预览"提示
- 后续 US-009 会增加 token 参数分支

**ArticlePreview.vue**（`admin/src/components/ArticlePreview.vue`）：
- 可复用的只读文章渲染组件
- Props：`digest: DigestBriefResponse`, `items: DigestItemResponse[]`
- 清新简约风：白底、`#f5f5f5` 背景、圆角卡片、淡色分割线
- 渲染结构：日期标题 → 导读摘要 → 条目列表（跳过 excluded）→ 底部固定文案
- 条目卡片区分 tweet / topic（aggregated/thread）
- 不显示任何操作按钮

---

## US-042：推送历史页

### 后端

**文件**：`app/api/history.py`（填充空壳 router）

**API 1**：`GET /api/history?page=1&page_size=20`（JWT 保护）

- 每日期只返回一条，版本选择优先级：
  1. `status='published'`
  2. `is_current=true`
  3. `version` 最大
- SQL：使用 `ROW_NUMBER() OVER (PARTITION BY digest_date ORDER BY ...)` 窗口函数
- 返回分页响应

```python
class HistoryListItem(BaseModel):
    id: int
    digest_date: date
    version: int
    status: str
    summary: str | None
    item_count: int
    published_at: datetime | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class HistoryListResponse(BaseModel):
    items: list[HistoryListItem]
    total: int
    page: int
    page_size: int
```

**API 2**：`GET /api/history/{id}`（JWT 保护）

- 查询 DailyDigest by id + 关联 digest_items（按 display_order 排序）
- 返回 `HistoryDetailResponse`

```python
class HistoryDetailResponse(BaseModel):
    digest: DigestBriefResponse
    items: list[DigestItemResponse]
```

### 前端

**History.vue**（`admin/src/views/History.vue`）：
- 导航栏 + 下拉刷新 + 列表
- 每条记录：日期、版本号、状态 Badge（van-tag）、条目数
- 点击跳转 `/history/:id`
- 滚动到底部加载更多（van-list 组件）

**HistoryDetail.vue**（`admin/src/views/HistoryDetail.vue`）：
- 导航栏（返回按钮）
- 复用 ArticlePreview 组件渲染内容（只读模式）
- 调用 `GET /api/history/{id}` 获取数据

---

## 文件变更清单

### 新建
| 文件 | 说明 |
|------|------|
| `tests/test_preview_api.py` | US-038 预览 API 测试 |
| `tests/test_history_api.py` | US-042 历史 API 测试 |
| `admin/src/components/ArticlePreview.vue` | 只读文章渲染组件（共享） |

### 修改
| 文件 | 说明 |
|------|------|
| `app/api/digest.py` | 新增 `GET /preview` 路由 |
| `app/api/history.py` | 填充 `GET /` 和 `GET /{id}` 路由 |
| `app/schemas/digest_types.py` | 新增 PreviewResponse / HistoryListItem / HistoryListResponse / HistoryDetailResponse |
| `admin/src/views/Preview.vue` | 实现预览页面 |
| `admin/src/views/History.vue` | 实现历史列表页 |
| `admin/src/views/HistoryDetail.vue` | 实现历史详情页 |

---

## 实施顺序（TDD）

### 第 1 步：后端 Schema 定义
- 在 `app/schemas/digest_types.py` 添加 4 个新 Schema

### 第 2 步：US-038 后端（测试 → 实现）
1. 写 `tests/test_preview_api.py`（红灯）
2. 在 `app/api/digest.py` 添加 `GET /preview` 路由
3. 测试通过（绿灯）

### 第 3 步：US-042 后端（测试 → 实现）
1. 写 `tests/test_history_api.py`（红灯）
2. 填充 `app/api/history.py`（两个端点）
3. 测试通过（绿灯）

### 第 4 步：运行 `make gen` 重新生成前端类型

### 第 5 步：前端组件实现
1. 创建 `ArticlePreview.vue` 共享组件
2. 实现 `Preview.vue` 页面
3. 实现 `History.vue` 列表页
4. 实现 `HistoryDetail.vue` 详情页

### 第 6 步：全量门禁
```bash
uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pyright && uv run pytest
cd admin && bunx biome check . && bunx vue-tsc --noEmit
```

---

## 测试要点

### test_preview_api.py
- `test_preview_returns_digest_with_items` — 有 current digest 时返回完整数据
- `test_preview_no_digest_returns_404` — 无 current digest 时 404
- `test_preview_requires_auth` — 无 JWT 返回 401
- `test_preview_excludes_excluded_items` — is_excluded=true 的条目不在响应中（或仍在但前端过滤）

### test_history_api.py
- `test_history_list_returns_paginated` — 返回分页列表
- `test_history_list_one_per_date` — 每日期只一条
- `test_history_version_priority_published` — published 版本优先
- `test_history_version_priority_current` — 无 published 时 is_current 优先
- `test_history_version_priority_max_version` — 都不满足时取 max version
- `test_history_detail_returns_items` — 返回完整 digest + items
- `test_history_detail_not_found` — id 不存在返回 404
- `test_history_requires_auth` — 无 JWT 返回 401

---

## 关键设计决策

1. **PreviewResponse vs TodayResponse**：Preview 不含 `low_content_warning`，增加 `content_markdown` 字段，语义更清晰
2. **Preview 路由在 digest.py**：属于 digest 管理域，不单独建文件
3. **History 窗口函数**：SQLite 支持 ROW_NUMBER()，避免 N+1 查询
4. **ArticlePreview 组件复用**：Preview.vue 和 HistoryDetail.vue 共用，减少重复
5. **Preview.vue 白名单处理**：/preview 在路由白名单中（为 US-009 预留），US-038 通过检查 localStorage JWT 实现登录态访问

---

## 执行结果

### 交付物清单
| 文件 | 操作 | 行数 |
|------|------|------|
| `app/schemas/digest_types.py` | 修改 | +45 |
| `app/api/digest.py` | 修改 | +35 |
| `app/api/history.py` | 重写 | +105 |
| `tests/test_preview_api.py` | 新建 | +152 |
| `tests/test_history_api.py` | 新建 | +245 |
| `admin/src/components/ArticlePreview.vue` | 新建 | +275 |
| `admin/src/views/Preview.vue` | 重写 | +92 |
| `admin/src/views/History.vue` | 重写 | +117 |
| `admin/src/views/HistoryDetail.vue` | 重写 | +70 |
| `packages/openapi-client/src/gen/types.gen.ts` | 重生成 | 自动 |
| `docs/spec/user-stories.md` | 修改 | +2 |

### 偏离项
| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | 仅修改本轮文件 | 额外修复 Settings.vue TS 错误 | biome 之前把 dayOptions/timeColumns 重命名为 _dayOptions/_timeColumns，模板引用断裂导致 vue-tsc 报错，需恢复原名才能通过 build |

### 问题与修复
| 问题 | 解决 |
|------|------|
| biome 误删 Vue 组件 import | biome 不识别 Vue template 中的组件引用，`--fix` 会移除。手动恢复 import 后不再用 `--fix --unsafe` 处理这些 |
| Settings.vue 预存 TS 错误 | biome 在之前轮次把变量名加了 `_` 前缀，但模板仍引用原名。恢复为不带下划线的变量名 |

### 质量门禁
| 门禁 | 结果 |
|------|------|
| ruff check | ✅ 通过 |
| ruff format | ✅ 通过 |
| lint-imports | ✅ 4 kept, 0 broken |
| pyright | ✅ 0 errors |
| pytest | ✅ 460 passed（+12 新测试） |
| biome check | ✅ 0 errors（warnings 为 Vue template 引用误报） |
| vue-tsc | ✅ 0 errors |
| bun run build | ✅ 通过 |

### PR 链接
https://github.com/neuer/zhixi/pull/22
