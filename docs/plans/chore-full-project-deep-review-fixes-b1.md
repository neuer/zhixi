# 全栈深度审查修复实施计划 — Batch 1

> **执行指引：** 使用 deep-review skill 按轮次逐步执行。步骤使用 checkbox (`- [ ]`) 语法追踪进度。

**目标：** 修复 `app/` + `admin/src/` 中 D1-D6+D8+D9+D10 维度发现的 5 个 Critical + 20 个 Important 问题

**审查模式：** 全量

**技术栈：** FastAPI + Python 3.12+ + 异步 SQLAlchemy 2.x + aiosqlite；Vue 3 + TypeScript + Vant 4

**分支命名：** `chore/full-project-deep-review-fixes-b1`

**分批策略：** 三批（本文件为 Batch 1：Critical + 高优先 Important）

---

## 文件结构地图

| 操作 | 文件路径 | 职责 | 涉及问题 |
|------|---------|------|---------|
| 修改 | `app/crypto.py` | 密钥加解密 | C-1 |
| 修改 | `app/clients/notifier.py` | 告警通知 | C-2, I-33 |
| 修改 | `app/api/settings.py` | 设置 API | C-3 |
| 新建 | `tests/test_cost_logger.py` | cost_logger 单元测试 | C-4 |
| 新建 | `tests/test_middleware.py` | middleware 单元测试 | C-4 |
| 修改 | `app/api/history.py` | 历史记录 API | I-1 |
| 修改 | `app/api/digest.py` | 日报 API | I-1, I-9, I-29 |
| 修改 | `admin/src/composables/useXApiDebug.ts` | X API 调试 | I-2 |
| 修改 | `app/schemas/processor_types.py` | Processor 类型 | I-3 |
| 修改 | `app/services/process_service.py` | AI 加工服务 | I-5 |
| 修改 | `admin/src/components/AccountAddPopup.vue` | 添加账号弹窗 | I-6 |
| 修改 | `app/api/debug.py` | 调试 API | I-7, I-14 |
| 修改 | `app/digest/renderer.py` | Markdown 渲染器 | I-10 |
| 修改 | `admin/src/composables/useApiStatus.ts` | API 状态检测 | I-11 |
| 修改 | `admin/src/views/DigestEdit.vue` | 日报编辑页 | I-13 |
| 修改 | `app/services/digest_service.py` | 日报服务 | I-15, I-43 |
| 修改 | `app/digest/cover_generator.py` | 封面图生成 | I-16 |
| 修改 | `app/fetcher/x_api.py` | X API 抓取 | I-17 |
| 修改 | `admin/src/composables/useSecretsManager.ts` | 密钥管理 | I-18, I-25 |
| 修改 | `app/schemas/auth_types.py` | 认证类型 | I-19 |
| 修改 | `app/services/pipeline_service.py` | Pipeline 服务 | I-27 |
| 修改 | `app/api/dashboard.py` | 仪表盘 API | I-30 |
| 测试 | `tests/` 多个文件 | 同步更新测试 | 各 Critical/Important |

---

## 问题总表

| 编号 | 维度 | 置信度 | 文件 | 摘要 |
|------|------|--------|------|------|
| C-1 | D2 | 95 | app/crypto.py:53-55 | decrypt_secret 解密失败返回空字符串 |
| C-2 | D1+D8 | 95 | app/clients/notifier.py:18-20 | _consecutive_failures 全局变量竞态 |
| C-3 | D8 | 92 | app/api/settings.py:265-269 | asyncio.gather 并发共享 AsyncSession |
| C-4 | D4 | 90 | app/lib/cost_logger.py + app/middleware.py | 基础设施代码无单元测试 |
| C-5 | D4 | 85 | app/api/debug.py + app/publisher/manual_publisher.py | 关键模块无测试 |
| I-1 | D10 | 92 | app/api/history.py + digest.py | summary_degraded 在 preview/history 中始终 False |
| I-2 | D3+D9+D10 | 90 | useXApiDebug.ts | 手写类型与 OpenAPI 重复 |
| I-3 | D3 | 90 | processor_types.py + enums.py | TopicResult.type "single" 与 DB 枚举不匹配 |
| I-5 | D2 | 90 | process_service.py | AI 加工失败静默返回 False |
| I-6 | D2 | 90 | AccountAddPopup.vue | 非 502 错误被吞掉 |
| I-7 | D1 | 90 | api/debug.py | 调用 XApiFetcher 私有方法 |
| I-9 | D1 | 89 | api/digest.py:326 | publish_mode 枚举比较问题 |
| I-10 | D2 | 88 | digest/renderer.py | JSON 解析失败返回空列表 |
| I-11 | D2+D9 | 88 | useApiStatus.ts | API 检测失败无用户反馈 |
| I-13 | D6+D9 | 88 | DigestEdit.vue | handleSave payload 重复 + null 问题 |
| I-14 | D1 | 85 | api/debug.py | 路由 import fetcher 内部代码 |
| I-15 | D1 | 85 | digest_service.py:630 | import processor.heat_calculator |
| I-16 | D2 | 85 | cover_generator.py | 封面图失败静默跳过 |
| I-17 | D2 | 85 | x_api.py:246-257 | 推文解析失败静默跳过 |
| I-19 | D3 | 85 | auth_types.py:17 | password 无最小长度 |
| I-25 | D2 | 85 | useSecretsManager.ts | catch 混合用户取消和请求失败 |
| I-27 | D2 | 82 | pipeline_service.py | Pipeline 异常 CLI exit code 0 |
| I-29 | D1 | 80 | api/digest.py:76 | 路由 import digest prompt 常量 |
| I-30 | D1 | 80 | api/dashboard.py:143-150 | 日志分页 total 不准确 |
| I-33 | D2 | 80 | clients/notifier.py:105-113 | 告警失败被吞掉 |
| I-18 | D10 | 85 | useSecretsManager.ts:14 | 手写类型而非生成类型 |
| I-43 | D1 | 75 | digest_service.py:667-675 | _get_existing_base_scores 可能含 None |

---

## 第 1 轮 — Critical 后端安全与并发修复

> 目标：修复 3 个 Critical 后端问题（C-1, C-2, C-3）
> 包含问题：C-1, C-2, C-3

### 1.1 C-1: decrypt_secret 解密失败返回空字符串

**文件：** `app/crypto.py:53-55`

- [ ] **Step 1:** 读取 `app/crypto.py` 当前代码，确认 `decrypt_secret` 函数的异常处理逻辑
- [ ] **Step 2:** 定义 `SecretDecryptionError` 异常类（在 `crypto.py` 中），继承 `RuntimeError`
- [ ] **Step 3:** 修改 `decrypt_secret`：`InvalidToken` 异常时不再返回空字符串，改为 `raise SecretDecryptionError("密钥解密失败，可能 JWT_SECRET_KEY 已变更")` 并保持日志
- [ ] **Step 4:** 搜索 `tests/` 中调用 `decrypt_secret` 的测试，更新断言为 `pytest.raises(SecretDecryptionError)`
- [ ] **Step 5:** 搜索 `app/` 中所有调用 `decrypt_secret` 的地方，确认上层是否需要 catch 新异常。如果 `get_secret_config` 调用了 `decrypt_secret`，需要在 API 层面为用户提供有意义的错误消息（如 "密钥配置异常"）

### 1.2 C-2: notifier.py 全局变量竞态 + 告警失败吞错（含 I-33）

**文件：** `app/clients/notifier.py:18-20, 97-113`

- [ ] **Step 1:** 读取 `app/clients/notifier.py` 当前代码
- [ ] **Step 2:** 将 `_consecutive_failures` 和 `_FAILURE_THRESHOLD` 改为类实例属性（如果已有 `Notifier` 类）或改用 `asyncio.Lock` 保护全局变量的读写
- [ ] **Step 3:** 在连续失败达阈值时，除 `logger.critical` 外，将告警系统健康状态写入一个模块级标志位（如 `_alert_system_degraded = True`），供 Dashboard API 读取
- [ ] **Step 4:** 确认 catch 块中不完全吞掉异常——至少在日志中保留 exc_info

### 1.3 C-3: asyncio.gather 并发共享 AsyncSession

**文件：** `app/api/settings.py:265-269`

- [ ] **Step 1:** 读取 `app/api/settings.py` 中 `get_api_status` 路由代码
- [ ] **Step 2:** 将 `_ping_x_api(db)`、`_ping_claude_api(db)`、`_ping_gemini_api(db)` 中的 DB 查询（`get_secret_config`）提到 `asyncio.gather` 之前串行执行。将解密后的 key 作为参数传给各 ping 函数，gather 只并发执行外部 HTTP 请求
- [ ] **Step 3:** 修改三个 `_ping_*_api` 函数签名，接受 `api_key: str` 参数而非 `db: AsyncSession`
- [ ] **Step 4:** 运行相关测试确认无回归

### 第 1 轮验证

- [ ] **运行本轮门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **提交本轮修复**

```bash
git add app/crypto.py app/clients/notifier.py app/api/settings.py tests/
git commit -m "fix: 修复 Critical 后端安全与并发问题 (C-1, C-2, C-3)"
```

---

## 第 2 轮 — Critical 测试覆盖补齐

> 目标：为无测试的基础设施代码补充测试（C-4, C-5）
> 包含问题：C-4, C-5

### 2.1 C-4: cost_logger + middleware 补充测试

- [ ] **Step 1:** 读取 `app/lib/cost_logger.py` 和 `app/middleware.py` 的代码
- [ ] **Step 2:** 创建 `tests/test_cost_logger.py`，测试 `record_api_cost` 和 `record_api_cost_failure` 的正常路径和 `digest_date=None` fallback 路径
- [ ] **Step 3:** 创建 `tests/test_middleware.py`，测试 `RequestIdMiddleware` 的 request_id 注入和 `X-Request-ID` 响应头

### 2.2 C-5: debug 路由和 manual_publisher 补充测试

- [ ] **Step 1:** 读取 `app/api/debug.py` 和 `app/publisher/manual_publisher.py`
- [ ] **Step 2:** 为 debug 路由的关键端点创建基本测试（至少覆盖认证检查和正常响应）
- [ ] **Step 3:** 为 `manual_publisher.py` 的 `ManualPublisher.publish()` 创建单元测试

### 第 2 轮验证

- [ ] **运行 pytest（包含所有新建测试）**

```bash
pytest tests/test_cost_logger.py tests/test_middleware.py tests/test_debug_api.py tests/test_manual_publisher.py -v
```

- [ ] **提交**

```bash
git add tests/test_cost_logger.py tests/test_middleware.py tests/
git commit -m "test: 补充 cost_logger + middleware + debug + publisher 测试 (C-4, C-5)"
```

---

## 第 3 轮 — 后端静默失败修复

> 目标：修复后端关键的错误吞没问题
> 包含问题：I-5, I-9, I-10, I-16, I-17, I-27, I-33（I-33 已在第 1 轮 C-2 中处理）

### 3.1 I-5: AI 加工失败丢失错误上下文

**文件：** `app/services/process_service.py:502-567`

- [x] **Step 1:** 读取三个 `_process_*_with_retry` 方法
- [x] **Step 2:** 在 except 块中增加 `logger.error` 记录具体失败的 tweet_id/topic_id 和异常详情
- [x] **Step 3:** 在 `ProcessResult` 中添加 `failed_details: list[str]` 字段（默认空列表），`_process_all_items` 收集失败详情到该字段

### 3.2 I-9: publish_mode 枚举比较

**文件：** `app/api/digest.py:326`

- [x] **Step 1:** 读取 `confirm_publish` 路由中 `publish_mode` 的比较逻辑
- [x] **Step 2:** 对 DB 读出的值做显式枚举转换：`try: mode = PublishMode(publish_mode) except ValueError: mode = PublishMode.MANUAL`
- [x] **Step 3:** 搜索测试中断言相关的测试用例，确认无回归

### 3.3 I-10: renderer.py JSON 解析失败改善日志

**文件：** `app/digest/renderer.py:173-183`

- [x] **Step 1:** 读取 `_parse_json_list` 函数
- [x] **Step 2:** 确认当前状态：已有 `logger.error` 且包含截断原始数据（`json_str[:200]`），日志内容充分

### 3.4 I-16: 封面图生成失败增加告警

**文件：** `app/digest/cover_generator.py:139-147`

- [x] **Step 1:** 读取 `generate_cover_image` 函数的异常处理
- [x] **Step 2:** 在 `digest_service.py` 中 `cover_path is None` 且 `enable_cover` 为 True 时增加 `send_alert` 告警通知

### 3.5 I-17: 推文解析失败增加计数和告警

**文件：** `app/fetcher/x_api.py:246-257`

- [x] **Step 1:** 读取 `_parse_tweet` 调用方的循环代码
- [x] **Step 2:** 确认已有实现：全部失败抛 `XApiError`，部分失败记录 `logger.warning`（已在之前轮次修复）

### 3.6 I-27: Pipeline 异常 CLI exit code 修复

**文件：** `app/services/pipeline_service.py` + `app/cli.py`

- [x] **Step 1:** 读取 `run_pipeline` 返回值和 `app/cli.py` 调用处
- [x] **Step 2:** 确认已有实现：CLI 层在 `result.status == "failed"` 时 `raise typer.Exit(code=1)`（已在之前轮次修复）

### 第 3 轮验证

- [x] **运行后端门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [x] **提交**

```bash
git add app/services/process_service.py app/api/digest.py app/services/digest_service.py app/schemas/processor_types.py docs/plans/chore-full-project-deep-review-fixes-b1.md
git commit -m "fix: 修复后端静默失败问题 (I-5, I-9, I-10, I-16, I-17, I-27)"
```

---

## 第 4 轮 — 后端模块隔离与类型安全

> 目标：修复模块隔离违规和类型设计问题
> 包含问题：I-1, I-3, I-7, I-14, I-15, I-19, I-29, I-30, I-43

### 4.1 I-1: summary_degraded 在 preview/history 中缺失

**文件：** `app/api/digest.py`, `app/api/history.py`

- [ ] **Step 1:** 读取 `get_preview` 和 `get_preview_by_token` 路由，确认 `summary_degraded` 是否被设置
- [ ] **Step 2:** 提取 `_set_degraded_flag(brief, digest)` 辅助函数，在所有返回 `DigestBriefResponse` 的路由中统一调用
- [ ] **Step 3:** 在 `history` 接口的 `HistoryDetailResponse` 中也包含 degraded 信息（如适用）

### 4.2 I-3: TopicResult.type 与 DB 枚举不匹配

**文件：** `app/schemas/processor_types.py:48`

- [ ] **Step 1:** 读取 `TopicResult` 和 `TopicType` 枚举
- [ ] **Step 2:** 将 `TopicResult.type` 改为使用独立的 `Literal["aggregated", "thread", "single"]` 类型别名 `TopicResultKind`，与 DB 层 `TopicType` 明确区分
- [ ] **Step 3:** 在 `process_service.py` 中对 `type="single"` 的 TopicResult 添加断言确保不入 DB

### 4.3 I-7 + I-14: debug 路由模块隔离修复

**文件：** `app/api/debug.py`

- [ ] **Step 1:** 读取 debug.py 中所有 import fetcher 的代码
- [ ] **Step 2:** 将 `_build_includes_index` 和 `_parse_tweet` 在 `XApiFetcher` 中去掉下划线前缀，改为公共方法
- [ ] **Step 3:** 将 `enrich_tweet_text` 移到 `app/fetcher/__init__.py` 作为公共导出（或保留在 x_api.py 但作为公共 API）

### 4.4 I-15: digest_service import processor.heat_calculator

**文件：** `app/services/digest_service.py:630`

- [ ] **Step 1:** 读取 `_calculate_manual_heat` 方法
- [ ] **Step 2:** 将 `heat_calculator.py` 中被 digest_service 使用的函数（`calculate_base_score`, `calculate_heat_score`, `normalize_scores`）移到 `app/lib/heat_calculator.py`，作为共享基础设施
- [ ] **Step 3:** 更新 `processor/` 和 `services/digest_service.py` 的 import 路径
- [ ] **Step 4:** 更新 `import-linter` 配置（如需）

### 4.5 I-19: password 添加最小长度校验

**文件：** `app/schemas/auth_types.py:17`

- [ ] **Step 1:** 读取 `SetupInitRequest` 和 `ChangePasswordRequest`
- [ ] **Step 2:** 给 `password` 字段添加 `min_length=8`
- [ ] **Step 3:** 搜索测试中密码相关断言，更新使用太短密码的测试用例

### 4.6 I-29: digest.py 路由 import prompt 常量

**文件：** `app/api/digest.py:76`

- [ ] **Step 1:** 读取 `get_today_digest` 中 `DEFAULT_SUMMARY` 的使用
- [ ] **Step 2:** 将降级判断逻辑移到 `DigestService`，在 `get_today_digest` 的返回值中增加 `summary_degraded` 信息（与 I-1 统一处理）

### 4.7 I-30: 日志分页 total 不准确

**文件：** `app/api/dashboard.py:143-150`

- [ ] **Step 1:** 读取 `_parse_log_file` 和调用方的分页逻辑
- [ ] **Step 2:** 修改逻辑：先不限制 max_entries 计算 total 数量，再对结果切片取当页数据
- [ ] **Step 3:** 或者改为两步：先用轻量扫描计算总行数，再读取目标页

### 4.8 I-43: _get_existing_base_scores 过滤 None

**文件：** `app/services/digest_service.py:667-675`

- [ ] **Step 1:** 读取查询代码
- [ ] **Step 2:** 在查询中添加 `.where(Tweet.base_heat_score.is_not(None))` 过滤

### 第 4 轮验证

- [ ] **运行全部后端门禁 + import-linter**

```bash
ruff check . && ruff format --check . && pyright && uv run lint-imports && pytest
```

- [ ] **提交**

```bash
git add app/ tests/
git commit -m "fix: 修复模块隔离违规与类型安全问题 (I-1, I-3, I-7, I-14, I-15, I-19, I-29, I-30, I-43)"
```

---

## 第 5 轮 — 前端静默失败与类型安全

> 目标：修复前端错误处理和类型问题
> 包含问题：I-2, I-6, I-11, I-13, I-18, I-25

### 5.1 I-2: useXApiDebug 使用 OpenAPI 生成类型

**文件：** `admin/src/composables/useXApiDebug.ts`

- [ ] **Step 1:** 读取文件，确认哪些 `as` 断言可替换为生成类型
- [ ] **Step 2:** 从 `@zhixi/openapi-client` 导入 `DebugXPingResponse`, `DebugXUserResponse`, `DebugXTweetsResponse`, `DebugXTweetResponse`
- [ ] **Step 3:** 替换所有 `data as {...}` 为泛型标注 `api.get<Type>(...)`

### 5.2 I-6: AccountAddPopup 错误处理

**文件：** `admin/src/components/AccountAddPopup.vue:61-73`

- [ ] **Step 1:** 读取 `handleAdd` 的 catch 块
- [ ] **Step 2:** 在 catch 块中区分 502（手动模式）和其他错误。非 502 错误设置 `addError.value` 显示错误信息

### 5.3 I-11: useApiStatus 检测失败反馈

**文件：** `admin/src/composables/useApiStatus.ts:33-34`

- [ ] **Step 1:** 读取 `checkApiStatus` 的 catch 块
- [ ] **Step 2:** catch 中不调用 `closeToast()`（会覆盖拦截器的 toast），改为 `showToast("API 状态检测失败")`

### 5.4 I-13: DigestEdit handleSave 重构

**文件：** `admin/src/views/DigestEdit.vue:88-103`

- [ ] **Step 1:** 读取 handleSave 的 payload 构建逻辑
- [ ] **Step 2:** 用字段映射数组驱动循环替代 5 个重复 if 判断
- [ ] **Step 3:** 修复空字符串转 null 的问题：发送空字符串而非 null，让后端决定语义

### 5.5 I-18: useSecretsManager 使用生成类型

**文件：** `admin/src/composables/useSecretsManager.ts:14`

- [ ] **Step 1:** 读取 `loadSecretsStatus` 的类型标注
- [ ] **Step 2:** 改为使用 `SecretsStatusResponse` 生成类型

### 5.6 I-25: useSecretsManager clearSecret catch 分离

**文件：** `admin/src/composables/useSecretsManager.ts:59-61`

- [ ] **Step 1:** 读取 `clearSecret` 的代码
- [ ] **Step 2:** 将 `showConfirmDialog` 的用户取消处理和 `api.delete` 的错误处理分离为两个独立的 try-catch

### 第 5 轮验证

- [ ] **运行前端门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交**

```bash
git add admin/src/
git commit -m "fix: 修复前端静默失败与类型安全问题 (I-2, I-6, I-11, I-13, I-18, I-25)"
```

---

## 执行结果（待回填）

### 交付物清单
（执行后回填）

### 偏离项表格

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|

### 问题与修复记录
（执行后回填）

### 质量门禁详表
（执行后回填）

### PR 链接
（执行后回填）
