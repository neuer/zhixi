# US-007 + US-008: 首次设置向导 + 管理员登录认证

## Context

P1 全部完成，进入 P2 阶段。US-007（设置向导）和 US-008（登录认证）是 P2 大多数 US 的前置依赖（US-010 accounts 路由需要 JWT 保护、US-030/039 等需要认证）。两个 US 彼此独立，可并行实现。

当前代码中 `app/auth.py` 仅有 docstring，`app/api/setup.py` 和 `app/api/auth.py` 是空路由壳。`pyproject.toml` 已包含 `pyjwt` 和 `bcrypt` 依赖。`seeded_db` fixture 中已有 `admin_password_hash` 配置项（空值）。`accounts.py` 路由已有 `# TODO: US-008 添加 Depends(get_current_admin)` 注释。

## 实施策略

**分支**: `us-007-008-setup-auth`（并行组）

**TDD 顺序**: 先实现核心模块 `app/auth.py`（无路由依赖），再实现路由层，最后补加 accounts 认证。

---

## 1. 新增/修改文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `app/schemas/auth_types.py` | 认证相关 Pydantic 类型 |
| `tests/test_setup.py` | 设置向导 API 测试 |
| `tests/test_auth.py` | 登录认证 API 测试 |

### 修改文件

| 文件 | 说明 |
|------|------|
| `app/auth.py` | 核心认证逻辑（JWT、bcrypt、限流器） |
| `app/api/setup.py` | 设置向导路由 |
| `app/api/auth.py` | 认证路由 |
| `app/api/deps.py` | 新增 `get_current_admin` 依赖 |
| `app/api/accounts.py` | 添加 JWT 认证依赖 |

---

## 2. 实现细节

### 2.1 `app/schemas/auth_types.py` — 认证 Schema

```python
class SetupStatusResponse(BaseModel):
    need_setup: bool

class SetupInitRequest(BaseModel):
    password: str
    notification_webhook_url: str | None = None

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
```

### 2.2 `app/auth.py` — 核心认证模块

**密码操作**:
- `hash_password(password: str) -> str` — bcrypt hash（salt rounds 默认 12）
- `verify_password(password: str, hashed: str) -> bool` — bcrypt verify
- `validate_password_strength(password: str) -> None` — ≥8位、含大小写+数字，不满足 raise `WeakPasswordError`

**JWT 操作**:
- `create_jwt(username: str) -> tuple[str, datetime]` — 使用 `settings.JWT_SECRET_KEY`，HS256，返回 (token, expires_at)
- `verify_jwt(token: str) -> dict` — 验证签名和过期，失败 raise `InvalidTokenError`

**登录限流器** (内存实现):
- `LoginRateLimiter` 类 or 模块级函数
  - `check_login_rate_limit(username: str) -> bool` — True=允许，False=锁定
  - `record_login_failure(username: str) -> None` — 计数+1，≥5 次触发锁定
  - `record_login_success(username: str) -> None` — 重置计数器
- 使用 `dataclass LoginAttempt(fail_count, locked_until)`
- `_login_attempts: dict[str, LoginAttempt]` 内存字典
- 常量: `LOCKOUT_THRESHOLD = 5`, `LOCKOUT_DURATION = timedelta(minutes=15)`
- 锁定到期后自动重置

**自定义异常**:
- `WeakPasswordError(Exception)` — 密码强度不足
- `InvalidTokenError(Exception)` — JWT 无效或过期

### 2.3 `app/api/setup.py` — 设置向导路由

**`GET /status`**:
1. 读取 `system_config` 中 `admin_password_hash`
2. 为空 → `{need_setup: true}`，非空 → `{need_setup: false}`

**`POST /init`**:
1. 检查 `admin_password_hash` 非空 → 403 "系统已完成初始化"
2. 校验密码强度（`validate_password_strength`），不满足 → 422 中文错误
3. bcrypt hash → 写入 `system_config.admin_password_hash`
4. 如有 `notification_webhook_url` → 写入 `system_config.notification_webhook_url`
5. 返回 200 `{"message": "初始化完成"}`

**依赖注入**: 直接用 `Depends(get_db)` 获取 session，不经 Service 层（简单 CRUD 级别操作）。

### 2.4 `app/api/auth.py` — 认证路由

**`POST /login`**:
1. 检查限流 → 423 "登录失败次数过多，请15分钟后再试"
2. 读取 `admin_password_hash` → 为空则 401（系统未初始化）
3. 校验 `username == "admin"` && `verify_password(password, hash)`
4. 失败 → `record_login_failure` → 401 "用户名或密码错误"
5. 成功 → `record_login_success` → `create_jwt("admin")` → 200 `{token, expires_at}`

**`POST /logout`**:
- 200 `{"message": "已退出登录"}`（后端无状态操作）

### 2.5 `app/api/deps.py` — 新增 JWT 依赖

```python
async def get_current_admin(
    authorization: str | None = Header(default=None),
) -> str:
    """从 Authorization header 提取并验证 JWT。

    返回用户名（"admin"）。无效/过期抛 HTTPException(401)。
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "登录已过期，请重新登录")
    token = authorization.removeprefix("Bearer ")
    try:
        payload = verify_jwt(token)
    except InvalidTokenError:
        raise HTTPException(401, "登录已过期，请重新登录") from None
    return payload["sub"]
```

### 2.6 `app/api/accounts.py` — 添加认证

在所有 4 个路由端点的参数中添加 `_admin: str = Depends(get_current_admin)` 依赖。

---

## 3. 测试要点

### 3.1 `tests/test_setup.py`（US-007）

| 测试用例 | 验证点 |
|---------|--------|
| `test_setup_status_need_setup` | 空密码哈希 → `need_setup: true` |
| `test_setup_status_already_done` | 有密码哈希 → `need_setup: false` |
| `test_setup_init_success` | 密码校验通过 → 200 + 密码写入 DB |
| `test_setup_init_with_webhook` | 带 webhook → webhook 同时写入 |
| `test_setup_init_weak_password_short` | <8位 → 422 |
| `test_setup_init_weak_password_no_upper` | 无大写 → 422 |
| `test_setup_init_weak_password_no_lower` | 无小写 → 422 |
| `test_setup_init_weak_password_no_digit` | 无数字 → 422 |
| `test_setup_init_already_done` | 重复调用 → 403 |
| `test_setup_init_verify_bcrypt` | 写入的哈希可用 bcrypt 验证 |

### 3.2 `tests/test_auth.py`（US-008）

| 测试用例 | 验证点 |
|---------|--------|
| `test_login_success` | 正确凭据 → 200 + JWT token |
| `test_login_wrong_password` | 错误密码 → 401 |
| `test_login_wrong_username` | 错误用户名 → 401 |
| `test_login_not_initialized` | 未初始化 → 401 |
| `test_login_lockout_after_5_failures` | 连续5次失败 → 423 |
| `test_login_lockout_6th_attempt` | 第6次 → 423 |
| `test_login_success_resets_counter` | 成功后重置计数 |
| `test_logout` | POST /logout → 200 |
| `test_jwt_protects_accounts` | 无 token 访问 accounts → 401 |
| `test_jwt_expired` | 过期 token → 401 |
| `test_jwt_invalid` | 无效 token → 401 |
| `test_jwt_valid_access` | 有效 token → 正常访问 |
| `test_setup_and_auth_no_jwt_required` | setup/auth 路由不需要 JWT |

### 3.3 单元测试（在 `tests/test_auth.py` 内）

| 测试用例 | 验证点 |
|---------|--------|
| `test_hash_and_verify_password` | bcrypt 加密/验证 |
| `test_validate_password_strength_valid` | 合规密码不抛异常 |
| `test_validate_password_strength_too_short` | <8位抛 WeakPasswordError |
| `test_create_and_verify_jwt` | JWT 创建/验证往返 |
| `test_jwt_expired_raises` | 过期 JWT 抛 InvalidTokenError |
| `test_rate_limiter_allows_initially` | 首次允许登录 |
| `test_rate_limiter_locks_after_threshold` | 5次失败后锁定 |
| `test_rate_limiter_resets_on_success` | 成功后重置 |

---

## 4. 关键决策

1. **密码强度正则**: `re.search(r'[A-Z]', p) and re.search(r'[a-z]', p) and re.search(r'\d', p) and len(p) >= 8`，不要求特殊字符。
2. **JWT payload**: `{"sub": "admin", "exp": expires_at}`，最小字段集。
3. **bcrypt salt rounds**: 使用 bcrypt 默认值（12 rounds），满足安全要求。
4. **setup 路由不经 Service 层**: 只是读/写 system_config 两条记录，属于简单 CRUD，直接在路由中操作 DB。
5. **accounts 路由加 JWT**: 按现有 TODO 注释添加依赖，accounts 的所有端点都需要认证。
6. **限流器时间使用 UTC**: `datetime.now(UTC)` 统一时区处理。

---

## 5. 验证方式

```bash
# 1. 运行测试
pytest tests/test_setup.py tests/test_auth.py -v

# 2. 质量门禁
ruff check .
ruff format --check .
pyright
uv run lint-imports

# 3. 全量测试确认无回归
pytest
```

---

## 执行结果

### 交付物清单

| 文件 | 类型 | 说明 |
|------|------|------|
| `app/auth.py` | 修改 | 核心认证模块：bcrypt 密码哈希/验证、密码强度校验、JWT HS256 创建/验证、登录限流器（内存实现） |
| `app/schemas/auth_types.py` | 新增 | SetupStatusResponse, SetupInitRequest, LoginRequest, LoginResponse |
| `app/api/setup.py` | 修改 | GET /status + POST /init 设置向导路由 |
| `app/api/auth.py` | 修改 | POST /login + POST /logout 认证路由 |
| `app/api/deps.py` | 修改 | 新增 `get_current_admin` JWT 依赖函数 |
| `app/api/accounts.py` | 修改 | 4 个端点添加 `Depends(get_current_admin)` |
| `tests/test_setup.py` | 新增 | 10 个设置向导 API 测试 |
| `tests/test_auth.py` | 新增 | 26 个认证测试（密码单元 + JWT 单元 + 限流单元 + API 集成） |
| `tests/conftest.py` | 修改 | 新增 `auth_headers` + `authed_client` fixture |
| `tests/test_accounts.py` | 修改 | 改用 `authed_client` fixture 适配 JWT 保护 |
| `tests/test_logging.py` | 修改 | request_id 中间件测试改用 conftest 的 `client` fixture |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 无 | — | — | 完全按计划执行 |

### 问题与修复

| 问题 | 修复 |
|------|------|
| `_login_attempts` 模块级变量误用 `field(default_factory=dict)` | 改为直接赋值 `{}` |
| `test_accounts.py` 全部因缺 JWT 失败（12 个） | 新增 `authed_client` fixture，全部改用 |
| `test_logging.py` request_id 测试因自行管理 client 无 DB 注入而失败 | 改用 conftest 的 `client` fixture + `/api/auth/logout` 端点 |
| pyright 报 fixture 返回类型错误 | `_clean_rate_limiter` 移除返回类型注解 |

### 质量门禁

| 检查项 | 结果 |
|--------|------|
| `ruff check .` | ✅ 通过 |
| `ruff format --check .` | ✅ 通过 |
| `pyright` | ✅ 0 errors |
| `lint-imports` | ✅ 4 contracts kept |
| `pytest` | ✅ 267 passed |

### PR 链接

https://github.com/neuer/zhixi/pull/11
