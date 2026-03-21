# API Key UI 管理设计

> 将 API Key 从 .env 手动配置迁移到管理后台 Settings 页，降低部署门槛。

## 背景

当前所有 API Key（X API、Anthropic、Gemini、微信）必须手动编辑 `.env` 文件才能配置。对于单用户自部署产品，这增加了不必要的上手门槛。用户需要 SSH 到服务器编辑文件，而非通过浏览器一站式完成。

## 设计决策

| 决策点 | 选择 | 理由 |
|--------|------|------|
| 存储方式 | Fernet 对称加密存入 DB | 满足 spec 禁止明文存 DB 的约束 |
| 配置入口 | 仅 Settings 页 | Setup 向导保持简洁（只设密码），Key 在登录后配置 |
| 兼容策略 | DB 优先 + .env fallback | 已有部署平滑迁移，无需重新配置 |
| 编辑交互 | 弹窗编辑 + 掩码展示 | 密钥不回显原文，点击"配置"按钮弹窗输入 |

## .env 配置项分类

### 必须保留 .env（启动时需要）

| 配置项 | 理由 |
|--------|------|
| `JWT_SECRET_KEY` | 加密种子，鸡生蛋问题 |
| `DATABASE_URL` | 启动前就要连 DB |
| `API_HOST` / `API_PORT` | 进程启动参数 |
| `DEBUG` / `LOG_LEVEL` / `TIMEZONE` | 进程启动时需要 |
| `DOMAIN` | Caddy/HTTPS 证书配置 |

### 迁移到 UI（运行时使用）

| 配置项 | 类型 |
|--------|------|
| `X_API_BEARER_TOKEN` | 密钥 |
| `ANTHROPIC_API_KEY` | 密钥 |
| `GEMINI_API_KEY` | 密钥 |
| `WECHAT_APP_ID` | 密钥 |
| `WECHAT_APP_SECRET` | 密钥 |
| `CLAUDE_MODEL` | 普通配置 |
| `CLAUDE_INPUT_PRICE_PER_MTOK` | 普通配置 |
| `CLAUDE_OUTPUT_PRICE_PER_MTOK` | 普通配置 |

## 架构设计

### 1. 加密模块 `app/crypto.py`

- 使用 `cryptography.fernet` 对称加密
- 从 `JWT_SECRET_KEY` 通过 PBKDF2 派生 32 字节 Fernet key（固定 salt，同一 JWT_SECRET_KEY 始终得到同一派生 key）
- 接口：`encrypt_secret(plaintext) -> str`、`decrypt_secret(ciphertext) -> str`
- 解密失败（JWT_SECRET_KEY 更换等）返回空字符串 + 日志告警

### 2. config.py 改造

- `X_API_BEARER_TOKEN`、`ANTHROPIC_API_KEY`、`GEMINI_API_KEY`、`WECHAT_APP_ID`、`WECHAT_APP_SECRET`、`CLAUDE_MODEL`、价格参数 → 全部改为 `str = ""`（可选）
- 启动不再因缺少 API Key 报错
- 新增 `get_secret_config(db, key) -> str`：DB 优先（解密）→ fallback .env

### 3. DB 存储约定

- 密钥类配置存入 `system_config` 表，key 加前缀 `secret:`
  - 例：`secret:x_api_bearer_token`、`secret:anthropic_api_key`
- value 字段存 Fernet 加密后的密文字符串
- 非密钥类配置（`CLAUDE_MODEL`、价格）直接明文存入 `system_config`，无前缀

### 4. 后端 API

#### `PUT /api/settings/secrets`（新增）

```
请求体: {
  "x_api_bearer_token?": "Bearer xxx",
  "anthropic_api_key?": "sk-ant-xxx",
  "gemini_api_key?": "AIza...",
  "wechat_app_id?": "wx...",
  "wechat_app_secret?": "..."
}
```

- 只传的字段才更新，不传不动
- 值加密后存入 `system_config`
- 需要 JWT 认证

#### `GET /api/settings/secrets-status`（新增）

```
响应: {
  "items": [
    {
      "key": "x_api_bearer_token",
      "configured": true,
      "masked": "Bear****wxyz",
      "source": "db"
    },
    {
      "key": "anthropic_api_key",
      "configured": true,
      "masked": "sk-a****ef12",
      "source": "env"
    }
  ]
}
```

- `source` 标明来自 "db" 或 "env"
- `masked` 首 4 尾 4 掩码，短于 12 字符只显示"****"
- 绝不返回原文

#### `DELETE /api/settings/secrets/{key}`（新增）

- 删除 DB 中的加密值，fallback 回 .env
- 需要 JWT 认证

#### 现有 `GET /api/settings/api-status` 保持不变

- 内部改为用 `get_secret_config()` 读 Key

### 5. 调用方改造

以下模块的 Key 读取方式从 `settings.XXX` 改为 `get_secret_config(db, key)`：

| 模块 | 当前读取 | 改为 |
|------|----------|------|
| `app/clients/claude_client.py` | `settings.ANTHROPIC_API_KEY` | `get_secret_config(db, "anthropic_api_key")` |
| `app/fetcher/x_fetcher.py` | `settings.X_API_BEARER_TOKEN` | `get_secret_config(db, "x_api_bearer_token")` |
| `app/clients/gemini_client.py` | `settings.GEMINI_API_KEY` | `get_secret_config(db, "gemini_api_key")` |
| `app/api/settings.py` (_ping 函数) | `settings.XXX` | `get_secret_config(db, ...)` |

注意：这些调用方本身已在异步上下文中持有 db session，改造成本低。对于无 session 的场景（如 CLI pipeline），需要创建临时 session 读取。

### 6. 前端 Settings 页改造

在现有"API 状态"区域增强：

- 每个 API 行增加"配置"按钮
- 点击弹出 `van-dialog`，含：
  - 当前状态标签（已配置/未配置 + 来源 db/env）
  - 掩码展示已有值
  - 输入框 placeholder "输入新值覆盖"
  - 确认 / 取消 / 清除（删除 DB 值）按钮
- 提交后自动刷新 API 状态检测
- CLAUDE_MODEL 和价格参数可以放在普通配置区域（非弹窗，直接内联编辑）

### 7. .env.example 更新

API Key 相关项改为注释 + 说明：

```bash
# ===== API 密钥（推荐通过管理后台 Settings 页配置）=====
# 以下配置项可选，如在此处填写则作为后备值
# X_API_BEARER_TOKEN=
# ANTHROPIC_API_KEY=
# GEMINI_API_KEY=
# WECHAT_APP_ID=
# WECHAT_APP_SECRET=
```

## 影响范围

| 改动点 | 文件 |
|--------|------|
| 新增加密模块 | `app/crypto.py` |
| config 改造 | `app/config.py` |
| Settings API | `app/api/settings.py` |
| Schema | `app/schemas/settings_types.py` |
| X Fetcher | `app/fetcher/x_fetcher.py` |
| Claude Client | `app/clients/claude_client.py` |
| Gemini Client | `app/clients/gemini_client.py` |
| 前端 Settings | `admin/src/views/Settings.vue` |
| 环境模板 | `.env.example` |
| 测试 | 新增 + 更新 |

## 约束与例外

- `constraints.md` 原有规则 "DB 中存 API Key 明文" → 通过 Fernet 加密满足，不再明文
- `constraints.md` 原有规则 "密钥只存 .env" → 需更新为 "密钥加密存 DB 或 .env"
- 例外编号：EXC-20260321-001 — 修改 constraints.md 密钥存储约束，到期条件：本功能合并后永久生效
