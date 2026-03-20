# US-019 + US-021 实施计划：全局分析 + 逐条/逐话题 AI 加工

## Context

P1 并行组 A（US-017/018/022）已完成。本轮实现并行组 B：
- **US-019**: 全局分析（第一步 AI）— 过滤无关推文、识别 Thread、聚合话题、评估 AI 重要性分
- **US-021**: 逐条/逐话题 AI 加工（第二步 AI）— 为每条推文/话题生成标题、翻译、点评

## 实施策略

### 分层结构
1. **Prompt 层**: analyzer_prompts.py / translator_prompts.py — 模板 + Schema + 序列化
2. **处理器层**: analyzer.py / translator.py — 调用 Claude + JSON 校验
3. **编排层**: process_service.py — 全流程编排（分析→过滤→Topic→加工→热度）

### TDD 流程
每层先写测试 → 再实现 → 测试通过后进入下一层

### 关键决策
1. `TopicResult.type` 使用 `Literal["aggregated", "thread", "single"]` 替代 `TopicType` 枚举
2. Thread `merged_text` 仅在内存保持（`dict[int, str]`），不入 DB
3. SQLite naive datetime 需 `_ensure_utc()` 处理
4. 空 topics fallback：未被任何 topic 覆盖的非 filtered 推文作为 single 处理

---

## 执行结果回填

### 交付物清单

| 文件 | 变更类型 | 说明 |
|------|----------|------|
| `app/processor/analyzer_prompts.py` | 重写 | R.1.2 Prompt + Schema + 序列化函数 |
| `app/processor/analyzer.py` | 重写 | `run_global_analysis()` 全局分析 |
| `app/processor/translator_prompts.py` | 重写 | R.1.3/R.1.4/R.1.5 三套 Prompt + Schema |
| `app/processor/translator.py` | 重写 | 三种加工函数 |
| `app/services/process_service.py` | 重写 | ProcessService 完整编排 |
| `app/schemas/processor_types.py` | 修改 | TopicResult.type → Literal |
| `app/api/deps.py` | 修改 | 添加 get_process_service |
| `app/processor/__init__.py` | 修改 | 导出公共 API |
| `tests/test_analyzer.py` | 新增 | 13 个测试用例 |
| `tests/test_translator.py` | 新增 | 9 个测试用例 |
| `tests/test_process_service.py` | 新增 | 16 个集成测试 |
| `tests/fixtures/analyzer/*.json` | 新增 | Mock 分析响应 |
| `tests/fixtures/translator/*.json` | 新增 | Mock 加工响应（3 个） |

### 偏离项

| 计划 | 实际 | 原因 |
|------|------|------|
| 无 | 添加 `_ensure_utc()` | SQLite 读回 datetime 丢失 tzinfo，热度计算报错 |
| TopicResult.type 用 Literal | 同计划 | — |

### 问题与修复

| 问题 | 修复 |
|------|------|
| SQLite naive datetime 与 tz-aware reference_time 相减报 TypeError | 在 `_calculate_all_heat_scores` 中添加 `_ensure_utc()` 辅助函数 |
| pyright 报 AsyncMock.call_args 不可访问 | `_mock_client` 返回类型从 `ClaudeClient` 改为 `AsyncMock` |

### 质量门禁

| 检查项 | 结果 |
|--------|------|
| `ruff check .` | ✅ All checks passed |
| `ruff format --check .` | ✅ 95 files already formatted |
| `pyright` | ✅ 0 errors, 0 warnings |
| `pytest` | ✅ 200 passed in 46.62s |

### PR 链接

https://github.com/neuer/zhixi/pull/9
