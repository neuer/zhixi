# 约束与运行环境

> 核心目标、范围、技术禁止项、安全约束、部署配置、环境变量、依赖版本。

---

## 核心目标与关键指标

**核心目标**:
1. **内容自动化**: 每日 pipeline 全自动「抓取 → AI加工 → 草稿生成」，管理员只需审核和一键发布
2. **内容质量**: AI 翻译准确率 >90%，话题聚合准确率 >80%，管理员可人工微调
3. **稳定运行**: 连续 7 天 pipeline 成功率 >95%，异常时自动通知管理员

**关键指标**:

| 指标 | 目标值 | 测量方式 |
|------|--------|----------|
| Pipeline 成功率 | >95%（连续7天） | job_runs 表统计 |
| 翻译准确率 | >90% | 管理员抽样评估 |
| 聚合准确率 | >80% | 管理员抽样评估 |
| 上线2周关注数 | >200 | 公众号后台 |
| 单篇平均阅读 | >100 | 公众号后台 |
| Pipeline 总耗时 | <15分钟 | job_runs 时间差 |
| API 月成本 | <$43 | api_cost_log 汇总 |

---

## MVP 范围（本期包含）

- X API 官方抓取（原创 + 自回复 Thread + 有观点 quote tweet）
- AI 两步加工：全局分析（过滤+聚合+Thread+热度）→ 逐条加工（标题+翻译+点评）
- Thread 专用 Prompt 加工
- 混合热度算法（规则 70% + AI 修正 30%）
- Markdown 输出 + 手动发布闭环
- 管理员审核 + 编辑（只改快照，不改源表）+ 调整排序
- 手动补录 tweet URL（ai_importance_score 固定 50）
- 任务幂等锁（job_runs）+ 统一 API 成本监控
- Pipeline 失败通知（企业微信 webhook）
- SQLite 备份 + 移动端优先 Vue 管理后台
- Docker Compose 部署（web + scheduler + caddy）

---

## 范围排除（NOT IN SCOPE）

| 功能 | 替代方案 | 计划阶段 |
|------|----------|----------|
| 图片下载/选图/展示 | 仅保存 media_urls 字段 | Phase 2 |
| AI 封面图作为验收项 | 默认关闭，可配置开启但不作为 MVP 验收 | Phase 2 |
| 微信公众号 API 自动发布 | 手动 Markdown 复制到排版工具 | Phase 2 |
| 第三方数据源实际接入 | BaseFetcher 留空壳类 | Phase 2 |
| `/api/manual/process` 接口 | 已砍掉，用 regenerate 替代 | — |
| 精修 HTML 渲染模板 | Markdown 输出 | Phase 2 |
| 跨批 AI 去重 | 单批处理（除非真实遇到溢出） | Phase 2 |
| 文章永久链接/详情页 | 只有今日内容和历史列表 | Phase 3 |
| 多管理员/角色权限 | 单管理员 admin | Phase 3 |
| 用户注册/登录 | 公众号读者纯浏览 | Phase 3 |
| 历史搜索 | 列表分页浏览 | Phase 3 |
| 小程序/H5 | 公众号文章 | Phase 3 |
| 多渠道推送 | 仅公众号 | Phase 3 |
| 付费会员/商业化 | 免费 | Phase 4 |

**明确不支持**: 多语言界面、桌面端优化、离线使用、并发多人编辑、推文评论/回复抓取、实时推送、推文图片展示、自定义 Markdown 模板、数据导出（用 SQLite 备份代替）。

---

## 技术栈（必须使用）

| 层级 | 选型 | 版本约束 |
|------|------|----------|
| 后端框架 | FastAPI | ≥0.115 |
| 后端语言 | Python | 3.12+ |
| 后端依赖管理 | uv | |
| 后端 Lint/格式化 | ruff | |
| 后端类型检查 | pyright | |
| 前端框架 | Vue 3 (Composition API) | |
| 前端语言 | TypeScript | 严格模式 |
| 前端 UI | Vant 4 | |
| 前端构建 | Vite | |
| 前端运行时/包管理 | bun | |
| 前端 Lint/格式化 | biome | |
| 前端类型检查 | vue-tsc | |
| 前端 E2E 测试 | Playwright | |
| ORM | SQLAlchemy 2.x | 通用类型 |
| 数据库迁移 | Alembic (autogenerate) | |
| 数据库 | SQLite (WAL 模式) | MVP 阶段 |
| CLI | Typer | |
| 定时调度 | supercronic（容器内） | |
| 部署 | Docker Compose（3容器） | |
| HTTPS | Caddy（自动证书） | |
| AI 文本 | Anthropic Claude API (Sonnet) | 模型名 .env 配置 |
| AI 图像 | Google Gemini API | 可选，默认关闭 |
| 认证 | JWT (PyJWT) | |
| 密码哈希 | bcrypt (salt rounds ≥12) | |
| HTTP 客户端 | httpx (async) | |
| OpenAPI 客户端生成 | @hey-api/openapi-ts | |
| Commit 规范 | Conventional Commits | |
| 模块边界检查 | import-linter（后端） | |

---

## 模块边界门禁

后端模块之间禁止直接 import 业务代码（如 `fetcher/` 不能 import `processor/`）。通过 `import-linter` 自动化检查，CI 中执行。

### 后端规则（pyproject.toml 中配置 import-linter）

```
# 禁止的跨模块 import
fetcher → processor, digest, publisher
processor → fetcher, digest, publisher
digest → fetcher（但可调用 processor，regenerate 场景）
publisher → fetcher, processor
```

允许所有模块 import `app.models`、`app.schemas`、`app.clients`、`app.crud`、`app.config`、`app.database`（共享基础设施）。

### CI 检查

`make lint` 中包含 `uv run lint-imports`，CI backend job 也执行此命令。

---

## 构建链路

### OpenAPI 生成

后端 FastAPI 自动产出 `/openapi.json`，通过 `@hey-api/openapi-ts` 生成 TypeScript 客户端和类型到 `packages/openapi-client/src/gen/`。

**生成命令**：`make gen`（统一入口）

**流程**：
1. 临时启动后端进程，导出 `openapi.json`
2. 运行 `@hey-api/openapi-ts` 生成客户端
3. 关闭临时进程

**规则**：
- `packages/openapi-client/src/gen/` 下的文件禁止手动修改
- 扩展逻辑写在 gen/ 目录之外的 Wrapper 文件中
- CI 必须运行 `make gen` 并校验工作区无 diff，任何差异视为失败
- 任何 API 变更后必须运行 `make gen` 并提交生成物

### Makefile

```makefile
.PHONY: gen gen-openapi lint lint-backend lint-frontend test dev setup

# 统一生成命令（P2 之后可用）
gen: gen-openapi

gen-openapi:
	@echo "== 导出 OpenAPI =="
	uv run python -c "import json; from app.main import app; from fastapi.openapi.utils import get_openapi; print(json.dumps(get_openapi(title=app.title, version=app.version, routes=app.routes), ensure_ascii=False, indent=2))" > openapi.json
	@echo "== 生成 TS 客户端 =="
	cd packages/openapi-client && bunx @hey-api/openapi-ts
	@rm openapi.json
	@echo "生成完成"

# 质量门禁（按阶段递进：P0 只有 lint-backend，P2 后全部可用）
lint: lint-backend lint-frontend

lint-backend:
	uv run ruff check .
	uv run ruff format --check .
	uv run lint-imports
	uv run pyright

lint-frontend:
	@test -f admin/package.json && (cd admin && bunx biome check . && bunx vue-tsc --noEmit) || echo "跳过前端检查（admin/ 不存在）"

test:
	uv run pytest

# 本地开发
dev:
	@echo "后端: uvicorn app.main:app --reload --port 8000"
	@echo "前端: cd admin && bun dev"

# 首次初始化（自动检测已有组件）
setup:
	uv sync --dev
	@test -f admin/package.json && (cd admin && bun install) || true
	@test -f packages/openapi-client/package.json && (cd packages/openapi-client && bun install) || true
	cp -n .env.example .env || true
	git config core.hooksPath .githooks
	@echo "初始化完成，请编辑 .env 填入 API Key"
```

### 本地开发环境初始化

#### 前置条件：安装工具

```bash
# uv（Python 依赖管理）
curl -LsSf https://astral.sh/uv/install.sh | sh

# bun（前端运行时，P2 阶段需要）
curl -fsSL https://bun.sh/install | bash
```

#### 初始化步骤

```bash
# 1. 克隆仓库
git clone <repo-url> && cd zhixi

# 2. 一键初始化（自动检测已有组件，跳过不存在的）
make setup

# 3. 编辑 .env（填入 X_API_BEARER_TOKEN、ANTHROPIC_API_KEY、JWT_SECRET_KEY）

# 4. 初始化数据库（US-002 完成后可用）
uv run alembic upgrade head

# 5. 启动开发服务器
# 终端 1（后端）:
uv run uvicorn app.main:app --reload --port 8000
# 终端 2（前端，P2 之后可用）:
cd admin && bun dev
```

---

## 技术禁止项

| 禁止项 | 原因 |
|--------|------|
| SQLite 专属语法 | 需兼容 PostgreSQL 迁移 |
| Python 中使用 `typing.Any` | 规避类型检查 |
| 前端使用 `any` 类型 | TypeScript 严格模式要求 |
| 前端 `.vue` 文件不使用 `<script setup lang="ts">` | 统一 TypeScript |
| 前端 localStorage 存业务数据 | 只存 JWT token |
| crud.py 中写业务逻辑 | 违反模块边界 |
| 业务模块间互相 import | fetcher/ 不能 import processor/ |
| Web 进程中嵌入定时任务 | 必须独立 CLI + supercronic |
| 硬编码 AI 模型名 | 必须从 CLAUDE_MODEL 环境变量读取 |
| 硬编码 API Key | 必须从 .env 读取 |
| DB 中存 API Key 明文 | 密钥只存 .env |
| 设置页回显 API Key | 只显示"已配置/未配置" |
| .env 中存 notification_webhook_url | 只存 DB system_config |
| .env 中存管理员密码 | 只存 DB（bcrypt hash） |

---

## 性能约束

| 指标 | 目标值 | 说明 |
|------|--------|------|
| API 接口响应 | <500ms | 非 AI 调用的 DB 查询接口 |
| Pipeline 总耗时 | <15 分钟 | 50 大V、200 条推文 |
| 单条 AI 加工 | <30 秒 | 含网络延迟 |
| 封面图生成超时 | 30 秒硬限制 | 超时用默认封面 |
| 前端首屏加载 | <3 秒 | 移动端 4G |
| SQLite 并发 | WAL + busy_timeout=5000ms | Web + CLI 同时访问 |

---

## 安全约束

| 要求 | 实现方式 |
|------|----------|
| HTTPS | Caddy 自动 Let's Encrypt 证书 |
| 密码存储 | bcrypt hash（salt rounds ≥12） |
| JWT 签名 | HS256，密钥从 JWT_SECRET_KEY 读取 |
| JWT 有效期 | 默认 72 小时（可配置） |
| 登录防暴力 | 连续 5 次失败锁定 15 分钟 |
| 预览链接 | secrets.token_urlsafe(32) + 24h 有效 |
| Prompt 注入 | 所有 AI Prompt 开头注入安全声明 |
| SQL 注入 | SQLAlchemy ORM 参数化查询 |
| API Key 保护 | 仅 .env 存储，不经 API 传输/回显 |

---

## 兼容性约束

| 维度 | 要求 |
|------|------|
| 移动端 | iOS Safari ≥15, Android Chrome ≥90（主力） |
| 桌面端 | 可用但非优化目标 |
| 数据库 | SQLAlchemy 通用类型，兼容未来 PostgreSQL |
| Python | 3.12+（Docker: python:3.12-slim） |
| Node.js | 20 LTS（Docker: node:20-slim，仅构建阶段，安装 bun） |

---

## 开放问题

| 编号 | 问题 | 状态 | 计划解决时间 |
|------|------|------|-------------|
| O-1 | X API 开发者账号审批可能延迟 | 已有 BaseFetcher 抽象兜底 | 开发期间并行申请 |
| O-2 | 微信公众号注册认证时间不确定 | MVP 用手动 Markdown 模式 | 认证通过后启用 |
| O-3 | Claude API Sonnet 定价可能调整 | estimated_cost 已标注为估算值 | 定价变更时更新配置 |
| O-4 | 跨批 AI 去重效果未验证 | 单批处理足够50大V日常量 | 真实遇到溢出时再启用 |
| O-5 | SQLite 在高并发下的表现 | MVP 单管理员无并发压力 | Phase 2 评估迁移 PostgreSQL |
| O-6 | running 状态残留自动清理阈值 | 暂定2小时 | 试运行期间观察调整 |
| O-7 | 单管理员多标签页编辑冲突 | MVP 不处理，last-write-wins | Phase 2 考虑 etag 乐观锁 |

---

## 全局规范例外声明

> 以下为本项目相对于 `~/.claude/CLAUDE.md` 全局规范的有意偏离，按第 23 条格式声明。项目 `docs/spec/` 目录下的约定为本项目唯一事实源。

| 编号 | 偏离项 | 项目方案 | 理由 | 到期条件 |
|------|--------|---------|------|----------|
| EXC-20260319-001 | 前端框架（全局: Next.js + React） | Vue 3 + TypeScript + Vant 4 | MVP 移动端优先管理后台，Vant 生态更匹配 | 长期 |
| EXC-20260319-002 | 数据库（全局: PostgreSQL + pgvector） | SQLite (WAL) | MVP 单管理员、单服务器，无向量搜索需求 | Phase 2 评估迁移 |
| EXC-20260319-003 | 异步任务（全局: Celery/Dramatiq + Redis） | supercronic + CLI 同步执行 | MVP 无并发任务需求 | Phase 2 评估 |
| EXC-20260319-004 | 前端 Zod 校验器（全局: 生成链路产出） | Vant 原生表单校验 | 单管理员场景，Vant 组件内置校验足够 | Phase 2 评估 |
| EXC-20260319-005 | 目录结构（全局: apps/web + apps/api + features/） | app/ + admin/ + 按功能模块拆分 | 项目规模较小，扁平结构更清晰 | 长期 |
| EXC-20260319-006 | 统一错误模型（全局: {code, message, details}） | FastAPI 默认 `{"detail": "..."}` | 单管理员前端用 toast 展示中文 detail 足够 | Phase 2 补错误码 |
| EXC-20260319-007 | 流式 SSE 协议（全局: 第 17 条） | 不适用 | AI 处理为后台任务，无实时流式输出场景 | 长期 |
| EXC-20260319-008 | 幂等性 Key Header（全局: 第 18 条） | job_runs 锁机制替代 | 单管理员 + 锁机制已防重复执行 | Phase 2 评估 |
| EXC-20260319-009 | 队列任务规范（全局: 第 19 条） | supercronic + CLI | 同 EXC-003 | Phase 2 评估 |
| EXC-20260319-010 | 可观测性（全局: OpenTelemetry + Sentry + Prometheus） | request_id + 结构化 JSON 日志 + api_cost_log | MVP 轻量方案，满足基本可追踪性 | Phase 2 补齐 |
| EXC-20260319-011 | LLM 事件日志（全局: prompt_hash + trace_id + span_id） | api_cost_log 记录 token_usage + cost + request_id | MVP 只做成本监控，不做完整事件审计 | Phase 2 补齐 |
| EXC-20260319-012 | 合规输出结构化对象（全局: 第 24 条） | PR 模板 Checklist 覆盖 | 单人开发，PR checklist 足够审计 | Phase 2 评估 |
| EXC-20260319-013 | 数据分级与保留策略（全局: 第 11.1 条） | 备份 30 天 + 日志 30 天 | MVP 无个人敏感数据（单管理员） | Phase 2 补齐 |

---

## 部署配置

### Dockerfile

```dockerfile
# Stage 1: 构建前端
FROM node:20-slim AS frontend-builder
RUN npm install -g bun
WORKDIR /app
COPY packages/openapi-client/package.json packages/openapi-client/
COPY admin/package.json admin/bun.lock admin/
WORKDIR /app/admin
RUN bun install --frozen-lockfile
COPY packages/openapi-client/ /app/packages/openapi-client/
COPY admin/ .
RUN bun run build

# Stage 2: 运行环境
FROM python:3.12-slim

WORKDIR /app

# 安装 supercronic + uv
RUN apt-get update && apt-get install -y curl && \
    curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.29/supercronic-linux-amd64 \
    -o /usr/local/bin/supercronic && \
    chmod +x /usr/local/bin/supercronic && \
    curl -LsSf https://astral.sh/uv/install.sh | sh && \
    apt-get remove -y curl && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.local/bin:$PATH"

# Python 依赖
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 复制代码
COPY app/ app/
COPY alembic/ alembic/
COPY alembic.ini .
COPY crontab .
COPY data/default_cover.png data/

# 复制前端构建产物
COPY --from=frontend-builder /app/admin/dist admin/dist/

# 创建数据目录
RUN mkdir -p data/covers data/backups data/logs

EXPOSE 8000
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    command: >
      sh -c "alembic upgrade head &&
             uvicorn app.main:app --host 0.0.0.0 --port 8000"
    ports:
      - "8000:8000"
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped

  scheduler:
    build: .
    command: supercronic /app/crontab
    volumes:
      - ./data:/app/data
    env_file:
      - .env
    restart: unless-stopped

  caddy:
    image: caddy:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile
      - caddy_data:/data
      - caddy_config:/config
    depends_on:
      - web
    restart: unless-stopped

volumes:
  caddy_data:
  caddy_config:
```

### Caddyfile

```
{$DOMAIN} {
    handle /api/* {
        reverse_proxy web:8000
    }
    handle {
        reverse_proxy web:8000
    }
}
```

### crontab

```cron
# UTC 20:00 = 北京 04:00 清理
0 20 * * * cd /app && python -m app.cli cleanup >> /app/data/logs/cron.log 2>&1

# UTC 21:00 = 北京 05:00 备份
0 21 * * * cd /app && python -m app.cli backup >> /app/data/logs/cron.log 2>&1

# UTC 22:00 = 北京 06:00 每日主流程
0 22 * * * cd /app && python -m app.cli pipeline >> /app/data/logs/cron.log 2>&1
```

---

## 环境变量（.env.example）

```env
# ===== X API =====
X_API_BEARER_TOKEN=xxx                   # 必填

# ===== Claude API =====
ANTHROPIC_API_KEY=xxx                    # 必填
CLAUDE_MODEL=claude-sonnet-4-20250514    # 可选，默认值如左
CLAUDE_INPUT_PRICE_PER_MTOK=3.0          # 可选，默认 $3/MTok
CLAUDE_OUTPUT_PRICE_PER_MTOK=15.0        # 可选，默认 $15/MTok

# ===== Gemini API（可选）=====
GEMINI_API_KEY=                          # 可选，留空则封面图不可用

# ===== 微信公众号（认证后填写）=====
WECHAT_APP_ID=                           # 可选，MVP 留空
WECHAT_APP_SECRET=                       # 可选，MVP 留空

# ===== JWT =====
JWT_SECRET_KEY=your_jwt_secret           # 必填
JWT_EXPIRE_HOURS=72                      # 可选，默认 72 小时

# ===== 系统 =====
DATABASE_URL=sqlite:///data/zhixi.db     # 可选，运行时自动转 sqlite+aiosqlite
DEBUG=false                              # 可选，true 启用 CORS
TIMEZONE=Asia/Shanghai                   # 可选
LOG_LEVEL=INFO                           # 可选
API_HOST=0.0.0.0                         # 可选
API_PORT=8000                            # 可选

# ===== 域名 =====
DOMAIN=your-domain.com                   # 必填，Caddy HTTPS 证书需要
```

---

## Python 依赖版本

依赖通过 `pyproject.toml` 管理，使用 `uv` 安装。

### pyproject.toml [project.dependencies]（生产）

```
fastapi>=0.115,<1.0
uvicorn[standard]>=0.32
sqlalchemy[asyncio]>=2.0,<3.0
aiosqlite>=0.20
alembic>=1.14
typer>=0.15
httpx>=0.28
anthropic>=0.49
pyjwt>=2.10
bcrypt>=4.2
python-dotenv>=1.0
pydantic>=2.0,<3.0
pydantic-settings>=2.0
google-generativeai>=0.8
```

### pyproject.toml [project.optional-dependencies.dev]（开发/测试）

```
pytest>=8.0
pytest-asyncio>=0.24
respx>=0.22
freezegun>=1.4
ruff>=0.9
pyright>=1.1
import-linter>=2.0
```

---

## 初始大V种子数据

| Handle | 名称 | 领域 | 建议权重 |
|--------|------|------|----------|
| sama | Sam Altman | OpenAI CEO | 1.5 |
| AnthropicAI | Anthropic | AI公司官方 | 1.5 |
| OpenAI | OpenAI | AI公司官方 | 1.5 |
| ylecun | Yann LeCun | Meta AI首席科学家 | 1.3 |
| karpathy | Andrej Karpathy | AI教育/前Tesla AI | 1.3 |
| GoogDeepMind | Google DeepMind | AI实验室官方 | 1.2 |
| huggingface | Hugging Face | 开源AI社区 | 1.2 |
| jimfan | Jim Fan | NVIDIA高级研究经理 | 1.0 |
| _jasonwei | Jason Wei | AI研究员 | 1.0 |
| swaborelabs | Swyx | AI工程师/作者 | 1.0 |

> 以上为初始建议，开发时通过 X API 验证正确性，首次部署后通过后台管理页面添加。
