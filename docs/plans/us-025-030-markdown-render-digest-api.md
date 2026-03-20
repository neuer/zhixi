# US-025 + US-030: Markdown 渲染 + 查看今日内容列表 API

## Context

P2 阶段 US-023/024（导读摘要 + 草稿组装）已完成。`DigestService.generate_daily_digest()` 能创建 DailyDigest + DigestItem 快照，但 `content_markdown` 字段为 None，`app/digest/renderer.py` 仅为占位符，`app/api/digest.py` 路由为空。

本轮实现两个互不依赖的 US：
- **US-025**：Markdown 渲染纯函数 + 集成到 DigestService
- **US-030**：`GET /api/digest/today` API 端点
- **US-052**：Markdown 渲染测试（通过 TDD 在 US-025 中覆盖）

---

## US-025: Markdown 渲染

### 核心逻辑

纯函数 `render_markdown(digest, items, top_n) -> str`，完全基于 snapshot 字段渲染，不回查源表。

### 渲染规则（来自 prompts.md R.2）

1. **标题行**：`# 🔥 智曦 · {M}月{D}日`
2. **导读摘要**：digest.summary
3. **热度榜**：列出前 top_n 条有效（非 excluded）条目的标题和热度分
4. **详细资讯**：按 display_order 渲染每条
   - **aggregated topic**：综合摘要 + 各方观点 + AI 点评 + 来源推文链接
   - **tweet**：作者 + 翻译 + AI 点评 + 原文链接
   - **thread topic**：同 tweet 模板（翻译 = Thread 完整翻译，作者 = 发起者）
5. **底部固定文案**：`> 智曦 - 每天一束AI之光\n> 👆 点击关注，不错过每一条重要资讯`

### 过滤与排序

- 先过滤 `is_excluded=True`
- 置顶（`is_pinned=True`）按 display_order 在最前
- 再取前 `top_n` 条渲染
- top_n 指最终渲染出的有效条目数

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/digest/renderer.py` | **改写** | 实现 `render_markdown()` 纯函数 |
| `app/services/digest_service.py` | **修改** | `generate_daily_digest()` 末尾调用 render_markdown 写入 content_markdown |
| `tests/test_markdown_renderer.py` | **新建** | 渲染器纯函数单元测试（US-052 覆盖） |
| `tests/test_digest_service.py` | **修改** | 验证 content_markdown 被正确写入 |

### renderer.py 设计

```python
# app/digest/renderer.py
"""Markdown 渲染器 — 从 digest_items 快照生成最终 Markdown。"""

def render_markdown(digest: DailyDigest, items: list[DigestItem], top_n: int = 10) -> str:
    """渲染 Markdown 内容。

    参数:
        digest: 日报对象（取 digest_date, summary）
        items: DigestItem 列表（已含 snapshot 字段）
        top_n: 最终渲染条目数上限
    """
    # 1. 过滤 excluded
    # 2. 按 display_order 排序（pinned 在前）
    # 3. 取前 top_n 条
    # 4. 生成标题 + 导读 + 热度榜 + 详细资讯 + 底部
```

内部辅助函数：
- `_render_header(digest_date) -> str` — 标题行
- `_render_summary(summary) -> str` — 导读摘要
- `_render_ranking(items) -> str` — 热度榜
- `_render_detail_item(item, rank) -> str` — 单条详细资讯（分发到 aggregated/tweet/thread）
- `_render_aggregated(item, rank) -> str` — 聚合话题模板
- `_render_single(item, rank) -> str` — 单条推文/Thread 模板
- `_render_footer() -> str` — 底部固定文案

### DigestService 集成

在 `generate_daily_digest()` 的步骤 8（摘要生成）之后，增加步骤 9：

```python
# 9. 渲染 Markdown
top_n = int(await get_system_config(self._db, "top_n", "10"))
digest.content_markdown = render_markdown(digest, created_items, top_n)
```

需要 import `get_system_config` 和 `render_markdown`。

---

## US-030: 查看今日内容列表 API

### API 契约

```
GET /api/digest/today
Authorization: Bearer {JWT}

成功 200:
{
  "digest": {
    "id": 1,
    "digest_date": "2026-03-20",
    "version": 1,
    "status": "draft",
    "summary": "...",
    "item_count": 8,
    "content_markdown": "...",
    "created_at": "..."
  },
  "items": [
    {
      "id": 1,
      "item_type": "tweet",
      "item_ref_id": 42,
      "display_order": 1,
      "is_pinned": false,
      "is_excluded": false,
      "snapshot_title": "...",
      "snapshot_translation": "...",
      "snapshot_comment": "...",
      "snapshot_heat_score": 85.5,
      "snapshot_author_name": "...",
      "snapshot_author_handle": "...",
      "snapshot_tweet_url": "...",
      "snapshot_source_tweets": null,
      "snapshot_topic_type": null,
      "snapshot_summary": null,
      "snapshot_perspectives": null,
      "snapshot_tweet_time": "..."
    }
  ],
  "low_content_warning": false
}

无数据:
{
  "digest": null,
  "items": [],
  "low_content_warning": false
}
```

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/schemas/digest_types.py` | **修改** | 添加 DigestResponse/DigestItemResponse/TodayResponse |
| `app/api/digest.py` | **改写** | 实现 `GET /today` 端点 |
| `tests/test_digest_api.py` | **新建** | API 集成测试 |

### Schema 设计

```python
# app/schemas/digest_types.py 新增

class DigestItemResponse(BaseModel):
    id: int
    item_type: str
    item_ref_id: int
    display_order: int
    is_pinned: bool
    is_excluded: bool
    snapshot_title: str | None
    snapshot_translation: str | None
    snapshot_summary: str | None
    snapshot_comment: str | None
    snapshot_perspectives: str | None  # JSON string
    snapshot_heat_score: float
    snapshot_author_name: str | None
    snapshot_author_handle: str | None
    snapshot_tweet_url: str | None
    snapshot_source_tweets: str | None  # JSON string
    snapshot_topic_type: str | None
    snapshot_tweet_time: datetime | None
    model_config = ConfigDict(from_attributes=True)

class DigestBriefResponse(BaseModel):
    id: int
    digest_date: date
    version: int
    status: str
    summary: str | None
    item_count: int
    content_markdown: str | None
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)

class TodayResponse(BaseModel):
    digest: DigestBriefResponse | None
    items: list[DigestItemResponse]
    low_content_warning: bool
```

### 路由实现

```python
# app/api/digest.py

@router.get("/today", response_model=TodayResponse)
async def get_today_digest(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> TodayResponse:
    # 1. digest_date = get_today_digest_date()
    # 2. 查询 daily_digest WHERE digest_date=today AND is_current=true
    # 3. 无数据 → {"digest": null, "items": [], "low_content_warning": false}
    # 4. 查询 digest_items WHERE digest_id=digest.id ORDER BY display_order
    # 5. 读取 min_articles 配置
    # 6. low_content_warning = item_count < min_articles
```

路由直接查询 DB（简单读取，不需要 Service 层编排）。

---

## TDD 实施顺序

### 第一步：US-025 Markdown 渲染测试 → 实现

1. **写 `tests/test_markdown_renderer.py`**（先写失败测试）
   - `test_render_basic_tweet` — 单条推文渲染包含标题、翻译、点评、原文链接
   - `test_render_aggregated_topic` — 聚合话题包含摘要、各方观点、来源链接
   - `test_render_thread_topic` — Thread 使用单条模板，翻译为 Thread 翻译
   - `test_excluded_items_skipped` — excluded 条目不在输出中
   - `test_top_n_limit` — 超过 top_n 的条目不渲染
   - `test_pinned_items_first` — 置顶条目排在最前
   - `test_header_and_footer` — 标题含日期，底部含固定文案
   - `test_heat_ranking` — 热度榜列出标题和分数
   - `test_empty_items` — 空列表渲染仅有标题和底部
   - `test_mixed_content` — 混合内容（tweet + aggregated + thread）完整渲染

2. **实现 `app/digest/renderer.py`**

3. **更新 `app/services/digest_service.py`** — 集成 render_markdown
4. **更新 `tests/test_digest_service.py`** — 验证 content_markdown 非空

### 第二步：US-030 API 测试 → 实现

5. **写 `tests/test_digest_api.py`**（先写失败测试）
   - `test_today_with_data` — 有草稿时返回 digest + items + low_content_warning
   - `test_today_no_data` — 无草稿时返回 null digest
   - `test_today_items_sorted_by_display_order` — items 按 display_order 排序
   - `test_today_low_content_warning` — item_count < min_articles 时 warning=true
   - `test_today_requires_auth` — 无 JWT 返回 401

6. **修改 `app/schemas/digest_types.py`** — 添加响应类型
7. **实现 `app/api/digest.py`** — `GET /today` 端点

### 第三步：质量门禁

8. `ruff check .` + `ruff format --check .`
9. `pyright`
10. `pytest`

---

## 关键文件路径

| 文件 | 作用 |
|------|------|
| `app/digest/renderer.py` | Markdown 渲染纯函数（主要新增） |
| `app/services/digest_service.py` | 集成 render_markdown（修改 ~5 行） |
| `app/api/digest.py` | GET /today 端点（改写） |
| `app/schemas/digest_types.py` | 响应 Schema（修改） |
| `app/api/deps.py` | 无需修改，get_digest_service 已存在 |
| `app/config.py` | 复用 get_today_digest_date + get_system_config |
| `tests/test_markdown_renderer.py` | 渲染器测试（新建） |
| `tests/test_digest_api.py` | API 测试（新建） |
| `tests/test_digest_service.py` | 集成测试更新 |
| `tests/conftest.py` | 复用 authed_client, seeded_db 等 fixture |

## 复用的已有函数/模式

- `get_today_digest_date()` @ `app/config.py:40`
- `get_system_config()` @ `app/config.py:57`
- `get_current_admin()` @ `app/api/deps.py:15` — JWT 认证
- `authed_client` / `seeded_db` fixture @ `tests/conftest.py`
- `DigestService._create_*_item()` 已正确填充所有 snapshot 字段
- `DailyDigest` / `DigestItem` 模型 @ `app/models/digest.py`, `app/models/digest_item.py`

## 验证方式

```bash
# 1. 单元测试
pytest tests/test_markdown_renderer.py -v

# 2. API 集成测试
pytest tests/test_digest_api.py -v

# 3. 全量测试
pytest

# 4. 质量门禁
ruff check . && ruff format --check . && pyright
```

---

## 执行结果

### 交付物清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `app/digest/renderer.py` | 改写 | ~160 行 |
| `app/api/digest.py` | 改写 | ~60 行 |
| `app/schemas/digest_types.py` | 修改 | +55 行 |
| `app/services/digest_service.py` | 修改 | +5 行 |
| `tests/test_markdown_renderer.py` | 新建 | ~370 行，20 个测试 |
| `tests/test_digest_api.py` | 新建 | ~170 行，5 个测试 |
| `tests/test_digest_service.py` | 修改 | +4 行 |
| `docs/spec/user-stories.md` | 修改 | US-025/030/052 → ✅ |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 无 | — | — | 完全按计划执行 |

### 问题与修复

| 问题 | 解决 |
|------|------|
| `round(85.5)` = 86（Python 银行家舍入） | 修正测试断言为 85.0 → 🔥85 |
| ruff E741 变量名 `l` 不规范 | 改为 `line` |
| ruff I001 import 排序 | `ruff check --fix` 自动修复 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 107 files already formatted |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 304 passed |

### PR 链接

https://github.com/neuer/zhixi/pull/14
