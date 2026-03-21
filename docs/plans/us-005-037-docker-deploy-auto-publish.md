# US-005 + US-037：Docker Compose 部署 + API 自动发布预留

## Context

P3 仅剩 US-005（Docker Compose 部署）和 US-037（API 自动发布预留）。两者互相独立。

- US-005：项目缺少 Dockerfile、docker-compose.yml、Caddyfile。constraints.md §部署配置 已给出完整参考实现
- US-037：wechat_client.py 当前是空壳文件（仅一行注释），需要定义接口签名并在调用时 raise NotImplementedError。mark-published 路由需要根据 publish_mode 分支

## US-005：Docker Compose 部署

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `Dockerfile` | 新建 | 多阶段构建：Stage 1 bun 构建前端 → Stage 2 Python 运行环境 |
| `docker-compose.yml` | 新建 | web + scheduler + caddy 三容器 |
| `Caddyfile` | 新建 | HTTPS 反向代理，`{$DOMAIN}` 读取域名 |

### Dockerfile 实现策略

参照 `docs/spec/constraints.md:326-372`：

- **Stage 1 (frontend-builder)**：`node:20-slim` 安装 bun → 拷贝 packages/openapi-client + admin → `bun install --frozen-lockfile` → `bun run build`
- **Stage 2 (runtime)**：`python:3.12-slim` → 安装 supercronic + uv → `uv sync --frozen --no-dev` → 拷贝 app/ + alembic/ + crontab + 前端构建产物

### docker-compose.yml 实现策略

参照 constraints.md:376-418：
- **web**: `alembic upgrade head && uvicorn ...`，挂载 `./data:/app/data`
- **scheduler**: `supercronic /app/crontab`，共享 `./data`
- **caddy**: 官方镜像，挂载 Caddyfile + persistent volumes

### Caddyfile

```
{$DOMAIN} {
    handle /api/* { reverse_proxy web:8000 }
    handle { reverse_proxy web:8000 }
}
```

## US-037：API 自动发布（预留）

### 文件清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/publisher/wechat_client.py` | 修改 | 定义完整接口签名 + NotImplementedError |
| `app/api/digest.py` | 修改 | mark-published 根据 publish_mode 分支 |
| `tests/test_publisher.py` | 新建/修改 | wechat_client 接口测试 + publish_mode 分支测试 |

### wechat_client.py 实现

WechatClient 类：
- `get_access_token() -> str`
- `upload_article(title, content, cover_url) -> str`
- `send_mass(media_id) -> str`

所有方法 raise NotImplementedError。工厂函数 `get_wechat_client()` 检查 WECHAT_APP_ID/SECRET。

### mark-published 路由修改

1. 读取 system_config publish_mode
2. `manual` → 现有逻辑
3. `api` → 返回 501

### 测试

1. wechat_client 三个方法均 raise NotImplementedError
2. WECHAT_APP_ID 为空时 get_wechat_client() raise ValueError
3. publish_mode="api" 时返回 501
4. publish_mode="manual" 正常标记

## 实施顺序

1. US-005：Dockerfile → docker-compose.yml → Caddyfile
2. US-037：wechat_client.py → mark-published 修改 → 测试
3. 全量 pytest + 质量门禁

## 验证

```bash
uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pyright && uv run pytest
docker compose config --quiet
```

## 执行结果

### 交付物清单
| 文件 | 操作 | 行数 |
|------|------|------|
| `Dockerfile` | 新建 | 42 |
| `docker-compose.yml` | 新建 | 37 |
| `Caddyfile` | 新建 | 9 |
| `app/publisher/wechat_client.py` | 重写 | 37 |
| `app/api/digest.py` | 修改 | +11/-3 |
| `tests/test_publisher.py` | 新建 | 100 |
| `docs/spec/user-stories.md` | 修改 | 2 行状态更新 |
| `docs/plans/us-005-037-docker-deploy-auto-publish.md` | 新建 | 计划文件 |

### 偏离项
| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | Dockerfile COPY data/default_cover.png | 跳过此行 | data/default_cover.png 不存在且代码中无引用 |
| 2 | docker-compose.yml 直接调用 alembic/uvicorn | 改用 uv run 前缀 | 容器内 uv sync --no-dev 安装的包在 .venv 中，需要 uv run 执行 |

### 问题与修复
| 问题 | 解决 |
|------|------|
| test_publisher.py 有未使用的 import（UTC, datetime） | 删除多余 import |
| ruff format 格式不一致 | ruff format 自动修复 |

### 质量门禁
| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 128 files already formatted |
| lint-imports | ✅ 4 contracts kept, 0 broken |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 479 passed |

### PR 链接
https://github.com/neuer/zhixi/pull/24
