# 前端深度审查修复实施计划

> **执行指引：** 使用 deep-review skill 按轮次逐步执行。步骤使用 checkbox (`- [ ]`) 语法追踪进度。

**目标：** 修复 `admin/src/` 中 D1-D6 + D9 维度发现的 3 个 Critical + 16 个 Important + 12 个 Suggestion 问题

**审查模式：** 全量

**技术栈：** Vue 3 (Composition API) + TypeScript 严格模式 + Vant 4 + Vite + axios

**分支命名：** `chore/frontend-deep-review-fixes`

**分批策略：** 分 2 批（第 1 批 Critical + Important 共 19 项；第 2 批 Suggestion 共 12 项）

---

## 文件结构地图

| 操作 | 文件路径 | 职责 | 涉及问题 |
|------|---------|------|---------|
| 修改 | `admin/src/composables/useAsyncData.ts` | 异步数据加载 composable | C-2, I-4 |
| 修改 | `admin/src/components/ArticlePreview.vue` | 文章预览展示组件 | C-1, I-10 |
| 修改 | `admin/src/views/Logs.vue` | 日志查看页 | C-3, I-2 |
| 修改 | `admin/src/api/index.ts` | HTTP 客户端 + 拦截器 | I-1, I-6 |
| 修改 | `admin/src/main.ts` | 应用入口 | I-11 |
| 修改 | `admin/src/utils/status.ts` | 状态映射工具 | I-5 |
| 修改 | `admin/src/views/Dashboard.vue` | 仪表盘页 | I-3 |
| 修改 | `admin/src/views/Digest.vue` | 今日草稿页 | I-3, I-6, I-7 |
| 修改 | `admin/src/views/History.vue` | 历史列表页 | I-3, I-14 |
| 修改 | `admin/src/views/Preview.vue` | 预览页 | I-13 |
| 修改 | `admin/src/views/Settings.vue` | 设置页 | I-9, I-12, I-15 |
| 修改 | `admin/src/views/ApiCosts.vue` | API 成本页 | I-8 |
| 修改 | `admin/src/router/index.ts` | 路由守卫 | I-16 |

---

## 问题总表

| 编号 | 维度 | 置信度 | 文件 | 摘要 |
|------|------|--------|------|------|
| C-1 | D5 注释 | 95 | ArticlePreview.vue:30-49 | parseSourceTweets 字段名与后端不匹配，来源推文永远不展示 |
| C-2 | D1+D2 | 95 | useAsyncData.ts:23 | error ref 永不赋值，错误状态无法传递给 UI |
| C-3 | D1+D9 | 88 | Logs.vue:9,100-106 | pull-refresh 与 list 共用 loading ref + loadLogs 守卫失效 |
| I-1 | D3 | 95 | api/index.ts:5-13 | 手写 ValidationErrorItem 重复 OpenAPI 生成类型 |
| I-2 | D2 | 92 | Logs.vue:68-70 | 加载失败时 finished=true 永久阻断滚动加载 |
| I-3 | D2+D9 | 90 | Dashboard/Digest/History | 多组件缺少 error 状态，加载失败显示误导信息 |
| I-4 | D1 | 90 | useAsyncData.ts | 死代码未被使用 + 多组件手写重复加载模式 |
| I-5 | D3 | 90 | status.ts:11,27 | statusMap 键未用后端枚举收窄 |
| I-6 | D6 | 88 | api/index.ts:48 + Digest.vue:135 | 嵌套三元运算符（2 处） |
| I-7 | D2 | 88 | Digest.vue:31-67 | publish/regenerate 无操作中状态保护，失败后不刷新 |
| I-8 | D2+D9 | 85 | ApiCosts.vue:17-34 | 串行请求 + 部分失败误导 |
| I-9 | D2 | 85 | Settings.vue:105-107 | 保存失败后表单未恢复 |
| I-10 | D6+D9 | 85 | ArticlePreview.vue:91-109 | parse 函数模板中每次渲染重复调用 JSON.parse |
| I-11 | D2 | 82 | main.ts:10-12 | 全局 errorHandler 只 console.error 不通知用户 |
| I-12 | D3+D9 | 82 | Settings.vue:238-255 | apiEntries 子字段可能 undefined + apiStatusText 类型过宽 |
| I-13 | D6+D2 | 82 | Preview.vue | 两个加载分支高度重复 + error 赋值逻辑冗余 |
| I-14 | D1 | 80 | History.vue:51-57 | refreshing 在 await loadMore() 之前设为 false |
| I-15 | D2 | 80 | Settings.vue:118-123 | finally 中 closeToast() 关闭拦截器错误 toast |
| I-16 | D2 | 78 | router/index.ts:101-103 | beforeEach 所有错误都重定向 login |
| S-1 | D6 | 78 | Digest.vue:31-67 | handlePublish/handleRegenerate 结构雷同可抽取 |
| S-2 | D3 | 78 | Logs.vue + router/index.ts | selectedLevel 未收窄 + setupCache 匿名类型 |
| S-3 | D6 | 76 | Settings.vue + Logs.vue | 对称映射函数可合并为映射表 |
| S-4 | D3 | 75 | Settings.vue:19-28 | form 类型未与 SettingsUpdate 建立编译期关联 |
| S-5 | D3 | 75 | Settings.vue:126 | onTimeConfirm 无数组长度检查 |
| S-6 | D2 | 75 | ArticlePreview.vue:24-47 | JSON 解析失败静默忽略无 console.warn |
| S-7 | D6 | 75 | Dashboard.vue:26-36 | 三个单行导航函数可内联 |
| S-8 | D5 | 75 | status.ts:1 | 注释枚举具体使用页面，容易过时 |
| S-9 | D9 | 72 | Settings.vue | 业务逻辑堆砌未抽取 composable |
| S-10 | D6 | 72 | History.vue:20 | isLoadingMore 与 loading 职责重叠 |
| S-11 | D6 | 72 | Dashboard/Digest | 重复 CSS 类定义 |
| S-12 | D5 | 70 | Login/Setup/Accounts/DigestEdit | TODO 引用已完成 US 产生歧义 |

---

# 第 1 批：Critical + Important（19 项）

## 第 1 轮 — 基础设施与共享模块

> 目标：修复 composable、API 客户端、全局错误处理、状态工具等基础设施，为后续组件修复打基础
> 包含问题：C-2, I-1, I-4, I-5, I-6(api), I-11

### 1.1 C-2 + I-4: useAsyncData error ref 修复

**文件：**
- 修改: `admin/src/composables/useAsyncData.ts`

- [ ] **Step 1: 修复 error ref 赋值**

```typescript
// admin/src/composables/useAsyncData.ts — execute 函数
async function execute() {
  loading.value = true;
  error.value = null;
  try {
    data.value = await fetcher();
  } catch (e: unknown) {
    // 拦截器已处理 toast，此处记录错误状态供组件判断
    error.value = e instanceof Error ? e.message : "请求失败";
  } finally {
    loading.value = false;
  }
}
```

注意：I-4 指出 useAsyncData 是死代码。修复 error 后保留该 composable——第 2 批 S-9 中可考虑让更多组件使用它。

### 1.2 I-1: 删除手写 ValidationErrorItem

**文件：**
- 修改: `admin/src/api/index.ts`

- [ ] **Step 2: 用 OpenAPI 生成类型替换手写类型**

删除 `ValidationErrorItem` 接口定义，从 `@zhixi/openapi-client` 导入 `ValidationError`。更新 `ApiError` 接口中对该类型的引用。拦截器中 `rawDetail` 类型标注相应更新。

### 1.3 I-6(api): api/index.ts 嵌套三元

**文件：**
- 修改: `admin/src/api/index.ts`

- [ ] **Step 3: 提取 extractDetail 函数替代嵌套三元**

```typescript
function extractDetail(rawDetail: string | ValidationError[] | undefined): string {
  if (typeof rawDetail === "string") return rawDetail;
  if (Array.isArray(rawDetail)) return rawDetail.map((e) => e.msg).join("; ");
  return "未知错误";
}
```

### 1.4 I-11: 全局 errorHandler 增加用户提示

**文件：**
- 修改: `admin/src/main.ts`

- [ ] **Step 4: errorHandler 中增加 showToast**

```typescript
import { showToast } from "vant";

app.config.errorHandler = (err, _instance, info) => {
  console.error(`[全局错误] ${info}:`, err);
  showToast({ type: "fail", message: "页面出现异常，请刷新重试", duration: 5000 });
};
```

### 1.5 I-5: status.ts statusMap 键收窄

**文件：**
- 修改: `admin/src/utils/status.ts`

- [ ] **Step 5: 用后端枚举类型收窄 statusMap 键**

检查 `@zhixi/openapi-client` 中是否有 `DigestStatus`/`JobStatus` 枚举类型。若有则导入使用；若无则在本地定义联合类型。移除无后端对应的 `success` 键（或合并到 `completed`）。`getStatus` 参数保持 `string | null | undefined`（兼容外部输入），内部用 `in` 操作符收窄。

### 第 1 轮验证

- [ ] **运行本轮门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```
预期：全部通过

- [ ] **提交本轮修复**

```bash
git add admin/src/composables/useAsyncData.ts admin/src/api/index.ts admin/src/main.ts admin/src/utils/status.ts
git commit -m "fix(admin): 修复基础设施层问题 (C-2, I-1, I-4, I-5, I-6, I-11)"
```

---

## 第 2 轮 — ArticlePreview + Logs 组件修复

> 目标：修复两个有 Critical 问题的组件
> 包含问题：C-1, C-3, I-2, I-10

### 2.1 C-1: ArticlePreview parseSourceTweets 字段名修复

**文件：**
- 修改: `admin/src/components/ArticlePreview.vue`

- [ ] **Step 1: 确认后端实际字段名**

读取 `app/digest/digest_service.py` 中写入 `snapshot_source_tweets` 的代码，确认字段名是 `handle`/`tweet_url` 还是 `author`/`url`。

- [ ] **Step 2: 修复类型守卫和字段引用**

将 `parseSourceTweets` 的返回类型和类型守卫改为匹配后端实际字段。同步修改模板中 `src.author` → `src.handle`，`src.url` → `src.tweet_url`（或其他后端实际字段名）。

### 2.2 I-10: ArticlePreview parse 函数模板重复调用

**文件：**
- 修改: `admin/src/components/ArticlePreview.vue`

- [ ] **Step 3: 将解析结果缓存到 computed**

```typescript
interface ParsedItem {
  item: DigestItemResponse;
  perspectives: string[];
  sourceTweets: { handle: string; tweet_url: string }[];
}

const parsedItems = computed<ParsedItem[]>(() =>
  visibleItems.value.map((item) => ({
    item,
    perspectives: parsePerspectives(item.snapshot_perspectives),
    sourceTweets: parseSourceTweets(item.snapshot_source_tweets),
  })),
);
```

模板中用 `parsedItems` 迭代，直接引用预解析的字段。

### 2.3 C-3: Logs.vue 分离 loading ref

**文件：**
- 修改: `admin/src/views/Logs.vue`

- [ ] **Step 4: 新增 refreshing ref，分离 pull-refresh 和 list 的加载状态**

```typescript
const refreshing = ref(false);
```

模板中 `van-pull-refresh v-model="refreshing"`。`resetAndLoad` 中设 `refreshing.value = false`。

- [ ] **Step 5: 修复 loadLogs 守卫逻辑**

使用独立的 `isLoadingMore` 变量做并发保护，不依赖被 van-list 外部修改的 `loading` ref。

### 2.4 I-2: Logs.vue 加载失败不设 finished

**文件：**
- 修改: `admin/src/views/Logs.vue`

- [ ] **Step 6: catch 块中移除 `finished.value = true`**

```typescript
} catch {
  // 拦截器已处理 toast；不设 finished，允许用户滚动重试
} finally {
  loading.value = false;
}
```

### 第 2 轮验证

- [ ] **运行门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交**

```bash
git add admin/src/components/ArticlePreview.vue admin/src/views/Logs.vue
git commit -m "fix(admin): 修复 ArticlePreview 字段名 + Logs 加载状态 (C-1, C-3, I-2, I-10)"
```

---

## 第 3 轮 — 页面错误状态补全

> 目标：为缺少 error 状态的页面补全错误态 UI，修复 History/Preview/Router 相关问题
> 包含问题：I-3, I-13, I-14, I-16

### 3.1 I-3: Dashboard.vue 增加 error 状态

**文件：**
- 修改: `admin/src/views/Dashboard.vue`

- [ ] **Step 1: 增加 error ref，catch 中赋值，模板中区分错误态**

```typescript
const error = ref<string | null>(null);

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<DashboardOverviewResponse>("/dashboard/overview");
    data.value = resp.data;
  } catch {
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
  }
}
```

模板顶部加 `<van-empty v-if="!loading && error" :description="error" image="error" />`。

### 3.2 I-3: Digest.vue 增加 error 状态

**文件：**
- 修改: `admin/src/views/Digest.vue`

- [ ] **Step 2: 同 Dashboard，增加 error ref + 模板区分"加载失败"和"尚未生成"**

```html
<van-empty v-if="!loading && error" :description="error" image="error" />
<van-empty v-else-if="!loading && !data?.digest" description="今日草稿尚未生成" />
```

### 3.3 I-3: History.vue 增加 error 状态

**文件：**
- 修改: `admin/src/views/History.vue`

- [ ] **Step 3: catch 中设置 error，模板区分"暂无记录"和"加载失败"**

### 3.4 I-14: History.vue refreshing 时序修复

- [ ] **Step 4: 将 `refreshing.value = false` 移到 `await loadMore()` 之后**

```typescript
async function onRefresh() {
  page.value = 1;
  finished.value = false;
  items.value = [];
  await loadMore();
  refreshing.value = false;
}
```

### 3.5 I-13: Preview.vue 重构两个分支

**文件：**
- 修改: `admin/src/views/Preview.vue`

- [ ] **Step 5: 合并两个加载分支为统一逻辑**

```typescript
async function loadPreview() {
  const rawToken = route.query.token;
  const shareToken = Array.isArray(rawToken) ? rawToken[0] : rawToken;
  const url = shareToken ? `/digest/preview/${shareToken}` : "/digest/preview";

  loading.value = true;
  error.value = null;
  try {
    const resp = await api.get<PreviewResponse>(url);
    data.value = resp.data;
  } catch (e) {
    if (shareToken && axios.isAxiosError(e) && e.response?.status === 403) {
      error.value = "链接已失效或过期";
    } else {
      error.value = "暂无可预览的内容";
    }
  } finally {
    loading.value = false;
  }
}
```

### 3.6 I-16: Router beforeEach 仅 401 重定向

**文件：**
- 修改: `admin/src/router/index.ts`

- [ ] **Step 6: catch 块中区分 401 和其他错误**

```typescript
} catch (e: unknown) {
  if (axios.isAxiosError(e) && e.response?.status === 401) {
    return "/login";
  }
  // 非认证错误：放行导航，让页面自身处理
  return true;
}
```

### 第 3 轮验证

- [ ] **运行门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交**

```bash
git add admin/src/views/Dashboard.vue admin/src/views/Digest.vue admin/src/views/History.vue admin/src/views/Preview.vue admin/src/router/index.ts
git commit -m "fix(admin): 补全页面错误状态 + 修复路由守卫 (I-3, I-13, I-14, I-16)"
```

---

## 第 4 轮 — Digest/Settings/ApiCosts 行为修复

> 目标：修复操作类功能的错误处理和 UX 问题
> 包含问题：I-6(Digest), I-7, I-8, I-9, I-12, I-15

### 4.1 I-6(Digest): Digest.vue 嵌套三元

**文件：**
- 修改: `admin/src/views/Digest.vue`

- [ ] **Step 1: 提取 getItemLabel 函数**

```typescript
function getItemLabel(item: DigestItemResponse): string {
  if (item.snapshot_author_handle) return `@${item.snapshot_author_handle}`;
  if (item.snapshot_topic_type === "aggregated") return "聚合话题";
  return "";
}
```

模板中 `:label="getItemLabel(item)"`。

### 4.2 I-7: Digest.vue publish/regenerate 增加操作保护

- [ ] **Step 2: 增加 publishing/regenerating ref，失败后刷新数据**

```typescript
const publishing = ref(false);
const regenerating = ref(false);

async function handlePublish() {
  if (!data.value?.digest || publishing.value) return;
  // ... dialog ...
  publishing.value = true;
  try {
    await api.post("/digest/mark-published");
    showToast("发布成功");
  } catch {
    // 拦截器已 toast
  } finally {
    publishing.value = false;
    await loadData();
  }
}
```

模板中按钮加 `:loading="publishing"` 和 `:disabled="publishing"`。handleRegenerate 同理。

### 4.3 I-8: ApiCosts.vue Promise.all 并行

**文件：**
- 修改: `admin/src/views/ApiCosts.vue`

- [ ] **Step 3: 两个请求改为 Promise.all + 增加 error ref**

```typescript
const error = ref<string | null>(null);

async function loadData() {
  loading.value = true;
  error.value = null;
  try {
    const [costsResp, dailyResp] = await Promise.all([
      api.get<ApiCostsResponse>("/dashboard/api-costs"),
      api.get<DailyCostsResponse>("/dashboard/api-costs/daily"),
    ]);
    costsData.value = costsResp.data;
    dailyData.value = dailyResp.data;
  } catch {
    error.value = "加载失败，下拉刷新重试";
  } finally {
    loading.value = false;
  }
}
```

### 4.4 I-9: Settings.vue 保存失败后恢复表单

**文件：**
- 修改: `admin/src/views/Settings.vue`

- [ ] **Step 4: catch 中重新加载服务端数据**

```typescript
} catch {
  // 拦截器已 toast；重载服务端数据恢复表单
  await loadSettings();
} finally {
  saving.value = false;
}
```

### 4.5 I-15: Settings.vue closeToast 时序修复

- [ ] **Step 5: 将 closeToast 移到 try 块成功分支中**

```typescript
async function checkApiStatus() {
  checkingApi.value = true;
  showLoadingToast({ message: "检测中...", duration: 0 });
  try {
    const resp = await api.get<ApiStatusResponse>("/settings/api-status");
    apiStatus.value = resp.data;
    closeToast();
  } catch {
    closeToast();
    // 拦截器会弹新的错误 toast
  } finally {
    checkingApi.value = false;
  }
}
```

### 4.6 I-12: Settings.vue apiEntries 过滤 + apiStatusText 类型

- [ ] **Step 6: apiEntries computed 增加 null 过滤**

```typescript
const apiEntries = computed(() => {
  if (!apiStatus.value) return [];
  return [
    { label: "X API", data: apiStatus.value.x_api },
    { label: "Claude API", data: apiStatus.value.claude_api },
    { label: "Gemini API", data: apiStatus.value.gemini_api },
    { label: "微信 API", data: apiStatus.value.wechat_api },
  ].filter((e) => e.data != null);
});
```

apiStatusText/Color 参数收窄为 `"ok" | "error" | "not_configured"`（或保持 string + 注释说明，视 OpenAPI 类型而定）。

### 第 4 轮验证

- [ ] **运行门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交**

```bash
git add admin/src/views/Digest.vue admin/src/views/ApiCosts.vue admin/src/views/Settings.vue
git commit -m "fix(admin): 修复操作行为与错误处理 (I-6, I-7, I-8, I-9, I-12, I-15)"
```

---

# 第 2 批：Suggestion（12 项）

## 第 5 轮 — 代码简化与类型改善

> 包含问题：S-1 到 S-12

### 5.1 S-1: Digest.vue 抽取 confirmAndExecute

- [ ] **Step 1: 抽取通用确认执行函数**

### 5.2 S-2: Logs.vue selectedLevel 收窄 + router setupCache 命名

- [ ] **Step 2: selectedLevel 改为 `ref<LogLevel>("INFO")`，setupCache.value 改名 needSetup**

### 5.3 S-3: Settings/Logs 映射函数合并

- [ ] **Step 3: apiStatusText/Color 合并为映射表，levelColor/levelBg 合并为映射表**

### 5.4 S-4: Settings.vue form 类型关联

- [ ] **Step 4: 定义 SettingsForm 接口，编译期断言键集合**

### 5.5 S-5: Settings.vue onTimeConfirm 边界检查

- [ ] **Step 5: 增加 `if (selectedValues.length < 2) return;`**

### 5.6 S-6: ArticlePreview JSON 解析增加 console.warn

- [ ] **Step 6: catch 中加 `console.warn("[ArticlePreview] JSON 解析失败:", raw, e);`**

### 5.7 S-7: Dashboard.vue 导航函数内联

- [ ] **Step 7: 删除 goDigest/goSettings/goAccounts，模板内联 router.push**

### 5.8 S-8: status.ts 注释泛化

- [ ] **Step 8: 将"统一 Dashboard/Digest/History 的状态展示"改为"状态映射工具"**

### 5.9 S-9: Settings.vue 不做 composable 抽取

此项为优化建议，当前 290 行未到阈值，不在本次处理。标记为"用户决定不修"。

### 5.10 S-10: History.vue isLoadingMore 保留

Vant van-list 的 v-model:loading 行为在边界场景下不够可靠，保留独立锁更安全。标记为"用户决定不修"。

### 5.11 S-11: 重复 CSS 不做全局提取

scoped style 隔离是 Vue 推荐做法，少量重复可接受。标记为"用户决定不修"。

### 5.12 S-12: TODO 注释更新

- [ ] **Step 9: Login/Setup/Accounts/DigestEdit 的 TODO 更新为"前端页面待实现（后端 API 已就绪）"**

### 第 5 轮验证

- [ ] **运行门禁**

```bash
cd admin && bunx biome check . && bunx vue-tsc --noEmit && bun run build
```

- [ ] **提交**

```bash
git add -u admin/src/
git commit -m "chore(admin): 代码简化与类型改善 (S-1~S-12)"
```

---

## 执行结果

> 以下在实施完成后一次性回填。

### 交付物清单

修改 17 个文件（+237/-196 行）：

| 文件 | 修改内容 |
|------|---------|
| `composables/useAsyncData.ts` | catch 中赋值 error ref (C-2) |
| `api/index.ts` | 删除手写类型用 OpenAPI 替换 (I-1)，提取 extractDetail (I-6) |
| `main.ts` | 全局 errorHandler 增加 showToast (I-11) |
| `utils/status.ts` | statusMap 键收窄为枚举 (I-5)，注释泛化 (S-8) |
| `components/ArticlePreview.vue` | 字段名修复 handle/tweet_url (C-1)，computed 缓存 (I-10)，JSON 解析 warn (S-6) |
| `views/Logs.vue` | 分离 refreshing/loading (C-3)，不设 finished (I-2)，类型收窄 (S-2)，映射表合并 (S-3) |
| `views/Dashboard.vue` | 增加 error 状态 (I-3)，导航函数内联 (S-7) |
| `views/Digest.vue` | 增加 error 状态 (I-3)，getItemLabel (I-6)，操作保护 (I-7)，confirmAndExecute (S-1) |
| `views/History.vue` | 增加 error 状态 (I-3)，refreshing 时序 (I-14) |
| `views/Preview.vue` | 合并加载分支 (I-13) |
| `views/ApiCosts.vue` | Promise.all 并行 + error 状态 (I-8) |
| `views/Settings.vue` | 保存失败恢复 (I-9)，closeToast 时序 (I-15)，apiEntries 过滤 (I-12)，映射表 (S-3)，SettingsForm 类型 (S-4)，边界检查 (S-5) |
| `router/index.ts` | 仅 401 重定向 (I-16)，setupCache 命名 (S-2) |
| `views/Login.vue` | TODO 更新 (S-12) |
| `views/Setup.vue` | TODO 更新 (S-12) |
| `views/Accounts.vue` | TODO 更新 (S-12) |
| `views/DigestEdit.vue` | TODO 更新 (S-12) |

### 偏离项表格

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| S-9 | 抽取 composable | 不修 | 290 行未到阈值 |
| S-10 | 去掉 isLoadingMore | 不修 | 保留锁更安全 |
| S-11 | 提取全局 CSS | 不修 | scoped 隔离可接受 |

无计划外偏离。

### 问题与修复

执行过程中无阻塞问题。所有轮次一次通过验证。

### 质量门禁详表

| 门禁 | 结果 |
|------|------|
| `bunx biome check .` | 0 error, 38 warnings（Vue 模板变量已知误报） |
| `bunx vue-tsc --noEmit` | 通过，0 error |
| `bun run build` | 通过 |
| 两阶段复审 — 规格合规 | 31/31 项通过 |
| 两阶段复审 — 代码质量 | 通过，无置信度 ≥ 80 的问题 |

### PR 链接

https://github.com/neuer/zhixi/pull/32
