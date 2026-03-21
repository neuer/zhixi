# 实施计划：API Key UI 管理

> 设计文档：`docs/specs/2026-03-21-api-key-ui-management-design.md`

## 分支

`feat/api-key-ui-management`

## 步骤总览

| # | 任务 | 依赖 | 预估改动量 |
|---|------|------|------------|
| 1 | 加密模块 `app/crypto.py` + 测试 | 无 | 新建 1 文件 + 1 测试文件 |
| 2 | `config.py` 改造 + `get_secret_config()` | Step 1 | 改 1 文件 |
| 3 | Schema 新增 + Settings API 新增 | Step 1, 2 | 改 2 文件 |
| 4 | 调用方改造（Client + Service） | Step 2 | 改 6 文件 |
| 5 | 前端 Settings 页改造 | Step 3 | 改 1 文件 |
| 6 | `.env.example` + `constraints.md` 更新 | 无 | 改 2 文件 |
| 7 | 测试补充 + 全量门禁 | Step 1-6 | 新增/修改测试文件 |

---

## Step 1: 加密模块 `app/crypto.py`

**目标**：提供 Fernet 加密/解密工具函数

**新建 `app/crypto.py`**：
- `_derive_key(secret: str) -> bytes`：从 `JWT_SECRET_KEY` 通过 PBKDF2-SHA256 派生 32 字节 key，固定 salt = `b"zhixi-secret-config"`
- `encrypt_secret(plaintext: str) -> str`：加密返回 base64 密文字符串
- `decrypt_secret(ciphertext: str) -> str`：解密返回明文；失败返回 `""` + `logger.warning`
- 空字符串输入返回空字符串（不加密）

**新建 `tests/test_crypto.py`**：
- 加密→解密往返一致
- 空字符串不加密
- 错误密文返回空字符串
- 不同 JWT_SECRET_KEY 派生不同 key（解密失败）

**依赖新增**：`cryptography`（已在 pyproject.toml 间接依赖中，确认是否需要显式添加）

---

## Step 2: `config.py` 改造

**目标**：API Key 字段改为可选；新增 `get_secret_config()` 运行时读取函数

**改 `app/config.py`**：

1. `Settings` 类字段改默认值：
   ```python
   X_API_BEARER_TOKEN: str = ""
   ANTHROPIC_API_KEY: str = ""
   GEMINI_API_KEY: str = ""  # 已经是 ""
   WECHAT_APP_ID: str = ""   # 已经是 ""
   WECHAT_APP_SECRET: str = ""  # 已经是 ""
   CLAUDE_MODEL: str = "claude-sonnet-4-20250514"  # 不变
   CLAUDE_INPUT_PRICE_PER_MTOK: float = 3.0  # 不变
   CLAUDE_OUTPUT_PRICE_PER_MTOK: float = 15.0  # 不变
   ```

2. 新增函数：
   ```python
   async def get_secret_config(db: AsyncSession, key: str) -> str:
       """读取密钥配置：DB 优先（解密），fallback .env。"""
   ```
   - 读 `system_config` 表 key = `secret:{key}`
   - 有值 → `decrypt_secret(value)` 返回
   - 无值 → fallback `getattr(settings, key.upper(), "")`

3. 新增辅助函数：
   ```python
   async def get_model_config(db: AsyncSession, key: str, default: str) -> str:
       """读取模型配置：DB 优先（明文），fallback .env。"""
   ```
   - 用于 `claude_model`、价格参数等非密钥配置

4. 新增掩码函数：
   ```python
   def mask_secret(value: str) -> str:
       """掩码处理：首4尾4，中间****。短于12字符只显示****。"""
   ```

**更新现有测试**：确认 `Settings()` 不再因缺少 API Key 报错

---

## Step 3: Schema 新增 + Settings API

**目标**：新增密钥管理 API 端点

**改 `app/schemas/settings_types.py`**，新增：
```python
class SecretsUpdateRequest(BaseModel):
    """密钥更新请求（所有字段可选）。"""
    x_api_bearer_token: str | None = None
    anthropic_api_key: str | None = None
    gemini_api_key: str | None = None
    wechat_app_id: str | None = None
    wechat_app_secret: str | None = None

class SecretStatusItem(BaseModel):
    """单个密钥状态。"""
    key: str
    configured: bool
    masked: str
    source: Literal["db", "env", "none"]

class SecretsStatusResponse(BaseModel):
    """密钥状态响应。"""
    items: list[SecretStatusItem]
```

**改 `app/api/settings.py`**，新增 3 个端点：

1. `GET /api/settings/secrets-status`
   - 遍历 5 个密钥 key
   - 每个检查 DB 是否有 `secret:{key}` → 解密 → 掩码
   - 没有则检查 .env → 掩码
   - 返回 `SecretsStatusResponse`

2. `PUT /api/settings/secrets`
   - 请求体 `SecretsUpdateRequest`
   - 有值的字段 → `encrypt_secret()` → `upsert_system_config(db, f"secret:{key}", ciphertext)`
   - 需要 JWT 认证

3. `DELETE /api/settings/secrets/{key}`
   - 删除 `system_config` 表中 `secret:{key}` 记录
   - 需要 JWT 认证
   - key 白名单校验（只允许 5 个已知密钥名）

**改现有 `_ping_x_api` / `_ping_claude_api` / `_ping_gemini_api`**：
- 从 `settings.XXX` 改为 `get_secret_config(db, "x_api_bearer_token")` 等
- `get_api_status` 端点需要注入 `db: AsyncSession`

---

## Step 4: 调用方改造

**目标**：所有 API Key 消费方改为运行时从 DB 读取

### 4a. Claude Client 改造

**改 `app/clients/claude_client.py`**：
- `get_claude_client()` 同步单例 → `get_claude_client(db: AsyncSession)` 异步工厂
- 每次调用时从 DB 读取 key/model/价格，若与缓存实例不同则重建
- 或者更简单：去掉单例，每次创建（ClaudeClient 内部的 AsyncAnthropic 创建开销可忽略）

**改 `app/api/deps.py`**：
- `get_process_service` 和 `get_digest_service` 传 db 给 `get_claude_client`

**改 `app/services/pipeline_service.py`**：
- `get_claude_client()` → `get_claude_client(db)`

### 4b. Fetcher 改造

**改 `app/services/fetch_service.py`**：
- 第 94 行和 262 行：`settings.X_API_BEARER_TOKEN` → `await get_secret_config(self._db, "x_api_bearer_token")`

**改 `app/services/account_service.py`**：
- 第 95 行：`settings.X_API_BEARER_TOKEN` → `await get_secret_config(self._db, "x_api_bearer_token")`

### 4c. Gemini Client 改造

**改 `app/clients/gemini_client.py`**：
- `get_gemini_client()` → `get_gemini_client(db: AsyncSession)` 异步
- 从 DB 读取 `gemini_api_key`

**改 `app/services/digest_service.py`**：
- 第 142 行和 247 行：传 db 给 `get_gemini_client`

---

## Step 5: 前端 Settings 页改造

**目标**：在 Settings 页 API 状态区域增加配置入口

**改 `admin/src/views/Settings.vue`**：

1. 新增 API 类型定义和状态：
   ```typescript
   const secretsStatus = ref<SecretStatusItem[]>([])
   const showSecretDialog = ref(false)
   const editingSecret = ref({ key: '', label: '', value: '' })
   ```

2. 页面加载时调用 `GET /api/settings/secrets-status` 获取状态

3. 每个 API 状态行增加：
   - 已配置：显示掩码 + 来源标签（DB/ENV） + "修改"按钮 + "清除"按钮
   - 未配置：显示"未配置" + "配置"按钮

4. 弹窗（`van-dialog`）：
   - 标题：配置 {API 名称}
   - 已配置时显示掩码值
   - 输入框 type=password，placeholder "输入新值"
   - 确认按钮 → `PUT /api/settings/secrets`
   - 清除按钮 → `DELETE /api/settings/secrets/{key}`
   - 成功后刷新状态 + 自动 ping 检测

5. 非密钥配置（CLAUDE_MODEL、价格）可后续再做，本轮先聚焦密钥管理

---

## Step 6: 文档更新

**改 `.env.example`**：
- API Key 相关项改为注释 + 说明"推荐通过管理后台 Settings 页配置"

**改 `docs/spec/constraints.md`**：
- "密钥只存 .env" → "密钥加密存 DB（推荐）或 .env（兼容）"
- 记录例外 EXC-20260321-001

---

## Step 7: 测试补充 + 全量门禁

### 新增测试
- `tests/test_crypto.py`：加密模块单元测试（Step 1 已写）
- `tests/test_settings_secrets_api.py`：
  - PUT 写入 → GET 状态正确（configured=true, source=db）
  - DELETE 删除 → fallback env
  - 未认证 → 401
  - 无效 key 名 → 422

### 更新现有测试
- `tests/test_api.py` / `tests/test_settings.py`：适配 API Key 可选
- `tests/test_pipeline.py`：mock `get_secret_config` 替代 `settings.XXX`
- Client 相关测试：适配新的异步工厂签名

### 全量门禁
```bash
ruff check .
ruff format --check .
pyright
pytest
```

---

## 执行结果（待回填）

| 项目 | 结果 |
|------|------|
| 交付物清单 | |
| 偏离项 | |
| 问题与修复 | |
| 质量门禁 | |
| PR 链接 | |
