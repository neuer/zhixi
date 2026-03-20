# US-039: Vue 项目初始化 实施计划

## Context

P2 后端 API 已全部完成（US-007/008/023/024/025/030-034），但前端尚未创建。US-039 是前端开发的入口，需要搭建 Vue 3 + TypeScript + Vant 4 完整基础设施，包括 OpenAPI 客户端生成链路、路由守卫、axios 拦截器、质量门禁工具链。后续 US-040（Dashboard）、US-041（设置页）等均依赖此基础设施。

## 实施策略

分 3 个阶段递进：先搭建 OpenAPI 生成链路（packages/），再初始化 Vue 项目骨架（admin/），最后验证全链路通过。

---

## 阶段 1: OpenAPI 客户端生成链路

### 1.1 创建 `packages/openapi-client/`

**新建文件：**

| 文件 | 说明 |
|------|------|
| `packages/openapi-client/package.json` | bun 包配置，依赖 `@hey-api/openapi-ts` |
| `packages/openapi-client/openapi-ts.config.ts` | 生成配置：输入 `../../openapi.json`，输出 `src/gen/` |
| `packages/openapi-client/tsconfig.json` | TypeScript 配置 |

**关键决策：**
- `@hey-api/openapi-ts` 使用最新稳定版
- 输出目录 `src/gen/`，生成 types + services
- 不生成 Zod schemas（EXC-20260319-004，Vant 原生表单校验即可）

### 1.2 运行 `make gen`

- 后端导出 `openapi.json` → `@hey-api/openapi-ts` 生成 TS 客户端
- 验证 `packages/openapi-client/src/gen/` 下有生成物
- Makefile 已有正确的 `gen-openapi` target，无需修改

---

## 阶段 2: Vue 项目骨架

### 2.1 项目初始化（admin/）

**新建文件：**

| 文件 | 说明 |
|------|------|
| `admin/package.json` | Vue 3 + Vant 4 + vue-router + axios + TypeScript + Vite |
| `admin/tsconfig.json` | strict 模式 |
| `admin/tsconfig.node.json` | Vite 配置用 Node 环境 TS |
| `admin/env.d.ts` | `/// <reference types="vite/client" />` |
| `admin/vite.config.ts` | 代理 `/api` → `localhost:8000`，`@` 别名 |
| `admin/biome.json` | biome lint/格式化规则 |
| `admin/index.html` | SPA 入口 HTML |

### 2.2 核心源码

| 文件 | 说明 |
|------|------|
| `admin/src/main.ts` | 应用入口：创建 app + Vant + router |
| `admin/src/App.vue` | 根组件：`<router-view />` |
| `admin/src/api/index.ts` | axios 实例 + JWT 拦截器 + 401 重定向 + 错误 toast |
| `admin/src/router/index.ts` | 10 条路由 + beforeEach 守卫（setup 检查 + JWT 检查） |

### 2.3 路由定义

| 路由 | 组件 | 认证 |
|------|------|------|
| `/setup` | Setup.vue | 白名单 |
| `/login` | Login.vue | 白名单 |
| `/dashboard` | Dashboard.vue | JWT |
| `/accounts` | Accounts.vue | JWT |
| `/digest` | Digest.vue | JWT |
| `/digest/edit/:type/:id` | DigestEdit.vue | JWT |
| `/history` | History.vue | JWT |
| `/history/:id` | HistoryDetail.vue | JWT |
| `/settings` | Settings.vue | JWT |
| `/preview` | Preview.vue | 白名单（token 参数） |

**路由守卫逻辑：**
1. 白名单路由（`/setup`, `/login`, `/preview`）直接通过
2. 首次加载调用 `GET /api/setup/status`，缓存 `need_setup`
3. `need_setup === true` → 重定向 `/setup`
4. 无 `localStorage('zhixi_token')` → 重定向 `/login`

### 2.4 View 占位组件

所有 10 个 View 创建为占位组件（`<script setup lang="ts">` + 简单标题），具体实现留给 US-040/041 等。

### 2.5 Playwright 配置

| 文件 | 说明 |
|------|------|
| `admin/playwright.config.ts` | Playwright 基础配置 |

MVP 阶段 E2E 仅本地运行，不纳入 CI。配置文件就绪即可。

---

## 阶段 3: 验证

### 3.1 质量门禁

```bash
cd admin && bun install
cd admin && bunx biome check .          # lint + 格式化
cd admin && bunx vue-tsc --noEmit       # 类型检查
cd admin && bun run build               # 生产构建
make gen && git diff --exit-code        # 生成物一致性
```

### 3.2 后端测试不受影响

```bash
uv run ruff check .
uv run ruff format --check .
uv run lint-imports
uv run pyright
uv run pytest
```

---

## 关键文件清单

### 新建文件（~20 个）

```
packages/openapi-client/
├── package.json
├── openapi-ts.config.ts
├── tsconfig.json
└── src/gen/                    # make gen 自动生成

admin/
├── package.json
├── bun.lock                    # bun install 自动生成
├── tsconfig.json
├── tsconfig.node.json
├── env.d.ts
├── vite.config.ts
├── biome.json
├── index.html
├── playwright.config.ts
└── src/
    ├── main.ts
    ├── App.vue
    ├── api/index.ts
    ├── router/index.ts
    └── views/
        ├── Setup.vue
        ├── Login.vue
        ├── Dashboard.vue
        ├── Accounts.vue
        ├── Digest.vue
        ├── DigestEdit.vue
        ├── History.vue
        ├── HistoryDetail.vue
        ├── Settings.vue
        └── Preview.vue
```

### 修改文件

无。Makefile 和 CI 已为前端预留了条件激活逻辑。

---

## 测试策略

US-039 为基础设施初始化，测试覆盖方式：
1. **类型检查**: `vue-tsc --noEmit` 通过 = TypeScript strict 无错误
2. **Lint**: `biome check .` 通过 = 代码风格一致
3. **构建**: `bun run build` 成功 = Vite 构建无错误
4. **生成链路**: `make gen && git diff --exit-code` = OpenAPI 生成物一致
5. **后端回归**: `pytest` 全部通过 = 不影响现有功能

---

## 注意事项

- **不使用 Pinia/Vuex**：组件级 `ref()`/`reactive()` + API 调用即可
- **不创建 components/**：US-039 只建 views 占位，组件在对应 US 中创建
- **axios 而非 fetch**：spec 指定 axios + 拦截器模式
- **CI 自动激活**：admin/package.json 创建后，CI frontend job 自动启用

---

## 执行结果

### 交付物清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `packages/openapi-client/package.json` | 新建 | @hey-api/openapi-ts 0.61 + TypeScript 5.7 |
| `packages/openapi-client/openapi-ts.config.ts` | 新建 | 生成配置：input openapi.json → output src/gen/ |
| `packages/openapi-client/tsconfig.json` | 新建 | TS 严格模式 |
| `packages/openapi-client/bun.lock` | 自动生成 | 锁定文件 |
| `packages/openapi-client/src/gen/types.gen.ts` | 自动生成 | 18 个 API 类型定义 |
| `packages/openapi-client/src/gen/index.ts` | 自动生成 | 导出入口 |
| `admin/package.json` | 新建 | Vue 3.5 + Vant 4.9 + vue-router 4.6 + axios 1.7 |
| `admin/tsconfig.json` | 新建 | strict 模式 + references |
| `admin/tsconfig.node.json` | 新建 | composite: true（vite/playwright 用） |
| `admin/env.d.ts` | 新建 | Vite + Vue 类型声明 |
| `admin/vite.config.ts` | 新建 | /api 代理 + @ 别名 |
| `admin/biome.json` | 新建 | lint + 格式化规则 |
| `admin/index.html` | 新建 | SPA 入口（移动端 viewport） |
| `admin/playwright.config.ts` | 新建 | Mobile Chrome + webServer |
| `admin/bun.lock` | 自动生成 | 锁定文件 |
| `admin/src/main.ts` | 新建 | 应用入口 |
| `admin/src/App.vue` | 新建 | 根组件 |
| `admin/src/api/index.ts` | 新建 | axios + JWT 拦截器 + 401 重定向 |
| `admin/src/router/index.ts` | 新建 | 10 条路由 + beforeEach 守卫 |
| `admin/src/views/*.vue` (×10) | 新建 | 占位组件 |
| `docs/spec/user-stories.md` | 修改 | US-039 状态 → ✅ |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | tsconfig.node.json 用 noEmit | 改为 composite: true | vue-tsc 要求 referenced project 必须 composite |

### 问题与修复

| 问题 | 解决 |
|------|------|
| biome 报 import 排序错误 | `biome check --fix --unsafe` 自动修复 |
| tsconfig.node.json noEmit 与 references 冲突 | 改用 composite: true |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| biome check | ✅ 通过 |
| vue-tsc --noEmit | ✅ 通过 |
| bun run build | ✅ 通过（522ms） |
| make gen 一致性 | ✅ 无 diff |
| ruff check | ✅ 通过 |
| ruff format --check | ✅ 通过 |
| lint-imports | ✅ 4 contracts kept |
| pyright | ✅ 0 errors |
| pytest | ✅ 319 passed |

### PR 链接

https://github.com/neuer/zhixi/pull/16
