# US-050 + US-051 实施计划：API 接口测试 + 状态流转测试

## Context

P3 阶段后端 API 全部实现完成，需要补充两组关键测试：
- US-050：综合 API 接口测试（认证、CRUD、权限、锁互斥）
- US-051：Digest 状态流转测试（draft/published/failed 间的流转链路）

现有 37 个测试文件已分散覆盖各 API 基本功能。US-050/051 的增量价值在于**跨模块集成视角**和**完整状态流转链路验证**。

## 新增文件

| 文件 | US | 说明 |
|------|-----|------|
| `tests/test_api.py` | US-050 | 综合 API 接口测试 |
| `tests/test_state_transition.py` | US-051 | 状态流转测试 |

## US-050：`tests/test_api.py`

### 测试结构

```
tests/test_api.py
├── _seed_config()
├── _seed_draft_with_items()
├── _create_running_pipeline()
├── TestUnauthedEndpoints         # 参数化：所有受保护端点 → 401
├── TestPublicEndpoints           # setup/login/logout 不需要 JWT
├── TestSetupLoginFlow            # 端到端：setup → login → 获取 token
├── TestDigestCRUD                # 查看 + 编辑 + 排序 + 剔除 + 恢复 综合
├── TestPermission409             # published 状态下所有编辑操作 → 409
└── TestLockMutex409              # pipeline running 时 regenerate/publish/fetch → 409
```

### 关键用例

**TestUnauthedEndpoints（参数化 ~18 个端点）**：
- `@pytest.mark.parametrize("method,url,body", [...])` 一个方法覆盖所有受保护端点
- 用无认证 `client` fixture

**TestPublicEndpoints（3 个）**：
- setup/status 200、auth/login 不需 JWT、auth/logout 200

**TestSetupLoginFlow（2 个）**：
- setup → login → 用 token 访问 accounts → 200
- setup 后重复 init → 403

**TestDigestCRUD（4 个）**：
- today + edit → markdown 包含编辑内容
- reorder → today items 顺序正确
- exclude → today 中 is_excluded=true
- summary 编辑 → markdown 包含新摘要

**TestPermission409（1 个参数化）**：
- published digest + 参数化 4 种操作 → 均返回 409

**TestLockMutex409（3 个）**：
- pipeline running → regenerate/mark-published/manual-fetch 均 409

### Mock 策略

- 日期：`@freeze_time("2026-03-20 08:00:00+08:00")` + 按需 `@patch`
- 锁测试：创建 `JobRun(job_type="pipeline", status="running")`
- 不需 mock Claude/X API

## US-051：`tests/test_state_transition.py`

### 测试结构

```
tests/test_state_transition.py
├── _seed_draft(db, version, status) -> DailyDigest
├── _seed_draft_with_items(db, version, status) -> (DailyDigest, list[DigestItem])
├── _mock_regenerate_success() -> context manager
├── _verify_digest(db, digest_date, version) -> DailyDigest
├── TestDraftToPublished            # 2 个
├── TestDraftRegenerateV2           # 3 个
├── TestPublishedRegenerateNewDraft # 2 个
├── TestFailedRegenerateNewDraft    # 2 个
├── TestFailedRetryPublish          # 2 个
├── TestPublishedNoEdit             # 1 个参数化
├── TestIsCurrentSwitch             # 3 个
└── TestRegenerateFailureRollback   # 2 个
```

### 用例清单

| 验收标准 | 测试类 | 用例数 |
|----------|--------|--------|
| draft→published | TestDraftToPublished | 2 |
| draft→regenerate→v2 | TestDraftRegenerateV2 | 3 |
| published后regenerate→new draft | TestPublishedRegenerateNewDraft | 2 |
| failed→regenerate→new draft | TestFailedRegenerateNewDraft | 2 |
| failed→重试发布→published | TestFailedRetryPublish | 2 |
| 已published不可修改 | TestPublishedNoEdit | 1 参数化 |
| is_current 切换正确 | TestIsCurrentSwitch | 3 |
| regenerate 失败回滚 | TestRegenerateFailureRollback | 2 |

### Regenerate Mock 策略

复用 `test_regenerate_api.py` 模式：
- `patch("app.api.digest.DigestService")` + `patch("app.api.digest.get_claude_client")`
- regenerate 前手动在 DB 中设置预期的 is_current 状态
- 失败回滚的 is_current 恢复由 Service 层测试保证，API 层验证 500 + job_run failed

### DB 验证

统一用 `select()` 查询（不用 `refresh()`）。

## 执行顺序

1. 创建 `tests/test_api.py` + 运行确认
2. 创建 `tests/test_state_transition.py` + 运行确认
3. 全量质量门禁

## 关键参考文件

- `tests/conftest.py` — fixtures
- `tests/test_regenerate_api.py` — regenerate mock 模式
- `tests/test_digest_edit_api.py` — 数据预置模式
- `tests/test_publish_api.py` — mark-published 测试模式
- `app/api/digest.py` — 全部 digest 路由实现

## 执行结果

### 交付物清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `tests/test_api.py` | 新增 | ~400 |
| `tests/test_state_transition.py` | 新增 | ~580 |
| `docs/spec/user-stories.md` | 修改 | 2 |
| `docs/plans/us-050-051-api-state-tests.md` | 新增 | ~160 |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 无 | — | — | 完全按计划执行 |

### 问题与修复

| 问题 | 解决 |
|------|------|
| main 上有 12 个预存测试失败（test_digest_edit_api.py + test_lock_service.py） | 确认为预存问题，本轮不引入新失败 |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 125 files already formatted |
| pyright | ✅ 0 errors, 0 warnings |
| pytest (新增) | ✅ 55/55 passed (test_api: 34, test_state_transition: 21) |
| pytest (全量) | ✅ 436 passed, 12 pre-existing failures |

### PR 链接

https://github.com/neuer/zhixi/pull/21
