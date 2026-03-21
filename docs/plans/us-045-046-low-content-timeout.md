# US-045 + US-046 实施计划：冷门日处理 + 超时未审核处理

## Context

P4 阶段，US-045（冷门日处理，必须）和 US-046（超时未审核处理，必须）。两个 US 改动量小，大部分行为已由现有代码满足。

## 现状分析

| 验收标准 | 现状 | 需改动 |
|---|---|---|
| US-045: 低于 min_articles 仍生成草稿 | `generate_daily_digest()` 不检查 min_articles | 已满足 |
| US-045: 0条推文 → 默认导读"今日 AI 领域较为平静" | DEFAULT_SUMMARY = "今日 AI 热点已为您整理完毕..." | **需改** |
| US-045: Dashboard 黄色提示"今日资讯较少（N条）" | DigestStatus 无 low_content_warning 字段 | **需改** |
| US-045: 今日内容页黄色提示 | TodayResponse 已有 low_content_warning；Digest.vue 是占位符 | **需实现前端** |
| US-046: 不设自动发布定时器 | 无自动发布逻辑 | 已满足 |
| US-046: 草稿保持 draft | mark-published 是唯一状态变更路径 | 已满足 |
| US-046: Dashboard 显示"待审核" | statusMap draft → "草稿" | **需改文案** |
| US-046: push_time 纯展示 | 仅 system_config 存储，无触发逻辑 | 已满足 |

## 变更清单

### C1: 区分两种 fallback 导读文案
- **`app/digest/summary_prompts.py`**: 新增 `EMPTY_DAY_SUMMARY = "今日 AI 领域较为平静"`
- **`app/digest/summary_generator.py`**: import EMPTY_DAY_SUMMARY，空 items 时返回它；Claude 失败仍返回 DEFAULT_SUMMARY

### C2: Dashboard DigestStatus 增加 low_content_warning
- **`app/schemas/dashboard_types.py`**: DigestStatus 新增 `low_content_warning: bool = False`
- **`app/api/dashboard.py`**: _get_digest_status 计算 `digest.item_count < min_articles`

### C3: Dashboard.vue 黄色低内容提示
- **`admin/src/views/Dashboard.vue`**: 在"今日状态"卡片后插入 `van-notice-bar` 黄色提示

### C4: Dashboard.vue draft 文案改为 "待审核"
- **`admin/src/views/Dashboard.vue`**: `draft: { text: "待审核" }`

### C5: Digest.vue 今日内容页
- **`admin/src/views/Digest.vue`**: 实现基本页面 — GET /api/digest/today + items 列表 + low_content_warning

## 测试策略

### T1: 修改 `tests/test_summary_generator.py`
- `test_generate_summary_empty_items`: 断言改为 EMPTY_DAY_SUMMARY

### T2: 修改 `tests/test_digest_service.py`
- `test_empty_digest_no_processed_tweets`: digest.summary 断言改为 EMPTY_DAY_SUMMARY

### T3: 新增/修改 `tests/test_dashboard_api.py`
- `test_overview_digest_low_content_warning`: min_articles=5, item_count=3 → warning=True
- `test_overview_digest_no_warning_when_enough`: min_articles=1, item_count=8 → warning=False
- `test_overview_draft_status_pending_review`: draft 状态正确返回
- 修改 `test_overview_empty`: 追加 low_content_warning=False 断言

## 实施顺序

1. 后端测试（红灯）: T1 + T2 + T3
2. 运行 pytest 确认失败
3. 后端实现: C1 + C2
4. 运行 pytest 确认通过
5. 质量门禁: ruff + pyright
6. make gen: 更新 OpenAPI client
7. 前端实现: C3 + C4 + C5
8. 前端门禁: biome check + vue-tsc

## 文件变更清单

| 文件 | 变更类型 | 说明 |
|---|---|---|
| `app/digest/summary_prompts.py` | 修改 | 新增 EMPTY_DAY_SUMMARY 常量 |
| `app/digest/summary_generator.py` | 修改 | 空 items 分支改用 EMPTY_DAY_SUMMARY |
| `app/schemas/dashboard_types.py` | 修改 | DigestStatus 增加 low_content_warning |
| `app/api/dashboard.py` | 修改 | _get_digest_status 计算 low_content_warning |
| `admin/src/views/Dashboard.vue` | 修改 | draft 改"待审核" + 低内容黄色提示 |
| `admin/src/views/Digest.vue` | 修改 | 实现今日内容页含 low_content_warning |
| `tests/test_summary_generator.py` | 修改 | 空 items 断言改为 EMPTY_DAY_SUMMARY |
| `tests/test_digest_service.py` | 修改 | 空草稿断言改为 EMPTY_DAY_SUMMARY |
| `tests/test_dashboard_api.py` | 修改 | 新增 low_content_warning + draft 行为测试 |
| `packages/openapi-client/src/gen/types.gen.ts` | 自动生成 | make gen 后自动更新 |
