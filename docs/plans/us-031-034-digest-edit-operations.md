# US-031 + US-032 + US-033 + US-034: 日报编辑操作 API

## Context

P2 阶段 US-025/030 已完成 Markdown 渲染和 `GET /api/digest/today` 查询 API。管理员可以查看今日草稿，但无法编辑内容、调整排序、剔除/恢复条目。

本轮实现四个编辑操作 API（纯后端，前端在 US-039 后实现）：
- **US-031**：编辑单条内容（修改 snapshot 字段）
- **US-032**：编辑导读摘要
- **US-033**：调整排序与置顶
- **US-034**：剔除与恢复条目

四个 US 共享：权限检查 → 修改数据 → 重渲染 Markdown 的模式。

---

## 共享基础设施

### 自定义异常（Service 层）

遵循 `account_service.py` 的模式（Service 定义异常 → 路由层 try-except 转 HTTPException `from None`）：

```python
# app/services/digest_service.py 新增
class DigestNotFoundError(Exception):
    """当日无 is_current=true 的草稿。"""

class DigestNotEditableError(Exception):
    """草稿状态非 draft（已发布等），不可编辑。"""

class DigestItemNotFoundError(Exception):
    """指定的 digest_item 不存在。"""
```

### 共享 helper 方法（DigestService 内部）

```python
async def _get_current_draft(self, digest_date: date) -> DailyDigest:
    """获取当日 is_current=true 的草稿，校验 status=draft。"""

async def _find_item(self, digest_id: int, item_type: str, item_ref_id: int) -> DigestItem:
    """通过 (digest_id, item_type, item_ref_id) 定位 digest_item。"""

async def _rerender_markdown(self, digest: DailyDigest) -> None:
    """重新查询 items → 调用 render_markdown → 写回 content_markdown。"""
```

---

## US-031: 编辑单条内容

### API 契约

```
PUT /api/digest/item/{item_type}/{item_ref_id}
Authorization: Bearer {JWT}

请求体（所有字段可选，partial update）:
{
  "title": "...",           // → snapshot_title
  "translation": "...",     // → snapshot_translation（tweet 和 thread）
  "summary": "...",         // → snapshot_summary（aggregated topic）
  "perspectives": "...",    // → snapshot_perspectives（aggregated topic，JSON 字符串）
  "comment": "..."          // → snapshot_comment
}

成功 200: DigestItemResponse
错误 404: "今日草稿不存在" / "条目不存在"
错误 409: "当前版本不可编辑，请先重新生成新版本"
错误 401: "登录已过期，请重新登录"
```

### 实现

1. `_get_current_draft(digest_date)` → 权限检查
2. `_find_item(digest.id, item_type, item_ref_id)` → 定位条目
3. 根据请求体更新 snapshot_* 字段（仅更新传入的非 None 字段）
4. `_rerender_markdown(digest)` → 重渲染 Markdown

### 请求 Schema

```python
# app/schemas/digest_types.py 新增
class EditItemRequest(BaseModel):
    title: str | None = None
    translation: str | None = None
    summary: str | None = None
    perspectives: str | None = None  # JSON 字符串
    comment: str | None = None
```

---

## US-032: 编辑导读摘要

### API 契约

```
PUT /api/digest/summary
Authorization: Bearer {JWT}

请求体:
{"summary": "新的导读摘要文本"}

成功 200: MessageResponse {"message": "导读摘要已更新"}
错误: 同 US-031
```

### 实现

1. `_get_current_draft(digest_date)` → 权限检查
2. 更新 `digest.summary`
3. `_rerender_markdown(digest)` → 重渲染 Markdown

### 请求 Schema

```python
class EditSummaryRequest(BaseModel):
    summary: str
```

---

## US-033: 调整排序与置顶

### API 契约

```
PUT /api/digest/reorder
Authorization: Bearer {JWT}

请求体:
{
  "items": [
    {"id": 1, "display_order": 0, "is_pinned": true},
    {"id": 2, "display_order": 1, "is_pinned": false},
    ...
  ]
}

成功 200: MessageResponse {"message": "排序已更新"}
错误: 同 US-031
```

### 实现

1. `_get_current_draft(digest_date)` → 权限检查
2. 遍历 items，逐条更新 `display_order` 和 `is_pinned`
3. 校验所有 item.id 属于当前 digest
4. `_rerender_markdown(digest)` → 重渲染 Markdown

### 请求 Schema

```python
class ReorderRequest(BaseModel):
    items: list[ReorderInput]  # ReorderInput 已存在
```

---

## US-034: 剔除与恢复条目

### API 契约

```
POST /api/digest/exclude/{item_type}/{item_ref_id}
成功 200: MessageResponse {"message": "条目已剔除"}

POST /api/digest/restore/{item_type}/{item_ref_id}
成功 200: MessageResponse {"message": "条目已恢复"}
错误: 同 US-031
```

### 实现

**剔除**：
1. `_get_current_draft` → `_find_item` → `is_excluded=True`
2. `_rerender_markdown(digest)`

**恢复**：
1. `_get_current_draft` → `_find_item` → `is_excluded=False`
2. `display_order = max(非 excluded 条目的 display_order) + 1`
3. `_rerender_markdown(digest)`

---

## 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/services/digest_service.py` | 修改 | 新增 3 个异常类 + 5 个编辑方法 + 3 个 helper |
| `app/api/digest.py` | 修改 | 新增 5 个路由端点 |
| `app/schemas/digest_types.py` | 修改 | 新增 EditItemRequest, EditSummaryRequest, ReorderRequest |
| `tests/test_digest_edit_api.py` | 新建 | 编辑操作 API 集成测试 |

### 不变文件

- `app/api/deps.py` — `get_digest_service` 已存在
- `app/digest/renderer.py` — `render_markdown` 已实现
- `app/models/digest_item.py` — 模型字段已完备
- `tests/conftest.py` — `authed_client`, `auth_headers`, `db` 等 fixture 已就绪

---

## TDD 实施顺序

### 第一步：Schema 定义

新增 `EditItemRequest`, `EditSummaryRequest`, `ReorderRequest` 到 `app/schemas/digest_types.py`。

### 第二步：写测试 → `tests/test_digest_edit_api.py`

**US-031 测试**：
1. `test_edit_tweet_item` — 编辑 tweet 的 title/translation/comment → snapshot 更新 + Markdown 重渲染
2. `test_edit_aggregated_topic_item` — 编辑 aggregated topic 的 title/summary/perspectives/comment
3. `test_edit_thread_topic_item` — 编辑 thread 的 title/translation/comment
4. `test_edit_item_partial_update` — 只传 title → 其他字段不变
5. `test_edit_item_not_found_404` — 不存在的条目 → 404
6. `test_edit_item_published_409` — 已发布草稿 → 409
7. `test_edit_item_requires_auth_401` — 无 JWT → 401

**US-032 测试**：
8. `test_edit_summary` — 更新 summary + Markdown 重渲染
9. `test_edit_summary_published_409` — 已发布 → 409

**US-033 测试**：
10. `test_reorder_items` — 更新 display_order 和 is_pinned
11. `test_reorder_rerenders_markdown` — Markdown 重渲染
12. `test_reorder_invalid_item_404` — 不属于当前 digest 的 item → 404

**US-034 测试**：
13. `test_exclude_item` — is_excluded=True + Markdown 重渲染
14. `test_restore_item` — is_excluded=False, display_order=max+1
15. `test_exclude_restore_requires_auth_401` — 无 JWT → 401

### 第三步：实现 Service 方法

`app/services/digest_service.py` 新增：
- 3 个异常类
- `_get_current_draft()`, `_find_item()`, `_rerender_markdown()` helper
- `edit_item()`, `edit_summary()`, `reorder_items()`, `exclude_item()`, `restore_item()`

### 第四步：实现路由

`app/api/digest.py` 新增 5 个路由端点。

### 第五步：质量门禁

```bash
ruff check . && ruff format --check . && uv run lint-imports && pyright && pytest
```

---

## 复用的已有代码

| 函数/类 | 位置 | 用途 |
|---------|------|------|
| `render_markdown()` | `app/digest/renderer.py:14` | 重渲染 Markdown |
| `get_today_digest_date()` | `app/config.py:40` | 获取当日日期 |
| `get_system_config()` | `app/config.py:57` | 读取 top_n 配置 |
| `get_current_admin()` | `app/api/deps.py:15` | JWT 认证 |
| `get_digest_service()` | `app/api/deps.py:50` | DI 注入 |
| `DigestItemResponse` | `app/schemas/digest_types.py:22` | 编辑响应 |
| `MessageResponse` | `app/schemas/digest_types.py:16` | 通用消息 |
| `ReorderInput` | `app/schemas/digest_types.py:8` | 排序输入 |
| `authed_client` fixture | `tests/conftest.py` | 测试用 |

---

## 验证方式

```bash
# 单个测试文件
pytest tests/test_digest_edit_api.py -v

# 全量测试（确保不破坏已有功能）
pytest

# 质量门禁
ruff check . && ruff format --check . && uv run lint-imports && pyright
```

---

## 执行结果

### 交付物清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `app/services/digest_service.py` | 修改 | +150 行（3 异常类 + 3 helper + 5 编辑方法） |
| `app/api/digest.py` | 修改 | +110 行（5 个路由端点） |
| `app/schemas/digest_types.py` | 修改 | +20 行（3 个请求 Schema） |
| `tests/test_digest_edit_api.py` | 新建 | ~560 行，15 个测试 |
| `docs/plans/us-031-034-digest-edit-operations.md` | 新建 | 实施计划 |
| `docs/spec/user-stories.md` | 修改 | US-031/032/033/034 → ✅ |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 无 | — | — | 完全按计划执行 |

### 问题与修复

| 问题 | 解决 |
|------|------|
| ruff I001 import 排序 | 调整 test 文件 import 顺序 |
| ruff B007 未使用的循环变量 `idx` | 移除 `enumerate` 改为直接迭代 |
| digest_service.py 格式化 | `ruff format` 自动修复 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 108 files already formatted |
| lint-imports | ✅ 4 kept, 0 broken |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 319 passed |

### PR 链接

https://github.com/neuer/zhixi/pull/15
