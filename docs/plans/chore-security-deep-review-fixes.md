# 安全深度审查修复实施计划

> **执行指引：** 使用 deep-review skill 按轮次逐步执行。步骤使用 checkbox (`- [ ]`) 语法追踪进度。

**目标：** 修复全项目 D1-D7 七维度审查发现的 4 个 Critical + 20 个 Important + 5 个 Suggestion 问题

**审查模式：** 全量

**技术栈：** FastAPI + Python 3.12 + 异步 SQLAlchemy 2.x + aiosqlite + Vue 3 + TypeScript + Vant 4

**分支命名：** `chore/security-deep-review-fixes`

**分批策略：** 一次性（29 个问题 ≤ 30 阈值）

---

## 文件结构地图

| 操作 | 文件路径 | 职责 | 涉及问题 |
|------|---------|------|---------|
| 修改 | `app/main.py` | 全局异常处理器 | I-1 |
| 修改 | `app/auth.py` | bcrypt、JWT | I-4 |
| 修改 | `app/clients/notifier.py` | Webhook SSRF 校验 | I-2 |
| 修改 | `docker-compose.yml` | 端口暴露 | I-3 |
| 修改 | `app/api/dashboard.py` | 日期类型、7天范围、日志 | C-1, C-2, I-5 |
| 修改 | `admin/src/views/Logs.vue` | 日志分页 offset | I-5 |
| 修改 | `app/models/digest.py` | ORM 枚举 | I-14 |
| 修改 | `app/models/job_run.py` | ORM 枚举 | I-14 |
| 修改 | `app/models/digest_item.py` | ORM 枚举 | I-14 |
| 修改 | `app/models/tweet.py` | ORM 枚举 | I-14 |
| 修改 | `app/models/topic.py` | ORM 枚举 | I-14 |
| 修改 | `app/models/api_cost_log.py` | ORM 枚举 | I-14 |
| 修改 | `app/services/lock_service.py` | 移除 typing.Any | I-15 |
| 修改 | `app/schemas/fetcher_types.py` | Literal 收窄 | I-16 |
| 修改 | `app/schemas/dashboard_types.py` | Literal 收窄 | I-16 |
| 修改 | `app/schemas/settings_types.py` | Literal/枚举统一 | I-16 |
| 修改 | `app/api/digest.py` | 路径参数枚举、响应 schema、异常处理器 | I-17, I-18, S-2 |
| 修改 | `app/api/manual.py` | 响应 schema | I-18 |
| 修改 | `app/processor/merger_prompts.py` | 移除重复安全声明 | I-19 |
| 修改 | `admin/src/components/ArticlePreview.vue` | parsePerspectives 修复 | I-20 |
| 修改 | `app/digest/renderer.py` | JSON 解析日志 | C-3 |
| 修改 | `app/services/process_service.py` | 失败率告警、IndexError | C-4, I-10 |
| 修改 | `app/processor/json_validator.py` | 括号补全顺序 | I-6 |
| 修改 | `admin/src/views/Digest.vue` | item_ref_id | I-7 |
| 修改 | `app/api/settings.py` | _parse_int_list | I-8 |
| 修改 | `app/services/digest_service.py` | is_current 清理 | I-9 |
| 修改 | `app/fetcher/x_api.py` | 解析失败聚合 | I-11 |
| 修改 | `app/services/pipeline_service.py` | 通知失败日志级别 | I-12 |
| 修改 | `app/digest/cover_generator.py` | 降级日志 | I-13 |
| 修改 | `app/crud.py` | TODO 更新 | S-1 |
| 修改 | `app/services/publish_service.py` | TODO 更新 | S-1 |
| 修改 | `app/services/notification_service.py` | TODO 更新 | S-1 |
| 修改 | `app/schemas/report_types.py` | TODO 更新 | S-1 |
| 修改 | `admin/src/router/index.ts` | Token 过期检查 | S-7 |
| 修改 | `app/services/fetch_service.py` | re.search | S-8 |

---

## 问题总表

| 编号 | 维度 | 置信度 | 文件 | 摘要 |
|------|------|--------|------|------|
| C-1 | D1 | 85 | dashboard.py:315 | `started_at` 与 `date` 类型比较，SQLite 行为不确定 |
| C-2 | D1 | 90 | dashboard.py:268 | 近 7 天查询实际只覆盖 6 天 |
| C-3 | D2 | 90 | renderer.py:169 | JSON 解析失败静默 pass，丢失内容无感知 |
| C-4 | D2 | 88 | process_service.py:419-516 | AI 加工失败率无阈值告警，低质量日报无感知 |
| I-1 | D7 | 90 | main.py:69-89 | 异常处理器泄露内部异常信息给客户端 |
| I-2 | D7 | 85 | notifier.py:41 | Webhook URL 无 SSRF 校验 |
| I-3 | D7 | 85 | docker-compose.yml:8 | 8000 端口直接暴露，可绕过 Caddy HTTPS |
| I-4 | D7 | 95 | auth.py:32 | bcrypt gensalt 未显式指定 rounds=12 |
| I-5 | D1 | 90 | dashboard.py:128 + Logs.vue:43 | 前端传 offset 但后端不支持，分页无效 |
| I-6 | D1 | 75 | json_validator.py:111 | 括号补全顺序错误（先 ] 再 }，应反转） |
| I-7 | D1 | 85 | Digest.vue:160 | 路由传 item.id 而非 item_ref_id |
| I-8 | D1 | 75 | settings.py:64 | _parse_int_list 未处理非数字导致 500 |
| I-9 | D1 | 85 | digest_service.py:54 | generate_daily_digest 未清理旧版本 is_current |
| I-10 | D1 | 75 | process_service.py:643 | _build_thread_data 空列表 IndexError |
| I-11 | D2 | 82 | x_api.py:118 | 推文解析失败未聚合，全部失败无告警 |
| I-12 | D2 | 70 | pipeline_service.py:129 | Pipeline 失败+通知失败=双重静默 |
| I-13 | D2 | 82 | cover_generator.py:138 | 封面生成降级管理员无感知 |
| I-14 | D3 | 95 | 6 个 models/*.py | ORM 模型用裸字符串而非已定义枚举 |
| I-15 | D3 | 90 | lock_service.py:5 | 使用 typing.Any（项目禁止） |
| I-16 | D3 | 85 | 3 个 schemas/*.py | Schema str 字段应用 Literal/枚举收窄 |
| I-17 | D3 | 85 | digest.py:176 | 路由路径参数 item_type 未用枚举约束 |
| I-18 | D3 | 80 | digest.py:296, manual.py:33 | 成功响应缺 Pydantic schema |
| I-19 | D1 | 85 | merger_prompts.py:12 | DEDUP_PROMPT 手动写安全声明与自动注入重复 |
| I-20 | D5 | 80 | ArticlePreview.vue:17 | parsePerspectives 过滤逻辑与后端数据格式不匹配 |
| S-1 | D5 | 90 | 4 个文件 | "TODO: Phase 2" 标记过时 |
| S-2 | D6 | 85 | digest.py | 5 处重复 try-except 应提为全局异常处理器 |
| S-7 | D7 | 80 | router/index.ts:115 | 前端路由守卫不检查 token 过期 |
| S-8 | D1 | 80 | fetch_service.py:37 | re.match 无法匹配含前缀文本的 URL |
| S-3 | D6 | 85 | digest_types.py | SettingsUpdate.publish_mode Literal 与枚举不一致 |

---

## 第 1 轮 — 安全修复

> 目标：修复安全相关问题，降低攻击面
> 包含问题：I-1, I-2, I-3, I-4

### 1.1 I-1: 异常处理器泄露内部异常信息

**文件：** `app/main.py:69-89`

- [ ] **Step 1: 修复异常处理器，移除 exc 详情**

将三个异常处理器的 detail 改为固定中文消息，不包含 `{exc}`。

- [ ] **Step 2: 验证**
```bash
pytest tests/test_api.py -v -x
```

### 1.2 I-2: Webhook URL 无 SSRF 校验

**文件：** `app/clients/notifier.py`

- [ ] **Step 1: 添加 URL 校验函数**

在 `notifier.py` 中添加 `_validate_webhook_url` 函数，禁止内网 IP 和 loopback 地址。

- [ ] **Step 2: 在 send_alert 中调用校验**

校验失败时记录 error 日志并返回 False。

- [ ] **Step 3: 验证**
```bash
pytest tests/test_notifier.py -v -x
```

### 1.3 I-3: docker-compose 暴露 8000 端口

**文件：** `docker-compose.yml`

- [ ] **Step 1: 将 ports 改为 expose**

`web` 服务的 `ports: - "8000:8000"` 改为 `expose: - "8000"`。

### 1.4 I-4: bcrypt salt rounds 显式指定

**文件：** `app/auth.py:32`

- [ ] **Step 1: 添加 rounds=12 参数**

`bcrypt.gensalt()` → `bcrypt.gensalt(rounds=12)`

- [ ] **Step 2: 验证**
```bash
pytest tests/test_auth.py -v -x
```

### 第 1 轮验证

- [ ] **运行后端门禁**
```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **提交**
```bash
git add app/main.py app/clients/notifier.py docker-compose.yml app/auth.py
git commit -m "fix(security): 修复异常信息泄露、SSRF、端口暴露、bcrypt rounds (I-1~I-4)"
```

---

## 第 2 轮 — Dashboard 关键 bug

> 目标：修复 Dashboard 数据展示的 Critical bug
> 包含问题：C-1, C-2, I-5

### 2.1 C-1 + C-2: 日期类型和范围修复

**文件：** `app/api/dashboard.py`

- [ ] **Step 1: 修复 _get_alerts 日期类型**

第 307 行 `since = today - timedelta(days=7)` 改为 `datetime` 类型：
```python
since = datetime(today.year, today.month, today.day, tzinfo=UTC) - timedelta(days=7)
```

- [ ] **Step 2: 修复 _recent_7_days 范围**

第 264 行改为 `since = today - timedelta(days=6)` 或用 `>=`，使近 7 天查询覆盖完整 6 天（加今日独立展示共 7 天）。

### 2.2 I-5: 日志 offset 支持

**文件：** `app/api/dashboard.py` + `admin/src/views/Logs.vue`

- [ ] **Step 1: 后端添加 offset 参数**

`get_logs` 路由添加 `offset: int = Query(default=0, ge=0)` 参数，在遍历日志行时跳过前 offset 条匹配记录。

- [ ] **Step 2: 验证**
```bash
pytest tests/test_dashboard_api.py -v -x
```

### 第 2 轮验证

- [ ] **运行门禁**
```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **提交**
```bash
git add app/api/dashboard.py admin/src/views/Logs.vue
git commit -m "fix(dashboard): 修复日期类型、7天范围、日志分页 (C-1, C-2, I-5)"
```

---

## 第 3 轮 — ORM 枚举迁移（系统性）

> 目标：将 ORM 模型的 str 列迁移为枚举类型，收窄不变量
> 包含问题：I-14, I-15, I-16, I-17, I-18, I-19, S-3

### 3.1 I-14: ORM 模型枚举迁移

**文件：** 6 个 models 文件

- [ ] **Step 1: 修改 DailyDigest 模型**

`app/models/digest.py`: `status: Mapped[str]` → 保持 `Mapped[str]`（SQLite 存储仍为字符串），但在赋值和比较时全部使用枚举。关键是将全项目的裸字符串替换为枚举成员引用。

注意：ORM 列类型不改（SQLite 不支持原生 enum），但所有业务代码中的赋值和比较改用枚举。

- [ ] **Step 2: 全项目替换裸字符串为枚举**

在 `app/services/`, `app/api/`, `app/models/` 中，将所有 `status="draft"` → `status=DigestStatus.DRAFT`、`job_type="pipeline"` → `job_type=JobType.PIPELINE` 等。

- [ ] **Step 3: 修改 ORM 模型 default 值为枚举**

如 `default="draft"` → `default=DigestStatus.DRAFT`。

### 3.2 I-15: 移除 lock_service.py 的 typing.Any

**文件：** `app/services/lock_service.py`

- [ ] **Step 1: 替换 Any 为精确类型**

`cast("CursorResult[Any]", result)` → `result.rowcount`（直接使用，或 `# type: ignore[union-attr]`）。

### 3.3 I-16: Schema Literal 收窄

**文件：** `app/schemas/fetcher_types.py`, `dashboard_types.py`, `settings_types.py`

- [ ] **Step 1: ReferencedTweet.type 用 Literal**

`type: str` → `type: Literal["retweeted", "quoted", "replied_to"]`

- [ ] **Step 2: LogEntry.level 用 Literal**

`level: str` → `level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]`

- [ ] **Step 3: ApiStatusItem.status 用 Literal**

`status: str` → `status: Literal["ok", "error", "unconfigured"]`

- [ ] **Step 4: ServiceCostItem.service 用 ServiceType**
- [ ] **Step 5: SettingsUpdate.publish_mode 统一为枚举 (S-3)**

### 3.4 I-17: 路由路径参数枚举

**文件：** `app/api/digest.py`

- [ ] **Step 1: edit_item/exclude_item/restore_item 的 item_type 参数改为 ItemType**

### 3.5 I-18: 响应 Schema 定义

**文件：** `app/api/digest.py`, `app/api/manual.py`

- [ ] **Step 1: 定义 RegenerateResponse、FetchResponse、CoverResponse**

在 `app/schemas/digest_types.py` 和 `app/schemas/pipeline_types.py` 中添加响应模型。

- [ ] **Step 2: 路由使用新 response_model**

### 3.6 I-19: 移除 DEDUP_PROMPT 重复安全声明

**文件：** `app/processor/merger_prompts.py`

- [ ] **Step 1: 删除 DEDUP_PROMPT 开头手动安全声明**

ClaudeClient.complete 已自动注入 SAFETY_PREFIX。

### 第 3 轮验证

- [ ] **运行门禁**
```bash
ruff check . && ruff format --check . && pyright && pytest
```

- [ ] **提交**
```bash
git add app/models/ app/services/ app/api/ app/schemas/ app/processor/merger_prompts.py
git commit -m "refactor(types): ORM 枚举迁移 + Schema Literal 收窄 + 响应模型 (I-14~I-19, S-3)"
```

---

## 第 4 轮 — 代码 bug 与静默失败

> 目标：修复 Critical 静默失败和各类代码 bug
> 包含问题：C-3, C-4, I-6, I-7, I-8, I-9, I-10, I-11, I-12, I-13, I-20

### 4.1 C-3: renderer.py JSON 解析添加日志

**文件：** `app/digest/renderer.py:169-179`

- [ ] **Step 1: 在 except 块中添加 warning 日志**

```python
except (json.JSONDecodeError, TypeError):
    logger.warning("JSON 数组解析失败，返回空列表: %s", json_str[:200])
```

### 4.2 C-4: AI 加工失败率告警

**文件：** `app/services/process_service.py`

- [ ] **Step 1: 在 run_daily_process 返回前添加失败率检查**

当 failed_count / total > 0.3 时记录 error 日志。

### 4.3 I-6: json_validator 括号补全顺序

**文件：** `app/processor/json_validator.py:111-122`

- [ ] **Step 1: 调整补全顺序为先 } 再 ]**

### 4.4 I-7: Digest.vue item_ref_id

**文件：** `admin/src/views/Digest.vue:160`

- [ ] **Step 1: `id: item.id` → `id: item.item_ref_id`**

### 4.5 I-8: _parse_int_list 防御

**文件：** `app/api/settings.py:64-65`

- [ ] **Step 1: 添加 try/except ValueError**

### 4.6 I-9: generate_daily_digest 清理旧 is_current

**文件：** `app/services/digest_service.py`

- [ ] **Step 1: 创建新 digest 前清理同日旧版本**

```python
await self._db.execute(
    update(DailyDigest)
    .where(DailyDigest.digest_date == digest_date, DailyDigest.is_current.is_(True))
    .values(is_current=False)
)
```

### 4.7 I-10: _build_thread_data 空列表防御

**文件：** `app/services/process_service.py:643`

- [ ] **Step 1: 添加空列表检查**

```python
if not member_tweets:
    raise ValueError("Thread 成员推文列表为空")
```

### 4.8 I-11: X API 解析失败聚合

**文件：** `app/fetcher/x_api.py`

- [ ] **Step 1: 在 fetch_user_tweets 循环中统计解析失败数**

全部失败时记录 error。

### 4.9 I-12: Pipeline 通知失败提升日志级别

**文件：** `app/services/pipeline_service.py:129-136`

- [ ] **Step 1: 通知 except 块日志从 warning 改为 error**

### 4.10 I-13: 封面降级日志

**文件：** `app/digest/cover_generator.py` 或 `app/services/digest_service.py`

- [ ] **Step 1: 封面为 None 且 enable_cover=true 时记录 warning**

### 4.11 I-20: ArticlePreview parsePerspectives 修复

**文件：** `admin/src/components/ArticlePreview.vue:17-28`

- [ ] **Step 1: 修改类型和过滤逻辑支持对象数组**

后端 perspectives 格式为 `[{author, handle, viewpoint}]`，不是 `string[]`。

### 第 4 轮验证

- [ ] **运行门禁**
```bash
ruff check . && ruff format --check . && pyright && pytest
cd admin && bunx biome check . && bunx vue-tsc --noEmit
```

- [ ] **提交**
```bash
git add app/ admin/src/
git commit -m "fix: 修复静默失败、JSON解析、括号补全、枚举路由等 bug (C-3, C-4, I-6~I-13, I-20)"
```

---

## 第 5 轮 — Suggestions

> 目标：处理建议级改进
> 包含问题：S-1, S-2, S-7, S-8

### 5.1 S-1: 更新过时 TODO 标记

**文件：** `app/crud.py`, `app/services/publish_service.py`, `app/services/notification_service.py`, `app/schemas/report_types.py`

- [ ] **Step 1: 更新 4 个文件的 TODO 注释**

### 5.2 S-2: Digest 路由异常提为全局处理器

**文件：** `app/main.py`, `app/api/digest.py`

- [ ] **Step 1: 在 main.py 注册 DigestNotFoundError/DigestNotEditableError/DigestItemNotFoundError 处理器**
- [ ] **Step 2: 删除 digest.py 中 5 处重复的 try-except**

### 5.3 S-7: 前端路由守卫检查 token 过期

**文件：** `admin/src/router/index.ts`

- [ ] **Step 1: 添加 isTokenValid 函数解析 JWT exp**
- [ ] **Step 2: 路由守卫调用 isTokenValid**

### 5.4 S-8: _parse_tweet_id re.match → re.search

**文件：** `app/services/fetch_service.py:37,43`

- [ ] **Step 1: `re.match` → `_TWEET_URL_PATTERN.search`**

### 第 5 轮验证

- [ ] **运行全部门禁**
```bash
ruff check . && ruff format --check . && pyright && pytest
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交**
```bash
git add app/ admin/src/
git commit -m "chore: 更新过时TODO、提取全局异常处理器、前端token过期检查 (S-1, S-2, S-7, S-8)"
```

---

## 延迟项（不在本次修复范围，记录到 PR 描述）

以下问题需要较大架构变更，建议在后续迭代中处理：

| 编号 | 问题 | 原因 |
|------|------|------|
| D7-4 | JWT 改为 HttpOnly cookie | 需要前后端认证流程全面重构 |
| D7-5 | 登录限流器持久化 | MVP 单实例可接受，Phase 2 评估 |
| D7-6 | JWT 吊销机制（黑名单） | 需要新增 DB 表和中间件 |
| D6-1 | 提取通用重试辅助函数 | 纯重构，不影响功能 |
| D6-2 | 提取 digest+items 查询方法 | 纯重构，不影响功能 |
| D1-11 | backup_service 异步化 | MVP CLI 场景影响小 |
| D1-16 | get_logs 流式读取大文件 | 性能优化，非安全问题 |

---

## 执行结果

### 交付物清单

修改 40 个文件，+900 / -188 行：

| 类别 | 文件 | 说明 |
|------|------|------|
| 安全 | `app/main.py` | 异常处理器移除内部详情 + 新增 Digest 全局异常处理器 |
| 安全 | `app/clients/notifier.py` | 新增 SSRF 校验函数 |
| 安全 | `docker-compose.yml` | ports→expose |
| 安全 | `app/auth.py` | bcrypt rounds=12 |
| Dashboard | `app/api/dashboard.py` | 日期类型修复 + 7天范围 + offset 支持 |
| Dashboard | `app/schemas/dashboard_types.py` | LogsResponse.total + LogEntry.level Literal |
| 枚举 | `app/models/*.py` (3 files) | ORM default 改用枚举 |
| 枚举 | `app/services/*.py` (7 files) | 全量裸字符串→枚举替换 |
| 枚举 | `app/api/*.py` (4 files) | 路由参数枚举 + 响应 Schema |
| 枚举 | `app/schemas/*.py` (4 files) | Literal 收窄 + 响应模型定义 |
| Bug | `app/digest/renderer.py` | JSON 解析日志 |
| Bug | `app/processor/merger_prompts.py` | 移除重复安全声明 |
| Bug | `app/fetcher/x_api.py` | 解析失败聚合告警 |
| Bug | `app/services/process_service.py` | 失败率告警 + 空列表防御 |
| Bug | `app/services/digest_service.py` | is_current 清理 + 封面降级日志 |
| 前端 | `admin/src/components/ArticlePreview.vue` | parsePerspectives 对象数组支持 |
| 前端 | `admin/src/views/Digest.vue` | item_ref_id |
| 前端 | `admin/src/router/index.ts` | JWT 过期检查 |
| 生成 | `packages/openapi-client/src/gen/types.gen.ts` | OpenAPI 类型更新 |
| 测试 | `tests/test_accounts.py`, `tests/test_error_handling.py` | 适配安全修复 |

### 偏离项表格

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| I-6 | 调整括号补全顺序（先}再]） | 保持原顺序不变 | 实施 agent 验证后确认原顺序正确：内层 ] 应先关闭，现有测试验证了此行为 |
| I-16 | ReferencedTweet.type 收窄为 Literal | 保持 str | X API 可能返回 "mentioned"/"pinned" 等值，Literal 会导致运行时校验失败 |
| — | — | 更新 test_accounts.py | 适配 I-1 异常处理器安全修复 |
| — | — | 更新 test_error_handling.py | 适配 I-1 异常处理器安全修复 |
| — | — | 更新 OpenAPI 生成物 | I-16/I-18 Schema 变更触发生成物更新 |

### 问题与修复记录

1. **I-1 导致 2 个测试失败**：测试断言了旧的异常消息格式（含内部详情），修复后测试需要适配新的固定消息。已在第 1 轮提交后发现并修复。
2. **CI 生成物过期**：I-16 的 Literal 收窄和 I-18 的响应 Schema 变更了 OpenAPI 输出，需要 `make gen` 更新前端类型。CI 第 1 轮失败，第 2 轮自动修复通过。
3. **I-6 括号顺序**：计划复核已指出描述不够明确，实施 agent 验证后确认原有逻辑正确，标记为不修改。

### 质量门禁详表

| 门禁 | 结果 |
|------|------|
| `ruff check .` | 0 errors |
| `ruff format --check .` | 0 errors |
| `pyright` | 0 errors |
| `pytest` | 537 passed |
| `vue-tsc --noEmit` | 0 errors |
| `biome check .` | 通过 |
| `bun run build` | 通过 |
| `make gen && git diff --exit-code` | 通过（CI 验证） |
| GitHub Actions CI | 全绿（backend ✓ / frontend ✓ / codegen ✓） |

### PR 链接
https://github.com/neuer/zhixi/pull/33
