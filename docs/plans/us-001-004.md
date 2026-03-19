# US-001 + US-004 实施计划

> 状态: ✅ 已完成 | 分支: `us-001-004-skeleton-logging` | PR: #1 (merged)

## Context

项目首轮开发。仓库仅有 spec 文档和 CI 基础设施（.gitignore, Makefile, .github/, .githooks/），尚无任何代码文件。本轮创建完整项目骨架 + 日志系统，为后续所有 US 奠定基础。

## 分支

`us-001-004-skeleton-logging`

---

## 第一部分：US-001 项目骨架初始化

### Step 1: pyproject.toml

创建 `pyproject.toml`，内容包括：
- `[project]` 元数据（name=zhixi, version=0.1.0, python>=3.12）
- `[project.dependencies]` — 完整生产依赖（来自 `docs/spec/constraints.md`）
- `[project.optional-dependencies.dev]` — 开发依赖
- `[tool.ruff]` — target-version="py312", line-length=100, select/ignore 规则
- `[tool.pyright]` — pythonVersion="3.12", typeCheckingMode="basic"
- `[tool.pytest.ini_options]` — asyncio_mode="auto", testpaths=["tests"]
- `[tool.importlinter]` — 模块边界约束（constraints.md 中的规则）

### Step 2: .env.example

复制 `docs/spec/constraints.md` 中的完整环境变量模板。

### Step 3: app/config.py

- `Settings(BaseSettings)` 类 — 所有环境变量字段（architecture.md 参考实现）
- `settings = Settings()` 模块级单例
- `get_today_digest_date() -> date` — 北京时间自然日
- `get_fetch_window(digest_date) -> tuple[datetime, datetime]` — 前一日06:00~当日05:59
- `get_system_config(db, key, default) -> str` — 从 DB system_config 读取

### Step 4: app/database.py

按 architecture.md 参考实现：
- `Base(DeclarativeBase)` — ORM 基类
- `get_async_url()` — sqlite:/// → sqlite+aiosqlite:///
- `engine` — 异步引擎
- `set_sqlite_pragma` — WAL + busy_timeout=5000
- `async_session` — sessionmaker
- `get_db()` — 依赖注入（auto-commit/rollback）

### Step 5: app/models/ — 全部模型定义

在 US-001 中创建完整模型（data-model.md 完整定义），因为：
1. config.py 需要 SystemConfig 模型
2. conftest.py 需要创建内存表
3. pyright 需要完整类型

文件列表：
- `__init__.py` — 集中注册所有模型
- `account.py` — TwitterAccount
- `tweet.py` — Tweet
- `topic.py` — Topic
- `digest.py` — DailyDigest
- `digest_item.py` — DigestItem（含联合唯一约束）
- `config.py` — SystemConfig（键值表）
- `fetch_log.py` — FetchLog
- `job_run.py` — JobRun
- `api_cost_log.py` — ApiCostLog

### Step 6: app/schemas/ — Pydantic 类型

按 data-model.md 的 Pydantic 类型定义：
- `fetcher_types.py` — TweetType, RawTweet, FetchResult, KEEP_TYPES 等
- `client_types.py` — ClaudeResponse
- `processor_types.py` — AnalysisResult, ProcessResult, TopicResult
- `digest_types.py` — ReorderInput
- `publisher_types.py` — PublishResult
- `report_types.py` — 空占位

### Step 7: app/main.py — FastAPI 入口

- lifespan context manager（engine.dispose）
- app = FastAPI(title="智曦 API", version="1.0.0")
- CORS 仅 DEBUG 模式
- 8 组 router include（从 stub router 导入）
- SPA 静态文件挂载（条件判断 admin/dist 存在）

### Step 8: app/cli.py — Typer CLI

- `pipeline` / `backup` / `cleanup` / `unlock` 子命令
- 均为 stub（`asyncio.run()` 桥接，内部 TODO）

### Step 9-14: stub 模块

- `app/crud.py` — 通用 CRUD 占位
- `app/auth.py` — 认证占位
- `app/api/` — 8 个路由 stub + deps.py
- `app/services/` — 6 个 service stub
- `app/clients/` — claude_client, gemini_client, notifier
- `app/fetcher/`, `app/processor/`, `app/digest/`, `app/publisher/` — 业务模块 stub

### Step 15: tests/conftest.py

按 architecture.md 参考实现：
- `db_engine` fixture — 内存 SQLite
- `db` fixture — AsyncSession
- `client` fixture — httpx AsyncClient + ASGITransport
- `seeded_db` fixture — 预置 system_config 默认数据

### Step 16: README.md

中文项目说明（项目名称、功能概述、技术栈、快速开始、开发命令）。

### Step 17: import-linter 配置

在 pyproject.toml `[tool.importlinter]` 中配置模块边界规则。

---

## 第二部分：US-004 日志系统

### Step 1: app/logging_config.py

- `setup_logging(log_level: str)` — 初始化日志系统
- JSON 格式化器（每行一个 JSON: timestamp, level, message, module, request_id）
- `TimedRotatingFileHandler` — 按天轮转，保留 30 天
- 控制台同时输出
- 后端日志英文

### Step 2: app/middleware.py — request_id 中间件

- `RequestIdMiddleware(BaseHTTPMiddleware)`
- UUID4 + `contextvars.ContextVar`
- 响应头 `X-Request-ID`

### Step 3: 更新 app/main.py

- lifespan 中调用 `setup_logging()`
- 添加 RequestIdMiddleware

### Step 4: tests/test_logging.py

- JSON 格式校验、必要字段、request_id 上下文、日志级别过滤、中间件响应头

---

## 实施顺序（TDD）

1. 写 config 测试 → 实现 config.py
2. 实现 database.py
3. 创建 models、schemas、stub 文件
4. 创建 main.py、cli.py、api/service/client stubs
5. 创建 conftest.py
6. 写日志测试 → 实现 logging_config.py + middleware.py
7. 创建 README.md、.env.example
8. 运行质量门禁，修复所有错误

## 实施结果

### 交付物

- 81 个文件变更（+3151 行），完整目录结构与 `docs/spec/directory-structure.md` 一致
- 10 个 SQLAlchemy 模型全部定义完成（使用通用类型，兼容 PostgreSQL）
- 6 个 Pydantic schema 文件
- 16 个测试用例全部通过

### 与计划的偏离

| 偏离点 | 计划 | 实际 | 原因 |
|--------|------|------|------|
| `_utcnow` 辅助函数 | 直接用 `datetime.utcnow` | 用 `datetime.now(UTC)` + `_utcnow()` 封装 | ruff UP017 规则要求不用已弃用的 `utcnow()` |
| TweetType 基类 | `str, Enum` | `StrEnum` | ruff UP042 自动修复 |
| pyright venvPath | 未预见 | 需在 pyproject.toml 添加 `venvPath`/`venv` | pyright 默认不读取 `.venv`，导致找不到测试依赖 |
| Settings 实例化 | 无特殊处理 | 添加 `# type: ignore[call-arg]` | pyright 不理解 pydantic-settings 的 .env 注入 |
| freezegun tz_offset | `tz_offset=8` | 改用 `+08:00` 时区字符串 | `tz_offset` 与 `datetime.now(tz)` 交互不符预期 |

### CI 问题与修复

1. `astral-sh/setup-uv@v4` 不存在 → 改为 `@v7`
2. `uv sync --dev` 不安装 `optional-dependencies` → 改为 `--all-extras`
3. CI 环境无 `.env` → 在 workflow `env:` 中注入测试值
4. `hashFiles()` 在 job 级 `if` 导致 workflow 解析失败 → P0 暂移除 frontend/codegen jobs
5. 私有仓库 Actions 额度受限 → 转为公开仓库

### 质量门禁

| 检查项 | 结果 |
|--------|------|
| ruff check | ✅ 通过 |
| ruff format | ✅ 通过 |
| lint-imports | ✅ 4/4 contracts kept |
| pyright | ✅ 0 errors |
| pytest | ✅ 16/16 passed |
| CI (GitHub Actions) | ✅ 通过 |

### PR

- PR #1: https://github.com/neuer/zhixi/pull/1
- Squash merged → main
