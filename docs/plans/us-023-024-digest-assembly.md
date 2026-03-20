# US-023 + US-024 实施计划：导读摘要生成 + 草稿组装

## Context

P1 全部完成后，推文已经过 AI 两步加工（全局分析 + 逐条加工）并计算了热度分。现在需要将处理结果组装为每日草稿（daily_digest + digest_items），并生成导读摘要。这是 M3 Digest 模块的核心功能，后续 US-025（Markdown 渲染）、US-030（查看列表）等均依赖本轮产出。

---

## 实施策略

### 整体流程

```
generate_daily_digest(digest_date)
  ├─ 1. 查询当日已处理推文 + 话题 + 账号信息
  ├─ 2. 构建待创建 items 列表（排除已聚合推文）
  ├─ 3. 按 heat_score 降序排序，分配 display_order
  ├─ 4. 创建 DailyDigest 记录 (status=draft, version=1)
  ├─ 5. 创建 DigestItem 记录（逐条写入 snapshot 快照）
  ├─ 6. 生成导读摘要（取 TOP 5 items → Claude API → summary）
  ├─ 7. 更新 digest.summary + item_count
  └─ 8. 记录 api_cost_log
```

### 关键决策

1. **summary 生成时序**：先创建 digest_items，再从 TOP 5 items 生成 summary。因为 summary 输入需要 items 的 snapshot_title 和 heat_score。
2. **content_markdown 留空**：US-025 负责 Markdown 渲染，本轮不实现 render_markdown。digest.content_markdown 暂为 None。
3. **summary_generator 作为纯函数模块**：与 processor/analyzer.py 模式一致，不持有 db session。DigestService 负责调用并写库。
4. **snapshot_source_tweets 构建**：对 aggregated 话题，查询其成员推文的 handle + tweet_url，序列化为 JSON。

---

## 文件清单

### 新建文件

| 文件 | 说明 |
|------|------|
| `app/digest/summary_prompts.py` | R.1.6 导读摘要 Prompt 模板 + 默认降级文案 |
| `app/digest/summary_generator.py` | 导读摘要生成器（调用 Claude API） |
| `tests/test_summary_generator.py` | 摘要生成器单元测试 |
| `tests/test_digest_service.py` | DigestService 集成测试 |

### 修改文件

| 文件 | 修改内容 |
|------|----------|
| `app/services/digest_service.py` | 实现 DigestService 类 |
| `app/api/deps.py` | 添加 `get_digest_service` DI 工厂 |

---

## 详细设计

### Snapshot 字段映射（严格按规范）

**tweet 类型**：

| snapshot 字段 | 来源 |
|---|---|
| snapshot_title | tweet.title |
| snapshot_translation | tweet.translated_text |
| snapshot_summary | None |
| snapshot_comment | tweet.ai_comment |
| snapshot_perspectives | None |
| snapshot_heat_score | tweet.heat_score |
| snapshot_author_name | account.display_name |
| snapshot_author_handle | account.twitter_handle |
| snapshot_tweet_url | tweet.tweet_url |
| snapshot_source_tweets | None |
| snapshot_topic_type | None |
| snapshot_tweet_time | tweet.tweet_time |

**topic (aggregated) 类型**：

| snapshot 字段 | 来源 |
|---|---|
| snapshot_title | topic.title |
| snapshot_translation | None |
| snapshot_summary | topic.summary |
| snapshot_comment | topic.ai_comment |
| snapshot_perspectives | topic.perspectives (JSON 字符串) |
| snapshot_heat_score | topic.heat_score |
| snapshot_author_name | None |
| snapshot_author_handle | None |
| snapshot_tweet_url | None |
| snapshot_source_tweets | json.dumps([{handle, tweet_url}]) 从成员推文生成 |
| snapshot_topic_type | "aggregated" |
| snapshot_tweet_time | None |

**topic (thread) 类型**：

| snapshot 字段 | 来源 |
|---|---|
| snapshot_title | topic.title |
| snapshot_translation | topic.summary (Thread 中文翻译) |
| snapshot_summary | None |
| snapshot_comment | topic.ai_comment |
| snapshot_perspectives | None |
| snapshot_heat_score | topic.heat_score |
| snapshot_author_name | Thread 第一条推文 → account.display_name |
| snapshot_author_handle | Thread 第一条推文 → account.twitter_handle |
| snapshot_tweet_url | Thread 第一条推文 → tweet.tweet_url |
| snapshot_source_tweets | None |
| snapshot_topic_type | "thread" |
| snapshot_tweet_time | None |

---

## TDD 测试计划

### tests/test_summary_generator.py

1. 正常生成：mock Claude 返回合法摘要
2. Prompt 构造验证：验证 top_articles_json 序列化格式
3. Claude API 失败降级：mock 抛 ClaudeAPIError → 返回默认文案
4. 空 items 列表：返回默认文案（不调用 Claude）

### tests/test_digest_service.py

1. 标准场景 — 混合推文和话题（独立推文 + aggregated + thread）
2. tweet snapshot 正确映射
3. aggregated topic snapshot 正确映射（含 source_tweets）
4. thread topic snapshot 正确映射（作者 = Thread 发起者）
5. 导读摘要生成 + api_cost_log 记录
6. 边界条件 — 0 条推文（空草稿）
7. 边界条件 — 全部聚合（只有 topic items）
8. item_count 正确性

---

## 实施顺序（TDD）

1. 写 `app/digest/summary_prompts.py`
2. 写 `tests/test_summary_generator.py` 失败测试
3. 实现 `app/digest/summary_generator.py` → 测试通过
4. 写 `tests/test_digest_service.py` 失败测试
5. 实现 `app/services/digest_service.py` → 测试通过
6. 更新 `app/api/deps.py` 添加 DI 工厂
7. 全量质量门禁验证

---

## 不做的事项

- Markdown 渲染 → US-025
- API 路由 → US-030
- 编辑功能 → US-031/032/033/034
- Regenerate → US-035

---

## 执行结果

### 交付物清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/digest/summary_prompts.py` | 新建 | R.1.6 导读摘要 Prompt 模板 + DEFAULT_SUMMARY 降级文案 |
| `app/digest/summary_generator.py` | 新建 | generate_summary() 异步函数，调用 Claude API，失败降级 |
| `app/services/digest_service.py` | 重写 | DigestService 类，完整草稿组装流程 |
| `app/api/deps.py` | 修改 | 新增 get_digest_service DI 工厂 |
| `tests/test_summary_generator.py` | 新建 | 4 个测试（正常/格式/降级/空列表） |
| `tests/test_digest_service.py` | 新建 | 8 个测试（混合场景 + snapshot 映射 + 边界条件） |
| `docs/spec/user-stories.md` | 修改 | US-023/024 状态更新为 ✅ |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 无 | - | - | 完全按计划执行，无偏离 |

### 问题与修复

| 问题 | 修复方式 |
|------|----------|
| SQLite 读回 datetime 丢失 tzinfo（经典问题） | 测试断言使用 `.replace(tzinfo=None)` 比较 |
| pyright: snapshot_tweet_time 可能为 None | 添加 `assert is not None` 前置检查 |
| pyright: snapshot_source_tweets 可能为 None | 添加 `assert is not None` 前置检查 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format --check | ✅ 105 files already formatted |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 279 passed（含 12 个新增） |
| pre-commit hook | ✅ 通过 |

### PR 链接

https://github.com/neuer/zhixi/pull/13
