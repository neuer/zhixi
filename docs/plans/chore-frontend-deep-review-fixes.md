# 前端深度审查修复实施计划

## Context

基于 4 个并行审查 Agent（代码质量、错误处理、类型设计、可维护性）对 `admin/src/` 全部 19 个文件的深度分析，共发现 6 个 Critical、14 个 Important、12 个 Suggestion 问题。本计划将全部 32 项修复按依赖关系和优先级组织为 5 个实施轮次，每轮独立可测试。

**分支命名**: `chore/frontend-deep-review-fixes`

---

## 第 1 轮 — API 层与路由核心缺陷修复

> 目标：修复全局基础设施 `api/index.ts` 和 `router/index.ts` 的全部 Critical + Important。这两个文件的缺陷影响所有视图。
>
> 包含问题：C-1, C-4, C-6, I-1, I-5, I-11, I-12, I-14, S-7, S-11（共 10 项）

### 1.1 C-1: 消除循环依赖
- **文件**: `admin/src/api/index.ts`
- **变更**: 删除第 1 行 `import router from "@/router"`，在 401 拦截器中改用延迟导入：
  ```typescript
  const { default: router } = await import("@/router");
  ```

### 1.2 C-4: 网络断开/超时差异化提示
- **文件**: `admin/src/api/index.ts`
- **变更**: 在响应拦截器开头增加 `error.response` 为空时的 `error.code` 判断：
  - `ECONNABORTED` → "请求超时，请稍后重试"
  - `ERR_NETWORK` → "网络连接失败，请检查网络"
  - 其他 → "网络异常，请稍后重试"

### 1.3 C-6: 使用生成类型替换手写内联类型
- **文件**: `admin/src/router/index.ts`
- **变更**: 第 96 行 `api.get<{ need_setup: boolean }>` → `api.get<SetupStatusResponse>`，顶部添加 `import type { SetupStatusResponse } from "@zhixi/openapi-client"`

### 1.4 I-1: setupStatus 缓存加 TTL
- **文件**: `admin/src/router/index.ts`
- **变更**: `setupStatus: boolean | null` → `setupCache: { value: boolean; fetchedAt: number } | null`，检查 `Date.now() - fetchedAt > 5 * 60 * 1000` 过期，`resetSetupCache()` 改为 `setupCache = null`

### 1.5 I-5: 拦截器排除签名链接 401 跳转
- **文件**: `admin/src/api/index.ts`
- **变更**: 401 分支中检查 `error.config?.url?.includes("/digest/preview/")`，匹配时直接 `return Promise.reject(error)` 不跳转

### 1.6 I-11: 注册全局错误处理器
- **文件**: `admin/src/main.ts`
- **变更**: `app.mount` 前加 `app.config.errorHandler = (err, _instance, info) => { console.error(\`[全局错误] ${info}:\`, err); }`

### 1.7 I-12: ApiError 扩展为联合类型
- **文件**: `admin/src/api/index.ts`
- **变更**: `detail: string` → `detail: string | Array<{ loc: Array<string | number>; msg: string; type: string }>`，拦截器中做类型判断：数组时 `.map(e => e.msg).join("; ")`

### 1.8 I-14: 并发 401 防重复跳转
- **文件**: `admin/src/api/index.ts`
- **变更**: 模块作用域加 `let isRedirectingToLogin = false`，401 分支内包裹 `if (!isRedirectingToLogin)` 守卫，`setTimeout(() => { isRedirectingToLogin = false }, 2000)`

### 1.9 S-7: 提取 token key 常量
- **新建**: `admin/src/constants/index.ts` → `export const AUTH_TOKEN_KEY = "zhixi_token"`
- **修改**: `api/index.ts`（2 处）、`router/index.ts`（1 处）替换硬编码字符串

### 1.10 S-11: 默认超时调整
- **文件**: `admin/src/api/index.ts`
- **变更**: `timeout: 300000` → `timeout: 30000`（30 秒），耗时操作调用方单独传 `{ timeout: 300000 }`

### 验证
```bash
cd admin && bunx vue-tsc --noEmit && bunx biome check .
cd admin && bun dev  # 浏览器控制台无循环引用警告
```

---

## 第 2 轮 — 后端 Schema 枚举化 + OpenAPI 重新生成

> 目标：将后端 Schema 的 `str` 字段改为已有枚举，重新生成前端类型使其自动收窄。这是 I-6/I-7 的根因修复。
>
> 包含问题：I-6, I-7（共 2 项，涉及约 12 个字段）

### 2.1 后端 Schema 枚举化

**`app/schemas/digest_types.py`**:
| 行 | 当前 | 改为 |
|----|------|------|
| 26 | `item_type: str` | `item_type: ItemType` |
| 41 | `snapshot_topic_type: str \| None` | `snapshot_topic_type: TopicType \| None` |
| 53 | `status: str` (DigestBriefResponse) | `status: DigestStatus` |
| 128 | `status: str` (HistoryListItem) | `status: DigestStatus` |

**`app/schemas/dashboard_types.py`**:
| 行 | 当前 | 改为 |
|----|------|------|
| 27 | `status: str \| None` (PipelineStatus) | `status: JobStatus \| None` |
| 35 | `status: str \| None` (DigestStatus) | `status: enums.DigestStatus \| None` |
| 46 | `status: str` (DigestDayRecord) | `status: enums.DigestStatus` |
| 54 | `job_type: str` (AlertItem) | `job_type: JobType` |
| 55 | `status: str` (AlertItem) | `status: JobStatus` |

> **注意**: dashboard_types.py 有类名 `DigestStatus` 与 enums.DigestStatus 冲突，需 `import app.schemas.enums as enums` 后用 `enums.DigestStatus`

**`app/schemas/settings_types.py`**:
| 行 | 当前 | 改为 |
|----|------|------|
| 17 | `publish_mode: str` (SettingsResponse) | `publish_mode: PublishMode` |

### 2.2 重新生成前端类型
```bash
make gen
```

### 2.3 前端去除 `as` 断言
- **文件**: `admin/src/views/Settings.vue`
- **变更**: 第 23 行、第 70 行删除 `as "manual" | "api"` 断言

### 验证
```bash
ruff check . && pyright && pytest
make gen && git diff --exit-code
cd admin && bunx vue-tsc --noEmit && bunx biome check .
```

---

## 第 3 轮 — 视图层 Critical + Important 缺陷修复

> 目标：修复各视图的运行时错误、数据丢失、用户体验问题。
>
> 包含问题：C-2, C-3, C-5, I-2, I-3, I-4, I-8, I-9, I-10, I-13, S-9（共 11 项）
>
> 依赖：第 1 轮（API 层）+ 第 2 轮（生成类型）

### 3.1 C-2: Digest.vue 分离 dialog 取消与 API 失败
- **文件**: `admin/src/views/Digest.vue:33-61`
- **变更**: `handlePublish` 和 `handleRegenerate` 各拆为两个 try-catch：第一个 catch dialog 取消直接 return，第二个 catch API 失败

### 3.2 C-3: History.vue 分页错误不置 finished
- **文件**: `admin/src/views/History.vue:46-48`
- **变更**: catch 中删除 `finished.value = true`，改为不操作（拦截器已 toast）

### 3.3 C-5: ArticlePreview.vue JSON 解析增加元素类型守卫
- **文件**: `admin/src/components/ArticlePreview.vue:22-46`
- **变更**:
  - `parsePerspectives`: `parsed as string[]` → `.filter((x): x is string => typeof x === "string")`
  - `parseSourceTweets`: `parsed as {…}[]` → `.filter()` 检查 `typeof author === "string" && typeof url === "string"`

### 3.4 I-2: formatDate 防御 Invalid Date
- **文件**: `admin/src/utils/format.ts:3-9`
- **变更**: `new Date(dateStr)` 后加 `if (Number.isNaN(d.getTime())) return dateStr`

### 3.5 I-3: History.vue van-list 竞态守卫
- **文件**: `admin/src/views/History.vue:26-51`
- **变更**: 加非响应式 `let isLoadingMore = false`，loadMore 入口检查 + finally 重置

### 3.6 I-4: Dashboard.vue 空值保护
- **文件**: `admin/src/views/Dashboard.vue:117`
- **变更**: `svc.estimated_cost.toFixed(4)` → `(svc.estimated_cost ?? 0).toFixed(4)`

### 3.7 I-8: HistoryDetail.vue route.params.id 校验
- **文件**: `admin/src/views/HistoryDetail.vue:15`
- **变更**: 解析为 Number，NaN 或 ≤0 时设 `error.value = "无效的记录 ID"` 并 return

### 3.8 I-9: ApiCosts.vue 分别 catch
- **文件**: `admin/src/views/ApiCosts.vue:20-25`
- **变更**: `Promise.all` → 两个独立 try-catch，任一失败不影响另一个

### 3.9 I-10: HistoryDetail.vue 区分 404 和其他错误
- **文件**: `admin/src/views/HistoryDetail.vue:21-22`
- **变更**: `catch (e)` 中判断 `axios.isAxiosError(e) && e.response?.status === 404` → "记录不存在"，其他 → "加载失败，请稍后重试"

### 3.10 I-13: Logs.vue 改用分页加载
- **文件**: `admin/src/views/Logs.vue`
- **变更**: limit 200 → 50，引入 `van-list` + `page`/`finished`/`loadMore` 分页逻辑

### 3.11 S-9: formatWeekday 移入 utils/format.ts
- **从**: `admin/src/views/History.vue:20-24`
- **到**: `admin/src/utils/format.ts`，export 后 History.vue import 使用

### 验证
```bash
cd admin && bunx vue-tsc --noEmit && bunx biome check .
# 手动验证：
# 1. Digest 发布：取消 → 无 toast；API 失败 → 拦截器 toast
# 2. History：网络断开 → 恢复后可继续加载
# 3. HistoryDetail：/history/abc → "无效的记录 ID"
# 4. ApiCosts：一个接口失败另一个仍显示
# 5. Logs：滚动触发分页
```

---

## 第 4 轮 — 重构与代码质量提升

> 目标：提取通用 composable、消除重复代码。纯重构，不改变行为。
>
> 包含问题：S-1, S-2, S-3, S-4, S-5, S-6, S-8, S-10（共 8 项）
>
> 依赖：前三轮全部完成

### 4.1 S-1: 提取 `useAsyncData<T>()` composable
- **新建**: `admin/src/composables/useAsyncData.ts`
- **应用**: Dashboard.vue、Digest.vue、Settings.vue、ApiCosts.vue、Logs.vue、Preview.vue 中重复的 loading/data/error 样板代码

### 4.2 S-10: 提取 `AsyncContent` 组件
- **新建**: `admin/src/components/AsyncContent.vue`（loading/error/content 三态模板）
- **应用**: HistoryDetail.vue、Preview.vue

### 4.3 S-2: visibleItems 共享工具函数
- **新建**: `admin/src/utils/digest.ts` → `filterVisibleItems(items)`
- **应用**: Digest.vue + ArticlePreview.vue 的 computed 改为调用此函数

### 4.4 S-3: ArticlePreview.vue 预计算解析结果
- **文件**: `admin/src/components/ArticlePreview.vue`
- **变更**: 模板中 `parsePerspectives`/`parseSourceTweets` 被调用两次 → 提取为 computed map，模板引用预计算结果

### 4.5 S-4: Settings.vue API 状态用 v-for
- **文件**: `admin/src/views/Settings.vue:228-280`
- **变更**: 四个 API 状态 van-cell → computed 配置数组 + `v-for`

### 4.6 S-5: ApiCosts.vue Tab 配置数组驱动
- **文件**: `admin/src/views/ApiCosts.vue:55-93`
- **变更**: 今日/本月 Tab → computed 配置数组 + `v-for`

### 4.7 S-6: 内联 style 迁移到 scoped CSS
- **文件**: Dashboard.vue（~10 处）、Digest.vue（~6 处）
- **变更**: 提取为 scoped CSS class（`.section-gap`、`.meta-text` 等），新增 `<style scoped>` 块

### 4.8 S-8: 字符串路径导航改为命名路由
- **涉及**: Dashboard.vue、Digest.vue、HistoryDetail.vue、Preview.vue 等约 10 处
- **变更**: `router.push('/dashboard')` → `router.push({ name: 'dashboard' })`，动态路径用 `params`

### 验证
```bash
cd admin && bunx vue-tsc --noEmit && bunx biome check .
# 逐页面功能回归测试，确认重构未引入行为变更
```

---

## 第 5 轮 — 收尾

> 目标：stub 页面标注 + 最终全量验证。
>
> 包含问题：S-12（共 1 项）

### 5.1 S-12: stub 页面添加 TODO
- **文件**: Login.vue, Setup.vue, Accounts.vue, DigestEdit.vue
- **变更**: `<script setup>` 中添加 `// TODO: 待实现 — 参见 docs/spec/user-stories.md`

### 最终全量验证
```bash
# 后端
ruff check . && ruff format --check . && pyright && pytest

# 生成物一致性
make gen && git diff --exit-code

# 前端
cd admin && bunx vue-tsc --noEmit && bunx biome check .
```

---

## 轮次依赖关系

```
第 1 轮 (API 层 + 路由)         ← 无前置依赖
    ↓
第 2 轮 (后端枚举 + 重新生成)    ← 无前置依赖（建议顺序执行）
    ↓
第 3 轮 (视图层缺陷修复)         ← 依赖第 1 轮 + 第 2 轮
    ↓
第 4 轮 (重构 + 代码质量)        ← 依赖前三轮
    ↓
第 5 轮 (收尾)                  ← 依赖第 4 轮
```

## 问题到轮次映射

| 问题 | 轮次 | 严重性 | 主要文件 |
|------|------|--------|----------|
| C-1 | 1 | Critical | api/index.ts |
| C-2 | 3 | Critical | views/Digest.vue |
| C-3 | 3 | Critical | views/History.vue |
| C-4 | 1 | Critical | api/index.ts |
| C-5 | 3 | Critical | components/ArticlePreview.vue |
| C-6 | 1 | Critical | router/index.ts |
| I-1 | 1 | Important | router/index.ts |
| I-2 | 3 | Important | utils/format.ts |
| I-3 | 3 | Important | views/History.vue |
| I-4 | 3 | Important | views/Dashboard.vue |
| I-5 | 1 | Important | api/index.ts |
| I-6 | 2 | Important | 后端 settings_types.py |
| I-7 | 2 | Important | 后端 4 个 Schema 文件 |
| I-8 | 3 | Important | views/HistoryDetail.vue |
| I-9 | 3 | Important | views/ApiCosts.vue |
| I-10 | 3 | Important | views/HistoryDetail.vue |
| I-11 | 1 | Important | main.ts |
| I-12 | 1 | Important | api/index.ts |
| I-13 | 3 | Important | views/Logs.vue |
| I-14 | 1 | Important | api/index.ts |
| S-1 | 4 | Suggestion | 新建 composables/useAsyncData.ts |
| S-2 | 4 | Suggestion | 新建 utils/digest.ts |
| S-3 | 4 | Suggestion | components/ArticlePreview.vue |
| S-4 | 4 | Suggestion | views/Settings.vue |
| S-5 | 4 | Suggestion | views/ApiCosts.vue |
| S-6 | 4 | Suggestion | views/Dashboard.vue, Digest.vue |
| S-7 | 1 | Suggestion | 新建 constants/index.ts |
| S-8 | 4 | Suggestion | 多个视图 |
| S-9 | 3 | Suggestion | utils/format.ts |
| S-10 | 4 | Suggestion | 新建 components/AsyncContent.vue |
| S-11 | 1 | Suggestion | api/index.ts |
| S-12 | 5 | Suggestion | 4 个 stub 页面 |

## 新建文件清单

| 文件 | 轮次 | 用途 |
|------|------|------|
| `admin/src/constants/index.ts` | 1 | AUTH_TOKEN_KEY 常量 |
| `admin/src/composables/useAsyncData.ts` | 4 | 通用异步数据加载 composable |
| `admin/src/components/AsyncContent.vue` | 4 | loading/error/content 三态包装组件 |
| `admin/src/utils/digest.ts` | 4 | filterVisibleItems 共享工具函数 |

---

## 执行结果（待回填）

> 以下内容在实施完成后回填

### 交付物清单
_待回填_

### 偏离项表格
_待回填_

### 问题与修复
_待回填_

### 质量门禁详表
_待回填_

### PR 链接
_待回填_
