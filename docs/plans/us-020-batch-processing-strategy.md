# US-020 分批处理策略 实施计划

> **分支**: `us-020-batch-processing-strategy`
> **日期**: 2026-03-20

## Context

P1 阶段最后一个 US。当前全局分析一次性传入所有推文，推文量大时可能超出 Claude API 上下文限制。需要增加 token 估算和分批策略，超限时按 author_weight 降序分批，多批结果合并后做轻量 AI 去重。

## 验收标准

- 估算 token 数（中文 1.5 字/token，英文 4 字符/token）
- 单批上限 100K input tokens
- 超限按 author_weight 降序分批
- 多批合并后做轻量 AI 去重（R.1.5b Prompt）
- 单批不触发去重

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/processor/token_estimator.py` | 新建 | Token 估算纯函数 |
| `app/processor/batch_strategy.py` | 新建 | 分批策略 |
| `app/processor/merger_prompts.py` | 重写空壳 | R.1.5b 去重 Prompt + Schema |
| `app/processor/batch_merger.py` | 重写空壳 | 多批合并 + AI 去重 |
| `app/services/process_service.py` | 修改 | `_run_analysis_with_retry()` 整合分批 |
| `tests/test_token_estimator.py` | 新建 | Token 估算测试 |
| `tests/test_batch_strategy.py` | 新建 | 分批策略测试 |
| `tests/test_batch_merger.py` | 新建 | 合并 + 去重测试 |
| `tests/test_process_service.py` | 修改 | 新增分批集成测试 |
| `tests/fixtures/merger/dedup_response.json` | 新建 | 去重 Mock 响应 |

## 实施方案

### 1. token_estimator.py — Token 估算

纯函数，三个函数：

- `estimate_tokens_for_text(text)` — CJK 字符 ×1/1.5，其他 ×1/4，向上取整
- `estimate_tokens_for_tweet(serialized_tweet)` — dict → JSON → text 估算
- `estimate_total_tokens(serialized_tweets)` — 列表 JSON + Prompt 模板开销

### 2. batch_strategy.py — 分批策略

按 author_weight 降序 + tweet_time 降序排序，逐条累加 token，超限切分。

### 3. merger_prompts.py — R.1.5b Prompt + Schema

照搬 spec R.1.5b 模板，Schema 复用 `GLOBAL_ANALYSIS_SCHEMA`。

### 4. batch_merger.py — 合并 + 去重

`merge_analysis_results()` 合并 filtered_ids 并集 + topics 拼接带 batch 标记。
`run_dedup_analysis()` 调用 Claude 执行去重。

### 5. process_service.py — 核心改造

提取 `_run_single_analysis()` 辅助方法，`_run_analysis_with_retry()` 整合分批逻辑。单批走原路径，多批逐批分析后合并去重。

## TDD 实施顺序

1. test_token_estimator.py → token_estimator.py
2. test_batch_strategy.py → batch_strategy.py
3. merger_prompts.py
4. test_batch_merger.py → batch_merger.py
5. test_process_service.py 新增 → process_service.py 改造
6. 全量门禁

---

## 执行结果

### 交付物清单

| 文件 | 说明 |
|------|------|
| `app/processor/token_estimator.py` | Token 估算纯函数（3 个公开函数） |
| `app/processor/batch_strategy.py` | `split_into_batches()` 分批策略 |
| `app/processor/merger_prompts.py` | `DEDUP_PROMPT` + `DEDUP_SCHEMA` |
| `app/processor/batch_merger.py` | `merge_analysis_results()` + `run_dedup_analysis()` |
| `app/services/process_service.py` | 改造 `_run_analysis_with_retry()`，新增 `_run_single_analysis()` + `_run_dedup_with_retry()` |
| `tests/test_token_estimator.py` | 12 个测试用例 |
| `tests/test_batch_strategy.py` | 8 个测试用例 |
| `tests/test_batch_merger.py` | 8 个测试用例 |
| `tests/test_process_service.py` | 新增 3 个分批集成测试（TestBatchProcessing 类） |

### 偏离项

| 项目 | 计划 | 实际 | 原因 |
|------|------|------|------|
| `tests/fixtures/merger/dedup_response.json` | 新建 | 未创建 | 改用内联 JSON 构造 mock 数据，更直观 |
| 测试中 ORM 对象构造 | `__new__` + 手动赋值 | 正常构造函数 | SQLAlchemy instrumentation 不兼容 `__new__` |

### 问题与修复

1. **SQLAlchemy `__new__` 构造失败**：`batch_strategy` 纯函数测试中用 `__new__` 构造 ORM 对象，instrumented attributes 未初始化导致 AttributeError。改用正常构造函数解决。
2. **pyright `dict[str, object]` 索引访问**：`merge_analysis_results` 返回 `dict[str, object]`，测试中直接用 `merged["topics"]` 会被 pyright 标记为 `object` 不可索引。用 `_get_topics()` 和 `_get_filtered_ids()` 辅助函数加 `isinstance` 断言做类型窄化。
3. **`dict[str, str]` 不可赋给 `dict[str, object]`**：pyright 对 dict value type 的不变性检查。测试中显式注解 `dict[str, object]` 解决。

### 质量门禁

| 检查项 | 结果 |
|--------|------|
| `pytest` | 231 passed |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 100 files already formatted |
| `pyright` | 0 errors, 0 warnings |

### PR 链接

https://github.com/neuer/zhixi/pull/10
