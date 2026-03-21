# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

智曦（ZhiXi）— AI 知识日报平台。自动抓取 Twitter/X 上 AI 领域大V推文，经 AI 过滤、话题聚合、翻译、点评后，生成每日精选内容供微信公众号发布。

## 文档索引

| 文件 | 内容 | 加载时机 |
|------|------|----------|
| `docs/spec/architecture.md` | 模块划分、工程基础设施、API 契约 | 实现任何模块时 |
| `docs/spec/data-model.md` | 全部表结构、Pydantic 类型、状态机 | 涉及数据操作时 |
| `docs/spec/user-stories.md` | 全部 US + 状态追踪表 | 实现具体功能时 |
| `docs/spec/prompts.md` | AI Prompt 模板 + Markdown 渲染模板 | 实现 M2/M3 时 |
| `docs/spec/implementation-plan.md` | 实施路线图（顺序+并行策略） | 规划开发顺序时 |
| `docs/spec/constraints.md` | 约束、部署、环境变量、依赖版本 | 配置和部署时 |
| `docs/spec/directory-structure.md` | 完整目录结构 | 创建文件时 |
| `docs/spec/git-ci.md` | Git 工作流、CI/CD、分支策略、PR 模板 | Git/CI 相关操作时 |
| `docs/ZhiXi_Final_Spec_v1.md` | 原始完整规范（归档） | 拆分文档有歧义时 |

## 技术栈

| 层级 | 选型 |
|------|------|
| 后端 | FastAPI + Python 3.12+ + 异步 SQLAlchemy 2.x + aiosqlite + Alembic |
| 后端依赖管理 | uv |
| 数据库 | SQLite (WAL)，需兼容 PostgreSQL |
| 前端 | Vue 3 (Composition API) + TypeScript + Vant 4 + Vite |
| 前端运行时 | bun |
| AI | Anthropic Claude API (Sonnet)，可选 Google Gemini（封面图） |
| 认证 | JWT (PyJWT) + bcrypt |
| HTTP | httpx (async) |
| CLI | Typer（asyncio.run 桥接） |
| 部署 | Docker Compose（web + scheduler + caddy） |

## 核心规范

1. **全异步**: 路由、Service、CRUD 均 `async def`，DB 操作用 `await`
2. **Service DI**: 构造函数注入 `AsyncSession`，`app/api/deps.py` 组装
3. **事务管理**: `get_db()` 统一 auto-commit/auto-rollback
4. **模块隔离**: fetcher/ 禁止 import processor/，跨模块只能通过 Service 层
5. **快照编辑**: 管理员编辑只改 `digest_items.snapshot_*`，源表保持 AI 原始值
6. **Prompt 安全**: 所有 AI Prompt 开头注入安全声明
7. **API Key 安全**: 仅 `.env` 存储，不经 API 传输/回显
8. **中文规范**: 所有 Python 文件中文 docstring，错误消息中文面向用户
9. **检查闭环**: 禁止通过 ignore、disable、suppress 等方式跳过任何 lint/类型/测试检查，除非同时由另一工具覆盖同等检测能力并在提交时说明闭环关系（例：biome 对 .vue 关闭 noUnusedVariables → vue-tsc noUnusedLocals 接管）。单纯关闭检查视为未通过质量门禁

## 模块概览

```
API 路由层 (app/api/)          — 无业务逻辑，委托 Service
Service 编排层 (app/services/) — 业务编排、事务管理
├─ M1 Fetcher   (app/fetcher/)    — 数据采集（tweets, accounts, fetch_log）
├─ M2 Processor (app/processor/)  — AI 加工（topics, tweets AI 字段）
├─ M3 Digest    (app/digest/)     — 草稿组装（daily_digest, digest_items）
└─ M4 Publisher  (app/publisher/) — 内容发布
M5 共享基础设施 (app/clients/ + crud.py + auth.py)
M6 Admin 前端  (admin/src/)       — Vue 3 + TypeScript + Vant 4 移动端优先
```

## 常用命令

### 后端
```bash
uvicorn app.main:app --reload --port 8000  # 开发服务器
python -m app.cli pipeline                 # 全流程
python -m app.cli backup                   # 数据库备份
python -m app.cli cleanup                  # 清理旧备份和日志
python -m app.cli unlock                   # 解锁卡住的任务
pytest                                     # 全部测试
pytest tests/test_heat_calculator.py -k "test_single"  # 单个测试
```

### 前端
```bash
cd admin && bun dev                        # Vite dev（代理到 8000）
cd admin && bun run build                  # 生产构建
```

### 代码生成（P2 之后可用）
```bash
make gen                                   # 统一全链路生成（OpenAPI → TS 客户端）
```

生成链路：后端 FastAPI `/openapi.json` → `@hey-api/openapi-ts` → `packages/openapi-client/src/gen/`。
生成物禁止手动修改，扩展逻辑写在 gen/ 目录之外。

### 质量门禁
```bash
# 后端
ruff check .                               # Lint
ruff format --check .                      # 格式化检查
pyright                                    # 类型检查

# 前端
cd admin && bunx biome check .             # Lint + 格式化
cd admin && bunx vue-tsc --noEmit          # 类型检查
cd admin && bunx playwright test           # E2E 测试

# 生成物一致性
make gen && git diff --exit-code           # 生成后工作区无 diff
```

### 部署
```bash
docker-compose up -d                       # 启动 3 容器
```

## 测试规范

- **TDD**：先写失败测试，再写实现，每个 US 必须有测试覆盖
- 每测试独立内存 SQLite（`sqlite+aiosqlite://`）
- httpx `AsyncClient` + `ASGITransport` + `dependency_overrides`
- Mock: Claude→AsyncMock, X API→respx, 时间→freezegun
- `asyncio_mode = "auto"`
- 所有外部 API 必须 mock，无网络无 Key 确定性通过

## Git 工作流

- **分支策略**: Feature Branch + PR，Squash Merge 到 main（详见 `docs/spec/git-ci.md`）
- **命名**: `us-{编号}-{描述}`，非 US 变更用 `chore/`、`fix/` 等
- **Commit**: Conventional Commits（`<type>(<scope>): <描述>`）
- **CI**: GitHub Actions 严格阻断，后端+前端并行检查
- **Pre-commit**: ruff + biome 快速检查

## 工作流规则

**每轮循环**（详见 `docs/spec/git-ci.md` §9）：

### 步骤 1: 预读（每轮必做，不可跳过）

| 必读文件 | 目的 | 何时读 |
|---------|------|--------|
| `docs/spec/user-stories.md` | 确定本轮 US 组（状态追踪表） | 每轮开始 |
| Memory 全部文件 | 回顾过往决策、反馈、踩坑经验 | 每轮开始 |
| `docs/spec/git-ci.md` | 分支策略、PR 模板、CI 规则 | 每轮开始 |
| `docs/plans/` 已有文件 | 确认命名规范和回填格式标准 | 写计划前 |
| `docs/spec/architecture.md` | 模块边界、DI 模式、API 契约 | 涉及代码实现时 |
| `docs/spec/data-model.md` | 表结构、Pydantic 类型、状态机 | 涉及数据操作时 |
| `docs/spec/constraints.md` | 技术禁止项、安全约束 | 涉及代码实现时 |

### 步骤 2: 创建分支

**在写任何代码之前**，必须先创建 feature branch：
```bash
git checkout -b us-{编号}-{描述}
```
禁止直接在 main 上提交代码。

### 步骤 3: 编写计划

进入 plan 模式 → 写实施计划到 `docs/plans/us-{编号}-{描述性英文名}.md`

### 步骤 4: TDD 实施

先写测试 → 再写实现

### 步骤 5: 收尾（五步缺一不可）

1. **user-stories.md**: 更新状态为 ✅ 已完成
2. **提交 + push + 创建 PR**: 推送分支 → `gh pr create` 得到 PR URL
3. **docs/plans/**: 一次性回填执行结果（**必须包含完整五项**：交付物清单、偏离项表格、问题与修复、质量门禁详表、PR 链接）。回填必须在 PR 创建之后，一次完成，禁止分多次回填
4. **memory**: 更新记忆（新决策、新踩坑）
5. **push 追加 + Merge**: 将回填 commit push 到 PR 分支 → CI 通过 → Squash Merge 到 main

### 步骤 6: `/clear` → 下一轮

**通用规则**：
- 每个 US 是独立可测试单元
- 最小改动原则，不确定时写测试确认
- 自动流转（CI 通过 → Merge），阻断时找用户确认
- Spec 歧义：影响契约的问用户，实现细节自行判断并在 PR 注明
- 每个 P 阶段结束执行阶段验证门槛，结果汇报用户

## Compaction 保留指令

上下文压缩时必须保留：
- 本文件全部内容
- 当前正在实施的 US 编号和阶段
- 已完成的阶段列表
- 未解决的错误或阻塞项
