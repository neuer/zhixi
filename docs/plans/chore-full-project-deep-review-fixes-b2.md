# 全栈深度审查修复实施计划 — Batch 2

> **执行指引：** 使用 deep-review skill 按轮次逐步执行。

**目标：** 修复剩余 Important 问题（约 24 项，排除 B1 已修复和重构类）

**审查模式：** 全量

**技术栈：** FastAPI + Python 3.12+ + 异步 SQLAlchemy 2.x；Vue 3 + TypeScript + Vant 4

**分支命名：** `chore/full-project-deep-review-fixes-b2`

**分批策略：** Batch 2/3

---

## SKIPPED 问题（重构类，不纳入本次）

| 编号 | 原因 |
|------|------|
| I-4 | snapshot_perspectives/source_tweets 结构化需后端 Schema 重构 + 前端适配，影响面大 |
| I-8 | 生成 SDK 客户端需要引入新 plugin + 全前端重构 API 调用方式 |
| I-12 | 路由返回 union 类型需定义统一错误响应 Schema，影响 OpenAPI 生成 |
| I-18, I-25, I-43 | 已在 Batch 1 修复 |

---

## 第 1 轮 — 后端类型安全与 Schema 修复

> 包含：I-23, I-26, I-31, I-38, I-40, I-44

### 1.1 I-23 + I-38: SQLite datetime 时区一致性

**文件：** `app/services/lock_service.py`, `app/api/dashboard.py`

- [ ] 读取 lock_service.py 中 clean_stale_jobs 的 cutoff 构造方式
- [ ] 读取 dashboard.py 中 _get_alerts 的 since_dt 构造方式
- [ ] 统一使用 `datetime.now(UTC).replace(tzinfo=None)` 或确保与 DB 存储格式一致（无时区后缀）
- [ ] 搜索项目中其他使用 `datetime.now(UTC)` 做 SQL WHERE 比较的地方，确保一致

### 1.2 I-26: AnalysisResult.from_parsed 类型收紧

**文件：** `app/schemas/processor_types.py`

- [ ] 读取 from_parsed 方法
- [ ] 在 docstring 中补充输入 dict 的预期结构说明
- [ ] 考虑添加关键字段的显式校验（如 topics 必须是 list），校验失败抛出明确异常而非静默降级

### 1.3 I-31: PublishResult 不变量约束

**文件：** `app/schemas/publisher_types.py`

- [ ] 读取 PublishResult 的 model_validator
- [ ] 添加约束：success=True 时 status 必须为 PUBLISHED；success=False 时 status 必须为 FAILED
- [ ] 搜索测试中构造 PublishResult 的地方，确认无回归

### 1.4 I-40: ReferencedTweet.type 类型收窄

**文件：** `app/schemas/fetcher_types.py`

- [ ] 读取 ReferencedTweet.type 定义和注释
- [ ] 保持 str 类型（X API 可能返回未知值）但添加注释说明设计决策
- [ ] 或改为 `Literal["replied_to", "quoted", "retweeted"] | str`（Pydantic v2 union 降级）

### 1.5 I-44: PBKDF2 固定 salt 文档化

**文件：** `app/crypto.py`

- [ ] 在 _SALT 定义处添加注释说明设计决策和风险评估
- [ ] 说明此处用于 API Key 加密而非密码存储，固定 salt 在单管理员系统中风险可控

### 第 1 轮验证

- [ ] `ruff check . && ruff format --check . && pyright && pytest`
- [ ] git commit

---

## 第 2 轮 — 测试质量改进

> 包含：I-21, I-22, I-28, I-35, I-36, I-37, I-42, I-45, I-46, I-47

### 2.1 I-28: fixture 用绝对路径

**文件：** `tests/test_analyzer.py`, `tests/test_translator.py`

- [ ] 将 `"tests/fixtures/..."` 改为 `Path(__file__).parent / "fixtures" / ...`

### 2.2 I-37: conftest dependency_overrides 精确清理

**文件：** `tests/conftest.py`

- [ ] 将 `app.dependency_overrides.clear()` 改为只清除自己设置的覆盖（`app.dependency_overrides.pop(get_db, None)`）

### 2.3 I-45: 断言改为相对比较

**文件：** `tests/test_digest_service.py`

- [ ] 找到断言精确浮点数的测试用例
- [ ] 改为断言排序关系（`items[0].snapshot_heat_score >= items[1].snapshot_heat_score`）

### 2.4 I-46: heat_calculator 补充边界测试

**文件：** `tests/test_heat_calculator.py`

- [ ] 补充负值输入（负 likes、负 retweets）的测试
- [ ] 补充极大值输入的测试

### 2.5 I-47: 摘要降级路径测试

**文件：** `tests/test_digest_service.py`

- [ ] 补充 Claude 摘要生成失败时的降级测试
- [ ] 验证 digest.summary == DEFAULT_SUMMARY 且 summary_degraded 标记正确

### 2.6 I-22: auth 边界测试补充

**文件：** `tests/test_auth.py`

- [ ] 补充密码恰好 8 位的边界测试
- [ ] 补充 JWT payload 缺少 sub 字段的测试
- [ ] 补充 Authorization header 格式异常的测试

### 2.7 I-21: mock side_effect 改进（仅添加注释）

**文件：** `tests/test_process_service.py`

- [ ] 在 mock 设置处添加注释说明调用顺序依赖及其原因
- [ ] 实际重构 mock 机制影响面较大，暂不修改

### 2.8 I-35: claude_client 测试 mock 注入（仅添加注释）

**文件：** `tests/test_claude_client.py`

- [ ] 在直接修改 _client 属性处添加注释说明此做法的局限性

### 2.9 I-36: fetch_service 退避验证（仅添加注释）

**文件：** `tests/test_fetch_service.py`

- [ ] 在重试测试处添加注释说明未验证退避时间

### 2.10 I-42: settings_api mock 层次（仅添加注释）

**文件：** `tests/test_settings_api.py`

- [ ] 在 mock 设置处添加注释说明测试实现而非行为的局限性

### 第 2 轮验证

- [ ] `pytest`
- [ ] git commit

---

## 第 3 轮 — 后端路由层修复

> 包含：I-32, I-41, I-50

### 3.1 I-32: DailyDigest ORM 防止 preview_token 泄露

**文件：** `app/schemas/digest_types.py`

- [ ] 在 DigestBriefResponse 添加注释说明 from_attributes 不会映射 Schema 未声明的字段
- [ ] 确认 preview_token 不在任何响应 Schema 中

### 3.2 I-41: get_today_digest 路由业务逻辑下沉

**文件：** `app/api/digest.py`

- [ ] 读取 get_today_digest 路由代码
- [ ] 将 safe_int_config / get_system_config 调用移到 DigestService 方法中
- [ ] 路由层只做数据透传

### 3.3 I-50: add_tweet TOCTOU 竞态文档化

**文件：** `app/api/digest.py`

- [ ] 在 add_tweet 路由中添加注释说明 TOCTOU 风险和缓解措施
- [ ] 说明 SQLite WAL 模式下串行化写入降低了实际风险
- [ ] 标记为迁移 PostgreSQL 后需要用 SELECT FOR UPDATE 修复

### 第 3 轮验证

- [ ] `ruff check . && ruff format --check . && pyright && pytest`
- [ ] git commit

---

## 第 4 轮 — 前端修复

> 包含：I-20, I-24, I-34, I-39, I-48, I-49

### 4.1 I-20: PerspectiveItem 手写重复

**文件：** `admin/src/utils/digest.ts`

- [ ] 读取当前 PerspectiveItem 定义
- [ ] 检查 OpenAPI 生成类型中是否有对应类型
- [ ] 如有则替换；如无则添加注释说明需要与后端 processor_types.py 保持同步

### 4.2 I-24: setup 守卫非 401 错误处理

**文件：** `admin/src/router/index.ts`

- [ ] 读取 beforeEach 守卫中 setup 检查的 catch 块
- [ ] 对非 401 错误增加处理：至少检查 token 有效性再决定放行

### 4.3 I-34: api.post 添加响应类型

**文件：** `admin/src/views/Digest.vue`, `admin/src/views/DigestEdit.vue`

- [ ] 先读取 packages/openapi-client/src/gen/types.gen.ts 确认可用类型
- [ ] 为 api.post 调用添加泛型类型标注（如 MessageResponse）

### 4.4 I-39: Settings before-close 时序修复

**文件：** `admin/src/views/Settings.vue`

- [ ] 读取密钥弹窗的 before-close 逻辑
- [ ] 修复时序问题：在 before-close 中接管整个确认逻辑，或在 saveSecret 中手动控制弹窗关闭

### 4.5 I-48: History 错误提示改进

**文件：** `admin/src/views/History.vue`

- [ ] 区分首次加载错误和翻页错误
- [ ] 翻页失败使用 toast 提示而非 van-empty

### 4.6 I-49: 401 处理 setTimeout 改进

**文件：** `admin/src/api/index.ts`

- [ ] 读取 401 处理逻辑
- [ ] 改用路由 afterEach 监听成功导航到 /login 后重置标志，替代固定 setTimeout

### 第 4 轮验证

- [ ] `cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build`
- [ ] git commit

---

## 执行结果

### 交付物清单

**后端（第 1+3 轮）：** lock_service.py, dashboard.py, processor_types.py, publisher_types.py, fetcher_types.py, crypto.py, digest_types.py, digest_service.py, digest.py

**测试（第 2 轮）：** test_analyzer.py, test_translator.py, conftest.py, test_digest_service.py, test_heat_calculator.py, test_auth.py, test_process_service.py, test_claude_client.py, test_fetch_service.py, test_settings_api.py

**前端（第 4 轮）：** digest.ts, router/index.ts, Digest.vue, DigestEdit.vue, Settings.vue, History.vue, api/index.ts

### 偏离项表格

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| I-4 | 结构化 JSON 字段 | SKIPPED | 需 Schema 重构，影响面过大 |
| I-8 | 生成 SDK 客户端 | SKIPPED | 需全前端重构 API 调用 |
| I-12 | 统一错误响应模型 | SKIPPED | 影响 OpenAPI 生成链路 |
| I-23+I-38 | 改用 naive datetime | 保持 aware datetime + 注释 | 实测 aware 是正确的一致格式 |
| I-21,I-35,I-36,I-42 | 重构 mock | 仅添加注释 | 重构影响面大，文档化局限性 |

### 质量门禁详表

| 门禁 | 结果 |
|------|------|
| ruff check | All checks passed |
| ruff format | 151 files formatted |
| pyright | 0 errors |
| pytest | 599 passed (135.99s) |
| biome check | 通过 |
| vue-tsc | 通过 |
| build | ok (947ms) |
| CI | ✅ 全绿 |

### PR 链接

https://github.com/neuer/zhixi/pull/41
