# 智曦 ZhiXi

AI 知识日报平台 — 自动抓取 Twitter/X 上 AI 领域大V推文，经 AI 过滤、话题聚合、翻译、点评后，生成每日精选内容供微信公众号发布。

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | FastAPI + Python 3.12+ + 异步 SQLAlchemy 2.x |
| 数据库 | SQLite (WAL 模式) |
| 前端 | Vue 3 + TypeScript + Vant 4 + Vite |
| AI | Anthropic Claude API (Sonnet) |
| 部署 | Docker Compose (web + scheduler + caddy) |

## 快速开始

```bash
# 1. 安装依赖
uv sync --dev

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env 填入 API Key

# 3. 初始化数据库
uv run alembic upgrade head

# 4. 启动开发服务器
uv run uvicorn app.main:app --reload --port 8000
```

## 常用命令

```bash
# 全流程
python -m app.cli pipeline

# 数据库备份
python -m app.cli backup

# 清理旧备份和日志
python -m app.cli cleanup

# 解锁卡住的任务
python -m app.cli unlock
```

## 质量门禁

```bash
uv run ruff check .           # Lint
uv run ruff format --check .  # 格式化检查
uv run pyright                # 类型检查
uv run pytest                 # 测试
```

## 项目结构

```
app/            后端应用
├── api/        路由层（无业务逻辑）
├── services/   编排层（业务逻辑）
├── models/     SQLAlchemy 模型
├── schemas/    Pydantic 类型
├── fetcher/    M1 数据采集
├── processor/  M2 AI 加工
├── digest/     M3 草稿组装
├── publisher/  M4 内容发布
└── clients/    外部 API 客户端
admin/          Vue 3 前端
tests/          测试
docs/spec/      项目规范
```
