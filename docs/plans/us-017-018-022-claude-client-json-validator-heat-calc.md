# US-017 + US-018 + US-022 实施计划

> P1 首批并行组：Claude API 客户端封装 + JSON 校验 + 热度分计算

## 概述

三个互不依赖的基础模块，为后续 AI 加工全流程提供基础能力。

| US | 内容 | 文件 |
|----|------|------|
| US-017 | Claude API 客户端封装 | `app/clients/claude_client.py` |
| US-018 | JSON 输出校验与修复 | `app/processor/json_validator.py` |
| US-022 | 热度分计算 | `app/processor/heat_calculator.py` |

---

## US-017: Claude API 客户端封装

### 修改文件
- `app/clients/claude_client.py` — 主实现
- `app/schemas/client_types.py` — 添加 `estimated_cost` 字段
- `tests/test_claude_client.py` — 新建测试

### 实现策略

1. **ClaudeAPIError** 自定义异常（同 `XApiError` 模式）

2. **ClaudeClient 类**：
   - 构造函数：`api_key`, `model`, `input_price`, `output_price`
   - 内部：`anthropic.AsyncAnthropic(api_key=..., timeout=60.0)`
   - `async def complete(prompt, system=None, max_tokens=4096) -> ClaudeResponse`
   - 安全声明（R.1.1）自动注入到 system 参数开头
   - 计时用 `time.monotonic()`
   - `estimated_cost` = `(input * price / 1M) + (output * price / 1M)`，6 位小数
   - 异常：`anthropic.APIError` → `ClaudeAPIError`

3. **get_claude_client()** 模块级惰性单例

### 测试要点
- 正常调用 → ClaudeResponse 各字段正确
- 安全声明注入（有/无 system 参数两种情况）
- 成本计算精度
- API 异常包装
- 超时配置

---

## US-018: JSON 输出校验与修复

### 修改文件
- `app/processor/json_validator.py` — 主实现
- `tests/test_json_validator.py` — 新建测试

### 实现策略

1. **JsonValidationError** 自定义异常，`raw_response` 属性

2. **validate_and_fix(raw_text, schema) -> dict**：
   - 第一级：`json.loads()` 直接解析
   - 第二级：清理（去 markdown 包裹 / 提取 JSON 子串 / 补括号）
   - 第三级：抛 `JsonValidationError`
   - Schema 校验：required 字段 + 类型匹配

### 测试要点（≥8 用例，满足 US-048）
1. 正常 JSON / markdown 包裹 / 缺括号 / 多余前缀 / 字段缺失 / 完全无效 / 嵌套 / 类型错误 / 空字符串 / 多余后缀

---

## US-022: 热度分计算

### 修改文件
- `app/processor/heat_calculator.py` — 主实现
- `tests/test_heat_calculator.py` — 新建测试

### 实现策略

全部纯函数，无 DB 依赖。

1. `calculate_base_score(likes, retweets, replies, author_weight, hours)` — 含 exp 衰减
2. `get_reference_time(digest_date)` — 当日北京 06:00 转 UTC
3. `calculate_hours_since_post(tweet_time, ref_time)` — 秒差/3600
4. `normalize_scores(scores)` — min-max 归一化 0-100，单条/全同=50
5. `calculate_heat_score(normalized_base, ai_importance)` — 0.7/0.3 加权

### 测试要点（满足 US-049）
- 多条正常 / 单条=50 / 全同=50 / time_decay / 聚合 AVG / 极端值 / 精度 2 位小数

---

## 实施顺序

1. US-022 热度计算（纯函数，最简单）
2. US-018 JSON 校验（纯函数+异常类）
3. US-017 Claude 客户端（外部包 mock）

每个 US：先写测试 → 实现 → 测试通过。

---

## 质量门禁

```bash
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
uv run pytest
```

---

## 执行结果

### 交付物清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/clients/claude_client.py` | 修改 | ClaudeClient 类 + ClaudeAPIError + SAFETY_PREFIX + get_claude_client() |
| `app/schemas/client_types.py` | 修改 | ClaudeResponse 添加 estimated_cost 字段 |
| `app/processor/json_validator.py` | 修改 | validate_and_fix + JsonValidationError + 三级解析 |
| `app/processor/heat_calculator.py` | 修改 | 5 个纯函数（base_score / ref_time / hours / normalize / heat_score） |
| `tests/test_claude_client.py` | 新建 | 11 测试用例 |
| `tests/test_json_validator.py` | 新建 | 21 测试用例 |
| `tests/test_heat_calculator.py` | 新建 | 22 测试用例 |
| `docs/spec/user-stories.md` | 修改 | US-017/018/022/048/049 → ✅ 已完成 |

### 偏离项

| 计划 | 实际 | 原因 |
|------|------|------|
| `response.content[0].text` 直接取值 | 添加 `isinstance(TextBlock)` 类型窄化 | pyright 严格检查 anthropic SDK union 类型 |
| Mock 用 MagicMock 模拟 content block | 用 `TextBlock(type="text", text=...)` 真实构造 | isinstance 检查需要真实类型 |

### 问题与修复

1. **pyright 报 11 errors**：anthropic SDK 的 `response.content[0]` 是 union 类型（TextBlock / ThinkingBlock / ToolUseBlock 等），不是所有类型都有 `.text`。修复：`from anthropic.types import TextBlock` + `isinstance` 类型窄化。
2. **ruff I001 import 排序**：测试中函数内 import 顺序不对。修复：按 ruff 要求调整。
3. **分支切换问题**：工作区意外切到 `chore/type-safety-enums` 分支。修复：stash → checkout → stash pop。

### 质量门禁详表

| 检查项 | 结果 |
|--------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 91 files already formatted |
| lint-imports | ✅ 4 contracts kept, 0 broken |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 141 passed |

### PR 链接

https://github.com/neuer/zhixi/pull/7
