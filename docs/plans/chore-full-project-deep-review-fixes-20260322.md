# 全栈深度审查修复实施计划

> **执行指引：** 使用 deep-review skill 按轮次逐步执行。步骤使用 checkbox (`- [ ]`) 语法追踪进度。

**目标：** 修复 `app/` + `admin/src/` + `packages/` 中 D1-D6 + D8-D10 共 9 个维度发现的 3 个 Critical + 20 个 Important + 10 个 Suggestion 问题

**审查模式：** 全量

**技术栈：** FastAPI + Python 3.12+ + SQLAlchemy 2.x + aiosqlite + Vue 3 + TypeScript + Vant 4 + Vite

**分支命名：** `chore/full-project-deep-review-fixes`

**分批策略：** 两批 — 第一批 Critical + Important（轮次 1-6），第二批 Suggestion（轮次 7-8）

---

## 文件结构地图

| 操作 | 文件路径 | 职责 | 涉及问题 |
|------|---------|------|---------|
| 修改 | `app/main.py` | 应用启动 + lifespan | C-1 |
| 修改 | `app/api/digest.py` | 日报路由 | C-2, C-3, I-7 |
| 修改 | `app/services/pipeline_service.py` | Pipeline 编排 | I-2 |
| 修改 | `app/services/process_service.py` | AI 加工服务 | I-1, S-5, S-6 |
| 修改 | `app/crypto.py` | 加密解密 | I-3, I-4 |
| 修改 | `app/api/dashboard.py` | 仪表盘路由 | I-8, I-12, S-8 |
| 修改 | `app/clients/notifier.py` | 告警通知 | I-9 |
| 修改 | `app/api/debug.py` | 调试路由 | I-10, I-13, S-3 |
| 修改 | `app/models/api_cost_log.py` | 成本日志模型 | I-11 |
| 修改 | `app/schemas/enums.py` | 枚举定义 | I-11, I-12 |
| 修改 | `app/lib/cost_logger.py` | 成本记录 | I-11 |
| 修改 | `app/api/settings.py` | 设置路由 | I-12, S-3 |
| 修改 | `app/models/config.py` | 系统配置模型 | I-14 |
| 修改 | `app/services/digest_service.py` | 日报服务 | I-6, S-7 |
| 修改 | `app/services/backup_service.py` | 备份服务 | I-5 |
| 修改 | `app/models/topic.py` | Topic 模型 | S-9 |
| 修改 | `app/digest/cover_generator.py` | 封面图生成 | S-10 |
| 修改 | `app/publisher/manual_publisher.py` | 手动发布占位 | I-15 |
| 修改 | `admin/src/views/Settings.vue` | 设置页 | I-16, I-17 |
| 修改 | `admin/src/views/ApiDebug.vue` | 调试页 | I-18 |
| 修改 | `admin/src/views/DigestEdit.vue` | 编辑页 | I-19 |
| 修改 | `admin/src/components/ArticlePreview.vue` | 文章预览 | I-19 |
| 新建 | `admin/src/utils/digest.ts` | Digest 工具 | I-19 |
| 修改 | `admin/src/views/Accounts.vue` | 账号页 | I-20 |
| 生成 | `packages/openapi-client/src/gen/*` | 自动生成 | C-2, C-3, I-7, I-11, I-12 |

---

## 问题总表

| 编号 | 维度 | 置信度 | 文件 | 摘要 |
|------|------|--------|------|------|
| C-1 | D8 异步 | 90 | app/main.py:50 | Alembic 同步迁移阻塞事件循环 |
| C-2 | D10 契约 | 95 | app/api/digest.py:327 | add-tweet response_model=None 导致 OpenAPI 缺失 AddTweetResponse |
| C-3 | D10 契约 | 95 | app/api/digest.py:297 | mark-published response_model=None 导致 OpenAPI 缺失响应 |
| I-1 | D2 静默失败 | 85 | app/services/process_service.py:480-545 | AI 加工全部失败时 pipeline 仍标记 completed |
| I-2 | D8 异步 | 85 | app/services/pipeline_service.py:115-118 | SQLAlchemyError/OSError 时 job_run 永久 RUNNING（锁泄漏） |
| I-3 | D8 异步 | 80 | app/crypto.py:18-26 | PBKDF2 每次调用重新派生密钥，阻塞事件循环 |
| I-4 | D2 静默失败 | 90 | app/crypto.py:44-48 | decrypt_secret 裸 Exception catch 吞掉所有异常 |
| I-5 | D8 异步 | 85 | app/services/backup_service.py:112-140 | run_cleanup 同步文件 I/O 在 async 函数中 |
| I-6 | D8 异步 | 82 | app/services/digest_service.py:330 | _create_topics 循环中逐个 flush |
| I-7 | D1+D10 | 88 | app/api/digest.py:260-277 | regenerate response_model 与 JSONResponse 不一致 |
| I-8 | D1+D8 | 90 | app/api/dashboard.py:141-178 | get_logs 全文件读入内存 + 后续处理在主线程 |
| I-9 | D6 简化 | 85 | app/clients/notifier.py:99-122 | 两个 except 分支逻辑完全重复 |
| I-10 | D6 简化 | 80 | app/api/debug.py:200-216 | 手动 try/finally close 应改用 async with |
| I-11 | D3 类型 | 90 | app/models/api_cost_log.py:20 | call_type 使用裸 str 而非枚举 |
| I-12 | D3 类型 | 88 | app/api/dashboard.py:131 | log level 参数使用 str 而非枚举 |
| I-13 | D1 规范 | 83 | app/api/debug.py:56-68 | raise_for_status 在 resp.json() 之后，可能 UnboundLocalError |
| I-14 | D5 注释 | 90 | app/models/config.py:9 | docstring "非密钥" 与实际存密钥不符 |
| I-15 | D5 注释 | 75 | app/publisher/manual_publisher.py:1 | docstring "P3 阶段实现" 已过时 |
| I-16 | D3+D10 | 95 | admin/src/views/Settings.vue:65-71 | SecretItem 手写类型重复 OpenAPI 生成类型 |
| I-17 | D3+D10 | 88 | admin/src/views/Settings.vue:24-33 | SettingsForm 手写类型重复 OpenAPI 生成类型 |
| I-18 | D3+D10 | 88 | admin/src/views/ApiDebug.vue:10-20 | TweetItem 手写类型重复 OpenAPI 生成类型 |
| I-19 | D3+D9 | 95 | admin/src/views/DigestEdit.vue + ArticlePreview.vue | PerspectiveItem 两处重复定义 |
| I-20 | D9 架构 | 90 | admin/src/views/Accounts.vue:387 | 模板中 .then() 链违反展示/业务分离 |
| S-1 | D6 简化 | 82 | app/services/digest_service.py:325-343 | 裸元组可用 NamedTuple 提升可读性 |
| S-2 | D6 简化 | 82 | app/api/settings.py + debug.py | _elapsed_ms 函数重复定义 |
| S-3 | D3 类型 | 85 | app/api/settings.py:243-244 | delete_secret key 参数应为枚举 |
| S-4 | D5 注释 | 80 | app/processor/batch_merger.py:20 | R.1.5b 编号与 R.1.5 Thread prompt 易混淆 |
| S-5 | D6 简化 | 78 | app/services/process_service.py:622-688 | account 字段提取重复三元条件 |
| S-6 | D1 规范 | 77 | app/services/process_service.py:405 | tweet_map 遍历 O(N*M)，可用倒排索引优化 |
| S-7 | D1+D6 | 72 | app/services/digest_service.py:330 | _build_sortable_items 裸元组 |
| S-8 | D6 简化 | 72 | app/api/dashboard.py:265-308 | 多层 if/elif 可用优先级键简化 |
| S-9 | D8 异步 | 75 | app/models/topic.py:18 | Topic.digest_date 缺少索引 |
| S-10 | D8 异步 | 80 | app/digest/cover_generator.py:122 | 同步 mkdir 在 async 函数中 |

---

## 第 1 轮 — 事件循环阻塞与契约修复（Critical）

> 目标：修复所有 Critical 问题 — 事件循环阻塞和 OpenAPI 契约缺失
> 包含问题：C-1, C-2, C-3

### 1.1 C-1: Alembic 同步迁移阻塞事件循环

**文件：** `app/main.py`

- [ ] **Step 1:** 读取 `app/main.py`，找到 `_run_alembic_upgrade()` 调用位置
- [ ] **Step 2:** 将 lifespan 中的 `_run_alembic_upgrade()` 调用改为 `await asyncio.to_thread(_run_alembic_upgrade)`，确保 import asyncio
- [ ] **Step 3:** 运行 `pyright app/main.py` 确认类型正确

### 1.2 C-2: add-tweet response_model=None 导致 OpenAPI 缺失

**文件：** `app/api/digest.py`

- [ ] **Step 1:** 读取 `app/api/digest.py`，找到 `POST /add-tweet` 路由装饰器
- [ ] **Step 2:** 将 `response_model=None` 改为合适的 response_model（如 `AddTweetResponse`），同时为 JSONResponse 回退路径使用 `responses` 参数声明替代响应码
- [ ] **Step 3:** 运行 `pyright app/api/digest.py` 确认类型正确

### 1.3 C-3: mark-published response_model=None 导致 OpenAPI 缺失

**文件：** `app/api/digest.py`

- [ ] **Step 1:** 同文件，找到 `POST /mark-published` 路由装饰器
- [ ] **Step 2:** 将 `response_model=None` 改为 `MessageResponse`，为 JSONResponse 回退路径使用 `responses` 参数
- [ ] **Step 3:** 运行 `pyright app/api/digest.py` 确认类型正确

### 1.4 I-7: regenerate response_model 与 JSONResponse 不一致

**文件：** `app/api/digest.py`

- [ ] **Step 1:** 找到 `POST /regenerate` 路由装饰器，检查 response_model 设置
- [ ] **Step 2:** 确保 response_model 与实际返回类型一致，为错误路径使用 `responses` 参数

### 第 1 轮验证

- [ ] **运行后端门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **运行 make gen 更新前端类型**

```bash
make gen
```

- [ ] **提交本轮修复**

```bash
git add app/main.py app/api/digest.py packages/openapi-client/
git commit -m "fix: 修复事件循环阻塞和 OpenAPI 契约缺失 (C-1, C-2, C-3, I-7)"
```

---

## 第 2 轮 — Pipeline 可靠性与加密安全

> 目标：修复 pipeline 锁泄漏、AI 加工静默失败、密钥派生阻塞
> 包含问题：I-1, I-2, I-3, I-4

### 2.1 I-2: Pipeline error 时 job_run 永久 RUNNING

**文件：** `app/services/pipeline_service.py`

- [ ] **Step 1:** 读取 pipeline_service.py，找到 `except (SQLAlchemyError, OSError)` 块
- [ ] **Step 2:** 在 re-raise 之前添加 `job_run.status = JobStatus.FAILED` + `job_run.error_message = str(exc)[:500]` + `job_run.finished_at = datetime.now(UTC)`，用 try/except 包裹状态更新避免二次失败
- [ ] **Step 3:** 搜索 tests/ 中 pipeline_service 相关测试，确认是否需要更新断言

### 2.2 I-1: AI 加工全部失败时 pipeline 仍标记 completed

**文件：** `app/services/process_service.py`

- [ ] **Step 1:** 读取 process_service.py，找到 `run_daily_process` 方法末尾的失败率检查逻辑
- [ ] **Step 2:** 当 `failed_count == total` 且 `total > 0` 时，抛出异常让 pipeline 标记为 FAILED，而非仅记录日志
- [ ] **Step 3:** 搜索相关测试确认断言是否需要更新

### 2.3 I-3: PBKDF2 每次调用重新派生密钥

**文件：** `app/crypto.py`

- [ ] **Step 1:** 读取 crypto.py，理解 `_derive_key` 调用模式
- [ ] **Step 2:** 添加模块级缓存：用 `functools.lru_cache` 或模块级变量缓存派生后的 Fernet 实例（因为 JWT_SECRET_KEY 运行期间不变）
- [ ] **Step 3:** 确保缓存机制在测试中不会导致 cross-test 污染

### 2.4 I-4: decrypt_secret 裸 Exception catch

**文件：** `app/crypto.py`

- [ ] **Step 1:** 将 `except Exception` 改为只捕获 `InvalidToken`（来自 cryptography.fernet），让其他非预期异常正常传播
- [ ] **Step 2:** 将 `logger.warning` 提升为 `logger.error`
- [ ] **Step 3:** 运行 `pytest tests/test_crypto.py` 确认测试通过

### 第 2 轮验证

- [ ] **运行后端门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **提交本轮修复**

```bash
git add app/services/pipeline_service.py app/services/process_service.py app/crypto.py
git commit -m "fix: 修复 pipeline 锁泄漏、AI 加工静默失败、密钥派生阻塞 (I-1, I-2, I-3, I-4)"
```

---

## 第 3 轮 — 异步正确性修复

> 目标：修复同步 I/O 在 async 上下文中的问题
> 包含问题：I-5, I-6, I-8

### 3.1 I-5: backup_service 同步文件 I/O

**文件：** `app/services/backup_service.py`

- [ ] **Step 1:** 读取 backup_service.py，找到 `run_cleanup` 方法
- [ ] **Step 2:** 将同步文件操作（iterdir, stat, unlink）提取为同步辅助函数，用 `asyncio.to_thread` 包装
- [ ] **Step 3:** 检查 run_backup 方法中的同步操作，同样处理

### 3.2 I-6: _create_topics 循环中逐个 flush

**文件：** `app/services/digest_service.py`

- [ ] **Step 1:** 读取 digest_service.py 中 `_create_topics` 方法
- [ ] **Step 2:** 将循环中的 `await self._db.flush()` 改为：先批量 add 所有 topic，执行一次 `flush()`，再遍历关联 tweet_id
- [ ] **Step 3:** 运行相关测试确认行为不变

### 3.3 I-8: Dashboard log 全文件读入内存

**文件：** `app/api/dashboard.py`

- [ ] **Step 1:** 读取 dashboard.py 中 `get_logs` 函数
- [ ] **Step 2:** 将整个日志解析逻辑（读取 + splitlines + JSON parse + 过滤）整合到一个同步辅助函数中，用 `asyncio.to_thread` 包装
- [ ] **Step 3:** 运行 `pytest tests/test_dashboard_api.py` 确认通过

### 第 3 轮验证

- [ ] **运行后端门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **提交本轮修复**

```bash
git add app/services/backup_service.py app/services/digest_service.py app/api/dashboard.py
git commit -m "fix: 修复异步上下文中的同步 I/O 问题 (I-5, I-6, I-8)"
```

---

## 第 4 轮 — 类型安全与枚举改造

> 目标：将裸 str 字段改为枚举，修复代码规范问题
> 包含问题：I-9, I-10, I-11, I-12, I-13, I-14, I-15

### 4.1 I-11: call_type 裸 str 改枚举

**文件：** `app/schemas/enums.py`, `app/models/api_cost_log.py`, `app/lib/cost_logger.py`

- [x] **Step 1:** 在 `app/schemas/enums.py` 中新增 `CallType(StrEnum)` 枚举，包含所有已使用的 call_type 值
- [x] **Step 2:** 更新 ORM 模型和 `record_api_cost` 函数的参数类型
- [x] **Step 3:** 搜索所有 `call_type=` 调用点，替换为枚举成员

### 4.2 I-12: log level 参数改枚举

**文件：** `app/api/dashboard.py`

- [x] **Step 1:** 将 `level: str` 参数改为 `Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]`
- [x] **Step 2:** FastAPI 自动校验无效值返回 422，保留 fallback 20 作为防御性编程

### 4.3 I-9: notifier.py 重复 except 块

**文件：** `app/clients/notifier.py`

- [x] **Step 1:** 合并 `except httpx.HTTPError` 和 `except Exception` 为单个 `except Exception`
- [x] **Step 2:** 确认合并后日志内容不变

### 4.4 I-10: debug.py 手动 try/finally 改 async with

**文件：** `app/api/debug.py`

- [x] **Step 1:** 将 `XApiFetcher` 的 `try/finally/close()` 模式改为 `async with XApiFetcher(...) as fetcher:`
- [x] **Step 2:** 确认所有使用点都已替换（debug_x_tweets + debug_x_tweet 两处）

### 4.5 I-13: debug.py raise_for_status 顺序修复

**文件：** `app/api/debug.py`

- [x] **Step 1:** 在 `debug_x_ping` 中将 `resp.raise_for_status()` 移到 `resp.json()` 之前
- [x] **Step 2:** 在 HTTPStatusError except 块中通过 `exc.response.json()` 安全获取响应

### 4.6 I-14 + I-15: 修复过时注释

**文件：** `app/models/config.py`, `app/publisher/manual_publisher.py`

- [x] **Step 1:** 将 SystemConfig docstring 从 "非密钥" 改为反映实际用途
- [x] **Step 2:** 将 manual_publisher.py docstring 从 "P3 阶段实现" 改为反映已完成状态

### 第 4 轮验证

- [x] **运行后端门禁** — ruff check + format + pyright + pytest 564 passed

- [ ] **运行 make gen 更新前端类型（枚举变更影响 OpenAPI）** — CallType 仅用于后端 ORM/Service，不影响 API 路由参数/响应 schema，但 level Literal 变更会影响 OpenAPI

- [ ] **提交本轮修复**

```bash
git add app/schemas/enums.py app/models/ app/lib/cost_logger.py app/api/dashboard.py app/clients/notifier.py app/api/debug.py app/publisher/manual_publisher.py packages/openapi-client/
git commit -m "fix: 枚举类型改造 + 代码规范修复 + 注释更新 (I-9~I-15)"
```

---

## 第 5 轮 — 前端类型清理（手写类型 → OpenAPI 生成类型）

> 目标：消除前端手写的重复类型定义，统一使用 OpenAPI 生成类型
> 包含问题：I-16, I-17, I-18, I-19, I-20

### 5.1 I-16: Settings.vue SecretItem 替换

**文件：** `admin/src/views/Settings.vue`

- [ ] **Step 1:** 读取 Settings.vue，找到手写的 `SecretItem` interface
- [ ] **Step 2:** 替换为 `import type { SecretStatusItem } from "@zhixi/openapi-client"`，更新所有引用点

### 5.2 I-17: Settings.vue SettingsForm 派生

**文件：** `admin/src/views/Settings.vue`

- [ ] **Step 1:** 将手写的 `SettingsForm` 改为从 `SettingsResponse` 用 `Pick<>` 派生
- [ ] **Step 2:** 确认所有字段映射正确

### 5.3 I-18: ApiDebug.vue TweetItem 替换

**文件：** `admin/src/views/ApiDebug.vue`

- [ ] **Step 1:** 将手写的 `TweetItem` 替换为从 `@zhixi/openapi-client` 导入的 `RawTweet`
- [ ] **Step 2:** 更新所有引用点

### 5.4 I-19: PerspectiveItem 提取到共享模块

**文件：** `admin/src/utils/digest.ts`（新建）, `admin/src/views/DigestEdit.vue`, `admin/src/components/ArticlePreview.vue`

- [ ] **Step 1:** 新建 `admin/src/utils/digest.ts`，将 `PerspectiveItem` 和 `parsePerspectives` 提取到此处
- [ ] **Step 2:** 更新 DigestEdit.vue 和 ArticlePreview.vue，import 替代本地定义
- [ ] **Step 3:** 确认功能不变

### 5.5 I-20: Accounts.vue 模板 .then() 链修复

**文件：** `admin/src/views/Accounts.vue`

- [ ] **Step 1:** 将 `@click="toggleActive(editingAccount).then(...)"`  提取为独立 async 方法
- [ ] **Step 2:** 模板中改为调用该方法

### 第 5 轮验证

- [ ] **运行前端门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交本轮修复**

```bash
git add admin/src/
git commit -m "fix: 前端类型清理 — 消除手写重复类型 + PerspectiveItem 提取 (I-16~I-20)"
```

---

## 第 6 轮 — 全量门禁验证

> 目标：全栈门禁通过 + 生成物一致性

- [ ] **运行后端全量门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **运行前端全量门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **生成物一致性检查**

```bash
make gen && git diff --exit-code
```

- [ ] **修复任何失败项后追加 commit**

---

## 第 7 轮 — Suggestion 修复（第二批）

> 目标：修复 Suggestion 级别问题
> 包含问题：S-1 ~ S-10

### 7.1 S-1 + S-7: _build_sortable_items 裸元组改 NamedTuple

> S-1 和 S-7 指向同一函数，合并处理。

**文件：** `app/services/digest_service.py`

- [ ] **Step 1:** 定义 `SortableItem = NamedTuple("SortableItem", [("heat_score", float), ("item_type", ItemType), ("source", "Tweet | Topic"), ("extra", "dict[str, object]")])`
- [ ] **Step 2:** 更新 `_build_sortable_items` 返回类型和所有引用点（解构赋值改为属性访问）

### 7.2 S-2: _elapsed_ms 重复定义提取

**文件：** `app/api/settings.py`, `app/api/debug.py`, `app/lib/timing.py`（新建）

- [ ] **Step 1:** 新建 `app/lib/timing.py`，将 `_elapsed_ms` 函数移入
- [ ] **Step 2:** 两个路由模块改为 `from app.lib.timing import elapsed_ms`

### 7.3 S-3: delete_secret key 参数改枚举

**文件：** `app/api/settings.py`, `app/schemas/enums.py`

- [ ] **Step 1:** 在 `app/schemas/enums.py` 新增 `SecretKey(StrEnum)` 枚举
- [ ] **Step 2:** 将路径参数 `key: str` 改为 `key: SecretKey`，移除手动 `if key not in SECRET_CONFIG_KEYS` 校验

### 7.4 S-4: batch_merger docstring 编号说明

**文件：** `app/processor/batch_merger.py`

- [ ] **Step 1:** 在 docstring 中补充说明 `R.1.5b` 是去重专用 prompt 编号（区别于 R.1.5 Thread prompt）

### 7.5 S-5: account 字段提取

**文件：** `app/services/process_service.py`

- [ ] **Step 1:** 提取 `_account_fields(account)` 辅助函数，返回 `(name, handle, bio)` 元组
- [ ] **Step 2:** 替换 3 处重复的三元条件

### 7.6 S-6: tweet_map O(N*M) 优化

**文件：** `app/services/process_service.py`

- [ ] **Step 1:** 在循环前按 `topic_id` 建立倒排索引 `dict[int, list[Tweet]]`

### 7.7 S-8: dashboard _get_recent_7_days 优先级键简化

**文件：** `app/api/dashboard.py`

- [ ] **Step 1:** 定义 `_priority(d)` 函数返回可比较的元组
- [ ] **Step 2:** 用 `max(group, key=_priority)` 替代多层 if/elif

### 7.8 S-9: Topic.digest_date 添加索引

**文件：** `app/models/topic.py`

- [ ] **Step 1:** 为 `digest_date` 字段添加 `index=True`
- [ ] **Step 2:** 生成 Alembic 迁移脚本 `alembic revision --autogenerate -m "add topic digest_date index"`

### 7.9 S-10: cover_generator mkdir 改异步

**文件：** `app/digest/cover_generator.py`

- [ ] **Step 1:** 将 `_COVERS_DIR.mkdir(...)` 包装到 `asyncio.to_thread` 中

### 第 7 轮验证

- [ ] **运行全量门禁**

```bash
ruff check . && ruff format --check . && pyright && pytest
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
make gen && git diff --exit-code
```

- [ ] **提交本轮修复**

```bash
git add -u && git add alembic/versions/ app/lib/timing.py
git commit -m "refactor: Suggestion 级别优化 — 类型安全 + 性能 + 可读性 (S-1~S-10)"
```

---

## 执行结果（待回填）

> 以下内容在全部修复完成并创建 PR 后一次性回填。

### 交付物清单

（待回填）

### 偏离项表格

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|

### 问题与修复记录

（待回填）

### 质量门禁详表

（待回填）

### PR 链接

（待回填）
