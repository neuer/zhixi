# 全栈深度审查修复实施计划 — Batch 3

> **执行指引：** Suggestion 级别修复，以注释文档化、小幅代码改进为主。

**目标：** 修复 27 个 Suggestion 问题（4 个 SKIPPED）

**分支命名：** `chore/full-project-deep-review-fixes-b3`

---

## SKIPPED

| 编号 | 原因 |
|------|------|
| S-3 | 需后端枚举化 + OpenAPI 重生成，影响面大 |
| S-9 | openapi.json 纳入版本控制属工程决策，需团队讨论 |
| S-15 | 降级持久化需新增 DB 字段 + 迁移 |
| S-18 | DigestBriefResponse 移除 content_markdown 需前端适配 |

---

## 第 1 轮 — 后端注释与文档化修复

> S-1, S-2, S-5, S-6, S-7, S-10, S-11, S-13, S-17, S-23, S-24, S-25, S-26, S-28

- [ ] **S-1:** `app/fetcher/x_api.py:7` — docstring 中 `_enrich_tweet_text` 改为 `enrich_tweet_text`
- [ ] **S-2:** `app/auth.py:104` — 在限流器处添加注释说明无递增退避和多 worker 局限性
- [ ] **S-5:** `app/api/settings.py:66` — `_get_db_size_mb` 改用 `await asyncio.to_thread(...)` 包装
- [ ] **S-6:** `app/schemas/dashboard_types.py:100` — `LogEntry.timestamp` 添加注释说明保持 str 的原因（日志文件时间戳格式不规范）
- [ ] **S-7:** `app/schemas/settings_types.py` + `app/schemas/debug_types.py` — 将重复的 `Literal["ok","error","unconfigured"]` 提取到 `enums.py` 为共享类型 `HealthStatus`
- [ ] **S-10:** `app/api/manual.py:103` — docstring "无可编辑草稿" 改为 "当日草稿不存在"
- [ ] **S-11:** `app/api/manual.py:60` — 添加注释说明此处直接构造 FetchService 是因为需要与其他 Service 共享同一 db session
- [ ] **S-13:** `app/schemas/auth_types.py:24` — `LoginRequest.username` 添加 `Field(min_length=1, max_length=50)`
- [ ] **S-17:** `app/services/pipeline_service.py:83` — 添加注释说明 CLI 入口不经过 FastAPI DI 系统
- [ ] **S-23:** `app/services/process_service.py:596` — 热度计算中 `member_scores` 改用预构建的 `tweets_by_topic` 索引（O(N+M)）
- [ ] **S-24:** `tests/test_process_service.py:434` — 硬编码 `"global_analysis"` 改用 `CallType.GLOBAL_ANALYSIS.value`
- [ ] **S-25:** `app/fetcher/x_api.py:5` — 补充注释说明 self-reply 在 exclude=replies 下的行为
- [ ] **S-26:** `app/main.py:138` — SPA fallback 路由上方添加"必须最后注册"注释
- [ ] **S-28:** `tests/factories.py:280` — `twitter_handle` 添加随机后缀或序号参数

### 第 1 轮验证
- [ ] `ruff check . && ruff format --check . && pyright && uv run pytest`
- [ ] git commit

---

## 第 2 轮 — 后端测试清理

> S-4, S-8, S-16

- [ ] **S-4:** `app/services/fetch_service.py:49` — `self.db` 改为 `self._db`，更新所有内部引用
- [ ] **S-8:** `tests/test_error_handling.py:29-51` — 删除与 `test_x_client.py` 重复的测试用例（`test_lookup_user_non_json_response` + `test_lookup_user_missing_id_field`）
- [ ] **S-16:** `tests/test_claude_client.py:97` — 添加注释说明验证内部调用参数的设计选择

### 第 2 轮验证
- [ ] `ruff check . && ruff format --check . && pyright && uv run pytest`
- [ ] git commit

---

## 第 3 轮 — 前端修复

> S-12, S-14, S-19, S-20, S-21, S-22, S-27, S-29, S-30, S-31

- [ ] **S-12:** `admin/src/views/Logs.vue:40` — `isLoadingMore` 改为注释说明用 let 的原因（仅做并发锁，不需要响应性）
- [ ] **S-14:** `admin/src/views/Logs.vue:12` — `LogEntry` 重命名为 `LogEntryWithUid`
- [ ] **S-19:** `admin/src/composables/useExperimentLog.ts:73` — clipboard 添加 `.catch(() => showToast("复制失败"))`
- [ ] **S-20:** `admin/src/schemas/account_types.py` — 添加注释说明当前阶段 AccountResponse 无需差异化
- [ ] **S-21:** `admin/src/composables/useApiStatus.ts:40` — `getApiStatus` 参数类型收窄为 `'ok' | 'error' | 'unconfigured'`
- [ ] **S-22:** `admin/src/utils/status.ts:31` — `getStatus` 参数类型收窄
- [ ] **S-27:** `admin/src/views/HistoryDetail.vue` — 在错误状态下添加"重新加载"按钮
- [ ] **S-29:** `admin/src/router/index.ts:91` — setupCache TTL 添加注释说明 5 分钟的选择理由
- [ ] **S-30:** `admin/src/components/AccountAddPopup.vue:62` — 添加注释说明手动模式下后端会跳过 X API 调用
- [ ] **S-31:** `admin/src/views/DigestEdit.vue:13` — route.params.type 添加类型校验

### 第 3 轮验证
- [ ] `cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build`
- [ ] git commit

---

## 执行结果

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| S-1 | 修改 docstring | 确认已正确，无需改动 | 之前轮次已修复 |
| S-3,S-9,S-15,S-18 | — | SKIPPED | 影响面大，需独立任务 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | All checks passed |
| ruff format | 151 files formatted |
| pyright | 0 errors |
| pytest | 597 passed |
| biome check | 通过 |
| vue-tsc | 通过 |
| build | ok |
| CI | ✅ 全绿 |

### PR 链接
https://github.com/neuer/zhixi/pull/42
