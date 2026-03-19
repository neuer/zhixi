# US-010: 大V账号管理（后端 API）

> **日期**: 2026-03-19
> **分支**: `us-010-accounts-api`
> **状态**: ✅ 已完成
> **范围**: 仅后端 API，跳过 JWT 认证（US-008）和前端（P2 补）

---

## Context

P0 阶段还剩 US-010/013/014/015 四个 US 待完成。US-013（每日自动抓取推文）依赖 US-010，必须先完成。
US-010 依赖 US-008（认证），但实施计划注明"可先做后端 API，前端 P2 补"。本轮仅实现后端 CRUD API。

---

## 文件清单

### 新建文件

| 文件 | 用途 |
|------|------|
| `app/schemas/account_types.py` | 账号相关 Pydantic 输入/输出模型 |
| `app/services/account_service.py` | 账号业务逻辑 Service |
| `app/clients/x_client.py` | X API 用户查询客户端 |
| `tests/test_accounts.py` | 账号 CRUD API 测试 |

### 修改文件

| 文件 | 变更 |
|------|------|
| `app/api/accounts.py` | 实现 4 个路由端点 |
| `app/api/deps.py` | 添加 `get_account_service` 依赖工厂 |

---

## 实现策略

### 1. Pydantic Schema (`app/schemas/account_types.py`)

- `AccountCreate`: twitter_handle(必填), weight(0.1-5.0, 默认1.0), display_name/bio/avatar_url(可选，非空触发手动模式)
- `AccountUpdate`: weight(0.1-5.0), is_active — 均可选，部分更新
- `AccountResponse`: 完整账号对象，`model_config = ConfigDict(from_attributes=True)` 支持 ORM 转换
- `AccountListResponse`: `{items, total, page, page_size}` 分页结构

### 2. X API 用户查询 (`app/clients/x_client.py`)

独立于 `XApiFetcher`（推文抓取），专门处理用户信息查询：
- 端点：`GET /2/users/by/username/{handle}?user.fields=profile_image_url,description,public_metrics`
- `httpx.AsyncClient`，超时 10s
- 返回 `XUserProfile` dataclass，失败抛 `XApiError`
- **为什么不放 XApiFetcher**：职责分离，XApiFetcher 只负责推文抓取

### 3. AccountService (`app/services/account_service.py`)

构造函数注入 `AsyncSession`，复用 BackupService DI 模式：
- `list_accounts(page, page_size, include_inactive)` — 默认只返回 is_active=True，分页
- `create_account(data)` — 去重检查 → X API 查询（或手动模式） → 入库
- `update_account(account_id, data)` — 部分更新 weight/is_active
- `delete_account(account_id)` — 软删除 is_active=false

创建逻辑：
1. handle 规范化：去除 `@` 前缀
2. 去重：查询 twitter_handle 是否已存在（含 inactive），已存在返回 409
3. 若 `display_name` 非空 → 跳过 X API，用提交的字段直接创建
4. 否则 → 调用 `x_client.lookup_user()` 拉取用户信息
5. X API 失败 → 抛异常，路由层转 502

### 4. API 路由 (`app/api/accounts.py`)

| 方法 | 路径 | 状态码 | 说明 |
|------|------|--------|------|
| GET | `/` | 200 | 分页列表，query: page, page_size |
| POST | `/` | 201 | 创建账号 |
| PUT | `/{account_id}` | 200 | 部分更新 |
| DELETE | `/{account_id}` | 200 | 软删除，返回 `{"message": "账号已删除"}` |

错误响应（中文）：
- 409 `{"detail": "该账号已存在"}`
- 502 `{"detail": "X API拉取失败", "allow_manual": true}`
- 404 `{"detail": "账号不存在"}`
- 422 Pydantic 自动校验

**Auth**: 暂不加 JWT，留 `# TODO: US-008 添加 Depends(get_current_admin)`

### 5. 依赖注入 (`app/api/deps.py`)

```python
async def get_account_service(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)
```

---

## 测试策略（TDD）

使用 `respx` mock X API，内存 SQLite 测试数据库（conftest.py 已有基础设施）。

| 测试用例 | 覆盖场景 |
|----------|---------|
| `test_list_accounts_empty` | 空列表 |
| `test_list_accounts_with_data` | 分页查询 |
| `test_list_accounts_excludes_inactive` | 默认不返回 inactive |
| `test_create_account_auto_fetch` | X API 自动拉取成功 → 201 |
| `test_create_account_manual_mode` | display_name 触发手动模式 → 201 |
| `test_create_account_x_api_failure` | X API 失败 → 502 |
| `test_create_account_duplicate` | 重复 handle → 409 |
| `test_create_account_strip_at` | 自动去除 @ 前缀 |
| `test_update_account_weight` | 更新权重 |
| `test_update_account_not_found` | 404 |
| `test_delete_account_soft` | 软删除验证 |
| `test_delete_account_not_found` | 404 |

---

## 关键决策

1. **X API 查询放 `app/clients/x_client.py`**：与推文抓取分离，职责清晰
2. **手动模式**：请求体包含 `display_name` 时跳过 X API
3. **handle 规范化**：去除 `@` 前缀，存储不含 `@`
4. **去重范围**：包含 inactive 账号，避免重复创建
5. **暂跳 auth**：US-008 实现后补上 JWT 中间件

---

## 实施顺序

1. 写 `app/schemas/account_types.py`
2. 写 `app/clients/x_client.py`
3. 写 `app/services/account_service.py`
4. 更新 `app/api/deps.py`
5. 更新 `app/api/accounts.py`
6. 写 `tests/test_accounts.py`（TDD 测试）
7. 质量门禁：ruff + pyright + pytest

---

## 验证

```bash
pytest tests/test_accounts.py -v
ruff check . && ruff format --check . && pyright && pytest
```

---

## 执行结果

### 交付物清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/schemas/account_types.py` | 新建 | AccountCreate/Update/Response/ListResponse 四个 Pydantic 模型 |
| `app/clients/x_client.py` | 新建 | X API 用户查询：lookup_user() + XUserProfile + XApiError |
| `app/services/account_service.py` | 新建 | AccountService（list/create/update/delete）+ 异常类 |
| `app/api/deps.py` | 修改 | 添加 get_account_service 依赖工厂 |
| `app/api/accounts.py` | 修改 | 实现 GET/POST/PUT/DELETE 四个端点 |
| `app/main.py` | 修改 | 添加 XApiError 全局异常处理器（502 + allow_manual） |
| `pyproject.toml` | 修改 | ruff ignore 添加 B008（FastAPI Depends 标准模式） |
| `tests/test_accounts.py` | 新建 | 12 个测试用例覆盖全部 CRUD + 边界场景 |

### 偏离项

| 项 | 计划 | 实际 | 原因 |
|----|------|------|------|
| 502 错误处理 | 路由内返回 JSONResponse | main.py 全局异常处理器 | FastAPI 不支持 Union[Response, Model] 返回类型注解，用全局 exception_handler 更干净 |
| ruff B008 | 未预见 | 添加到 ignore 列表 | `Depends()` 在函数默认参数中是 FastAPI 标准模式，B008 误报 |

### 问题与修复

1. **FastAPI 返回类型限制**: `dict[str, str] | JSONResponse` 作为返回类型会导致 FastAPI 启动失败。改用 HTTPException + 全局异常处理器模式。
2. **ruff B008 误报**: FastAPI 的 `Depends()` 在函数签名中是标准用法，但 ruff bugbear B008 会报错。添加到 ignore 列表解决。
3. **ruff B904**: except 块中 raise HTTPException 需要 `from None` 以切断异常链。

### 质量门禁

| 检查项 | 结果 |
|--------|------|
| ruff check | ✅ All checks passed |
| ruff format --check | ✅ 84 files already formatted |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 63 passed in 0.61s |

### PR 链接
> 待推送后填写
