# Git 工作流与 CI/CD 设计

> **日期**: 2026-03-19
> **状态**: 已批准

---

## 背景

智曦项目需要建立 Git 工作流和 CI/CD 流程。项目由单人开发，托管在 GitHub，部署方式为 Docker Compose 自托管。MVP 阶段手动部署，CI 只做质量门禁。

---

## 1. 分支策略

### 主分支

`main` — 始终可运行、可部署。禁止直接 push，必须走 PR。

### Feature 分支

**命名规则**：`us-{编号}-{简短描述}`

| 场景 | 示例 |
|------|------|
| 单个 US | `us-001-project-skeleton` |
| 并行组合并 | `us-011-012-fetcher-classifier` |
| 非 US 变更 | `chore/ci-setup`、`fix/login-lockout` |

### 合并方式

**Squash Merge** — 每个 PR 在 main 上产生一个干净的 commit，保持线性历史。PR 标题即为 main 上的 commit message。

### 分支生命周期

1. `git checkout -b us-xxx-desc main`
2. 在 branch 上开发、commit
3. `git push -u origin us-xxx-desc`
4. `gh pr create` 创建 PR
5. CI 全部通过 → Squash Merge
6. 删除远程 feature branch

---

## 2. Conventional Commits

**格式**：`<type>(<scope>): <描述>`

### type 类型

| type | 用途 |
|------|------|
| `feat` | 新功能 |
| `fix` | 修复 bug |
| `docs` | 文档变更 |
| `test` | 测试相关 |
| `refactor` | 重构（不改变外部行为） |
| `chore` | 构建、CI、依赖等杂项 |
| `style` | 格式化（不影响逻辑） |

### scope 范围

| scope | 对应 |
|-------|------|
| `fetcher` | M1 数据采集 |
| `processor` | M2 AI 加工 |
| `digest` | M3 草稿组装 |
| `publisher` | M4 发布 |
| `infra` | M5 共享基础设施（DB、auth、config、clients） |
| `admin` | M6 前端 |
| `ci` | CI/CD 配置 |
| `deploy` | Docker/部署相关 |

### 示例

- `feat(fetcher): 实现 BaseFetcher 抽象基类`
- `test(processor): 添加热度计算测试用例`
- `chore(ci): 添加 GitHub Actions 工作流`
- `fix(infra): 修复 JWT 过期时间计算`

---

## 3. CI 工作流（GitHub Actions）

### 触发条件

- `push` 到所有非 main 分支（覆盖 `us-*`、`chore/*`、`fix/*` 等所有分支命名）
- `pull_request` 目标为 `main`

### Job 结构

三个 Job：backend 始终运行，frontend 和 codegen 条件激活（对应目录存在时才运行）：

```yaml
# .github/workflows/ci.yml

name: CI

on:
  push:
    branches-ignore: [main]
  pull_request:
    branches: [main]

jobs:
  backend:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: uv sync --dev
      - run: uv run ruff check .
      - run: uv run ruff format --check .
      - run: uv run lint-imports
      - run: uv run pyright
      - run: uv run pytest

  frontend:
    runs-on: ubuntu-latest
    if: hashFiles('admin/package.json') != ''
    steps:
      - uses: actions/checkout@v4
      - uses: oven-sh/setup-bun@v2
      - run: cd admin && bun install --frozen-lockfile
      - run: cd admin && bunx biome check .
      - run: cd admin && bunx vue-tsc --noEmit
      - run: cd admin && bun run build

  codegen:
    runs-on: ubuntu-latest
    needs: [backend]
    if: hashFiles('packages/openapi-client/package.json') != ''
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - uses: oven-sh/setup-bun@v2
      - run: uv sync --dev
      - run: make gen
      - run: git diff --exit-code || (echo "生成物过期，请本地运行 make gen 并提交" && exit 1)
```

> **条件激活说明**：P0/P1 阶段只有 backend job 运行。P2 创建 `admin/` 后 frontend job 激活，创建 `packages/openapi-client/` 后 codegen job 激活。分支保护规则只要求已激活的 Job 通过。

> MVP 阶段 Playwright E2E 测试仅在本地运行，不纳入 CI。待 P2 前端完成后补充 CI E2E 步骤。

### 分支保护规则

在 GitHub Settings > Branches > Branch protection rules 中配置 `main`：

- **Require status checks to pass before merging**: 启用
  - 必需通过：`backend`（始终）
  - 条件必需：`frontend`（admin/ 存在时）、`codegen`（packages/ 存在时）
  - **注**：GitHub 对 skipped job 视为通过，条件不满足时不阻塞合并
- **Require branches to be up to date before merging**: 启用
- **Do not allow bypassing the above settings**: 启用（即使紧急修复也必须走 PR + CI，确保 main 始终可验证）
- **Require a pull request before merging**: 启用
  - Required approvals: 0（单人开发）
- **Allow squash merging only**: 启用

---

## 4. Pre-commit Hook

### 策略

Hook 只跑秒级快速检查，重型检查留给 CI：

| Hook 中运行（快，<3 秒） | 仅 CI 中运行（慢） |
|--------------------------|---------------------|
| `ruff check` | `pyright` |
| `ruff format --check` | `pytest` |
| `biome check` | `vue-tsc --noEmit` |
| | `bun run build` |

### 实现

使用 `.githooks/pre-commit` shell 脚本，项目初始化时通过 `git config core.hooksPath .githooks` 激活。

Hook 有意对全项目执行检查（而非仅 staged 文件），确保任何 commit 时项目整体 lint 状态干净。

```bash
#!/usr/bin/env bash
set -e

# 检测是否有 Python 文件变更
PY_CHANGED=$(git diff --cached --name-only --diff-filter=ACMR -- '*.py' | head -1)
if [ -n "$PY_CHANGED" ]; then
  echo "== ruff check =="
  uv run ruff check .
  echo "== ruff format --check =="
  uv run ruff format --check .
fi

# 检测是否有前端文件变更（仅 admin/ 存在时）
ADMIN_CHANGED=$(git diff --cached --name-only --diff-filter=ACMR -- 'admin/' | head -1)
if [ -n "$ADMIN_CHANGED" ] && [ -f admin/package.json ]; then
  echo "== biome check =="
  cd admin && bunx biome check .
fi

echo "Pre-commit checks passed."
```

---

## 5. PR 模板

```markdown
## Summary
<!-- 变更摘要，关联的 US 编号 -->

## Changes
-

## Contract
- [ ] OpenAPI 无变更 / 已更新

## Tests
- [ ] 新增或更新的测试用例

## Migration
- [ ] 无 DB 迁移 / 已包含迁移脚本

## Checklist
- [ ] ruff check 通过
- [ ] pyright 通过
- [ ] biome check 通过
- [ ] vue-tsc 通过
- [ ] pytest 通过
- [ ] bun run build 通过

## Compliance
<!-- 合规检查结果（参考约束文档第 24 条），无变更可删除此节 -->

## Exceptions
<!-- 若有规则例外，列出编号和到期策略；无则写"无" -->
无
```

---

## 6. .gitignore

```gitignore
# Python
__pycache__/
*.pyc
*.pyo
.venv/
.ruff_cache/
.pyright/
*.egg-info/
.pytest_cache/
htmlcov/
.coverage

# Node / bun
node_modules/
admin/dist/
admin/.vite/

# 项目数据（运行时生成）
data/
*.db
*.db-journal
*.db-wal

# 环境变量
.env
.env.local

# IDE
.vscode/
.idea/
*.swp
*.swo
.DS_Store
```

> 注：`uv.lock` 和 `bun.lock` 是锁定文件，**必须提交**到版本控制，不应忽略。

---

## 7. 涉及文件清单

### 新增文件

| 文件 | 说明 |
|------|------|
| `.github/workflows/ci.yml` | CI 工作流 |
| `.github/pull_request_template.md` | PR 模板 |
| `.githooks/pre-commit` | Pre-commit hook 脚本 |
| `.gitignore` | 忽略规则 |

### 需同步更新的 spec 文件

| 文件 | 更新内容 |
|------|----------|
| `docs/spec/directory-structure.md` | 补充 `.github/`、`.githooks/`、`.gitignore` |
| `docs/spec/constraints.md` | 补充 Git/CI 工作流章节 |
| `CLAUDE.md` | 补充分支策略和 PR 流程说明 |

---

## 8. Bootstrap（项目引导）

Bootstrap 分三个阶段递进，与 US 实施阶段对齐：

### Phase 0：Git/CI 初始化（US-001 之前）

纯基础设施，不涉及应用代码：

1. `git init`
2. 创建 GitHub 私有仓库（`gh repo create zhixi --private`）
3. 创建以下文件：
   - `.gitignore`
   - `.githooks/pre-commit`
   - `.github/workflows/ci.yml`
   - `.github/pull_request_template.md`
   - `Makefile`（仅包含 setup/lint/test target，gen target 留空壳）
4. `git config core.hooksPath .githooks`
5. 初始 commit 包含：现有 docs/、CLAUDE.md + 以上文件
6. push 到 main（**唯一一次直接 push**，此后全部走 PR）
7. 配置 GitHub 分支保护规则（此时只需 `backend` job 通过）

### Phase 1：后端骨架就绪（US-001 完成后）

US-001 创建 `pyproject.toml`、`app/` 目录结构后：
- `make setup` 的后端部分可用（`uv sync --dev`）
- CI backend job 完整运行
- `make lint` 的后端部分可用

### Phase 2：前端+生成链路就绪（US-039 完成后）

US-039 创建 `admin/`、`packages/openapi-client/` 后：
- `make setup` 全部可用
- CI frontend 和 codegen job 自动激活
- `make gen` 可用
- `make lint` 全部可用

Bootstrap 完成后，后续所有变更走 Feature Branch + PR 流程。

---

## 9. 开发工作流

### 单轮循环（每次会话）

```
┌─ 1. 启动 ──────────────────────────────────────────────┐
│  读取 user-stories.md 状态追踪表 + memory               │
│  确定本轮并行 US 组                                      │
│  创建 feature branch（us-xxx-desc）                      │
└──────────────────────────────────────────────────────────┘
         ↓
┌─ 2. 计划 ──────────────────────────────────────────────┐
│  读取对应 spec（architecture + data-model + 对应 US）    │
│  进入 plan 模式                                          │
│  写实施计划到 docs/plans/us-xxx-xxx.md                   │
│  用户确认计划                                            │
└──────────────────────────────────────────────────────────┘
         ↓
┌─ 3. 实施 ──────────────────────────────────────────────┐
│  TDD：先写失败测试 → 再写实现 → 测试通过                 │
│  互不依赖的 US 使用并行 agent 同时推进                    │
│  同一并行组内模型变更集中在一次 Alembic 迁移中            │
└──────────────────────────────────────────────────────────┘
         ↓
┌─ 4. 收尾 ──────────────────────────────────────────────┐
│  更新 user-stories.md 状态追踪表（✅ 已完成）             │
│  提交代码 + push 分支 + gh pr create 得到 PR URL          │
│  一次性回填 docs/plans/us-xxx.md（五项含 PR 链接）        │
│  写入 memory（新决策、新踩坑）                            │
│  push 追加到 PR 分支 → CI 通过 → Squash Merge            │
│  如为阶段最后一组 → 执行阶段验证门槛，汇报用户            │
└──────────────────────────────────────────────────────────┘
         ↓
       /clear → 下一轮
```

### 实施计划文件

- **目录**：`docs/plans/`
- **命名**：`us-{编号}-{内容概要}.md` — 编号后必须附带能概括实施内容的描述，使人仅看文件名即可知道该计划做了什么
  - 单个 US：`us-002-alembic-initial-migration.md`
  - 并行组：`us-011-012-base-fetcher-tweet-classifier.md`
  - 反例（禁止）：`us-002.md`、`us-011-012.md`（纯编号无法辨识内容）
- **实施前内容**：需要创建/修改的文件清单、实现策略、关键决策、测试要点
- **实施后补充**：交付物清单、偏离项表格、问题与修复、质量门禁详表、PR 链接。**在 PR 创建后一次性回填**，禁止分多次
- **生命周期**：随 PR 提交，**永久保留**作为完整的实施记录（计划 + 执行结果）

### 测试策略

- **TDD**：每个 US 先写失败测试，再写实现，测试通过后 US 才算完成
- 每个 US 必须有测试覆盖，不依赖专门的测试 US（US-047/048/049 等是额外验收点）
- 测试基础设施：内存 SQLite、外部 API 全 mock、无网络无 Key 确定性通过
- LLM mock 数据存放在 `tests/fixtures/` 目录下，按模块组织

### 审核方式

- **自动流转**：测试通过 + CI 通过 → Squash Merge，不需要用户逐次确认
- **阻断时找用户确认**：CI 失败、spec 歧义（契约级）、需求不明确时停下来沟通
- **阶段验证**：每个 P 阶段最后一组 US 完成后，执行 implementation-plan.md 中的阶段验证门槛，结果汇报用户

### Spec 歧义处理

- 影响数据模型或 API 契约的歧义 → 停下来问用户
- 纯实现细节的歧义 → 自行判断，在 PR 中注明决策理由

### 会话间状态保持

- **`/clear` 前必做**：更新 user-stories.md 状态 + 写入 memory
- **唯一事实源**：`docs/spec/user-stories.md` 状态追踪表
- **新会话开始**：先读 user-stories.md 状态追踪表 + memory，确认当前进度和下一组 US
