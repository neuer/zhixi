# US-009 预览签名链接 — 实施计划

## Context

管理员需要将日报预览分享给未登录用户（如合作方、审核人员）。当前预览功能（US-038）要求 JWT 登录态，无法分享。US-009 通过签名 token 实现匿名预览链接，有效期 24h，自动失效。

**关键利好**：DB 字段 `preview_token` 和 `preview_expires_at` 已在初始迁移中预留，无需 Alembic 迁移。

---

## 文件变更清单

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/schemas/digest_types.py` | 修改 | 新增 `PreviewLinkResponse` |
| `app/services/digest_service.py` | 修改 | 新增 `generate_preview_link()`、`get_preview_by_token()`、`PreviewTokenInvalidError`、`_ensure_utc()` |
| `app/api/digest.py` | 修改 | 新增 `POST /preview-link`（需认证）和 `GET /preview/{token}`（匿名） |
| `admin/src/views/Preview.vue` | 修改 | 支持 `?token=xxx` 查询参数分支 |
| `tests/test_preview_link_api.py` | 新增 | 11 个测试用例 |

**无需修改**：models（字段已存在）、Alembic（无迁移）、router/index.ts（`/preview` 已在白名单）、api/index.ts、ArticlePreview.vue。

---

## 后端实现

### 1. Schema（`app/schemas/digest_types.py`）

```python
class PreviewLinkResponse(BaseModel):
    """预览签名链接响应。"""
    token: str
    expires_at: datetime
```

### 2. Service（`app/services/digest_service.py`）

**新增 `_ensure_utc()` 辅助函数**（模块级，与 process_service 中的同名函数一致，因模块隔离不跨 import）：

```python
def _ensure_utc(dt: datetime) -> datetime:
    """确保 datetime 有 UTC 时区信息（SQLite 读回可能丢失 tzinfo）。"""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt
```

**新增 `PreviewTokenInvalidError` 异常类**（与现有 DigestNotFoundError 同区域）。

**`generate_preview_link(digest_date)`**：
1. `_get_current_digest_or_none(digest_date)` → 不存在抛 `DigestNotFoundError`
2. `secrets.token_urlsafe(32)` 生成 token
3. `expires_at = datetime.now(UTC) + timedelta(hours=24)`
4. 写入 `digest.preview_token` 和 `digest.preview_expires_at`
5. `flush()` → 返回 `(token, expires_at)`
6. 不检查 status — 已发布 digest 也可生成预览链接

**`get_preview_by_token(token)`**：
1. `SELECT ... WHERE preview_token = :token` 查询 DailyDigest
2. 不存在 → 抛 `PreviewTokenInvalidError`
3. `is_current == False` → 抛 `PreviewTokenInvalidError`
4. `_ensure_utc(preview_expires_at) < datetime.now(UTC)` → 抛 `PreviewTokenInvalidError`
5. 查询该 digest 的 DigestItem 列表（按 display_order 排序）
6. 返回 `(digest, items)`

### 3. 路由（`app/api/digest.py`）

**`POST /preview-link`**（需认证）— 放在现有 `GET /preview` 之后：
- `Depends(get_current_admin)` + `Depends(get_digest_service)`
- 调用 `svc.generate_preview_link()`
- `DigestNotFoundError` → 404
- 返回 `PreviewLinkResponse(token=token, expires_at=expires_at)`

**`GET /preview/{token}`**（匿名）— 放在 `POST /preview-link` 之后：
- 仅 `Depends(get_db)`，无认证依赖
- 手动构造 `DigestService(db, claude_client=get_claude_client())`（与 regenerate 路由模式一致）
- `PreviewTokenInvalidError` → 403 `{"detail": "链接已失效或过期"}`
- 返回 `PreviewResponse`（复用 US-038 响应模型）

**路由顺序**：`GET /preview` → `POST /preview-link` → `GET /preview/{token}`，FastAPI 按注册顺序优先匹配固定路径，不会冲突。

---

## 前端实现

### Preview.vue 改造

```typescript
import { useRoute, useRouter } from "vue-router";

const route = useRoute();
const isTokenMode = computed(() => !!route.query.token);

async function loadPreview() {
  const shareToken = route.query.token as string | undefined;

  if (shareToken) {
    // 签名链接模式：匿名访问
    try {
      const resp = await api.get<PreviewResponse>(`/digest/preview/${shareToken}`);
      data.value = resp.data;
    } catch (e) {
      const axiosErr = e as AxiosError;
      error.value = axiosErr.response?.status === 403
        ? "链接已失效或过期"
        : "暂无可预览的内容";
    } finally {
      loading.value = false;
    }
    return;
  }

  // 登录态模式（原逻辑不变）
  // ...
}
```

- Token 模式隐藏"返回"按钮和"返回首页"按钮（匿名用户无法访问 dashboard）
- 错误态按钮也隐藏（token 模式下无处可返回）

---

## 测试用例（`tests/test_preview_link_api.py`）

复制 `_seed_digest_with_items()` helper（保持测试独立性）。

| # | 测试名 | 验证点 |
|---|--------|--------|
| 1 | `test_create_preview_link_success` | 返回 token + expires_at，DB 字段已写入 |
| 2 | `test_create_preview_link_no_digest_404` | 无 current digest → 404 |
| 3 | `test_create_preview_link_requires_auth` | 无 JWT → 401 |
| 4 | `test_create_preview_link_overwrites_old` | 新 token 覆盖旧 token |
| 5 | `test_preview_by_token_success` | 有效 token 返回完整预览数据 |
| 6 | `test_preview_by_token_invalid_403` | 不存在的 token → 403 |
| 7 | `test_preview_by_token_expired_403` | 过期 token → 403 |
| 8 | `test_preview_by_token_not_current_403` | is_current=False → 403 |
| 9 | `test_preview_by_token_no_auth_required` | 不带 JWT 也能访问 |
| 10 | `test_preview_by_token_includes_excluded` | 返回全部条目含 excluded |
| 11 | `test_regenerate_invalidates_old_token` | regenerate 后旧版本 is_current=False，旧 token 403 |

Mock 时间：过期测试直接设 `preview_expires_at` 为过去时间，无需 freezegun。`get_today_digest_date` 用 `@patch` mock。

---

## TDD 实施顺序

1. 写测试（红灯）
2. `app/schemas/digest_types.py` — 新增 `PreviewLinkResponse`
3. `app/services/digest_service.py` — `_ensure_utc`、`PreviewTokenInvalidError`、两个新方法
4. `app/api/digest.py` — 两个新路由
5. 后端测试通过（绿灯）
6. `admin/src/views/Preview.vue` — 前端改造
7. 质量门禁全通过

---

## 验证方式

```bash
uv run pytest tests/test_preview_link_api.py -v     # 新增测试
uv run pytest                                         # 全量回归
uv run ruff check . && uv run ruff format --check .   # lint
uv run pyright                                        # 类型检查
cd admin && bunx biome check . && bunx vue-tsc --noEmit  # 前端检查
```
