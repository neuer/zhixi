# US-016 手动补录推文 — 实施计划

## Context

P4 阶段仅剩 US-016 待开发。该功能允许管理员通过推文 URL 手动补录推文到当日草稿，是唯一同时横跨 M1(Fetcher)、M2(Processor)、M3(Digest) 三个模块的路由。所有依赖（US-011/021/024/030）已完成，`ProcessService.process_single_tweet_by_id()` 已预留。

## 需要新增/修改的文件

| 文件 | 操作 | 说明 |
|------|------|------|
| `app/fetcher/base.py` | 修改 | 新增 `fetch_single_tweet` 抽象方法 |
| `app/fetcher/x_api.py` | 修改 | 实现 `fetch_single_tweet(tweet_id)` |
| `app/services/fetch_service.py` | 修改 | 新增 `fetch_single_tweet(tweet_url, digest_date)` + `_parse_tweet_id` + `_find_or_create_account` + `TweetAlreadyExistsError` |
| `app/services/digest_service.py` | 修改 | 新增 `add_manual_tweet_item(tweet, digest_date)` + `_calculate_manual_heat` + `_get_existing_base_scores` |
| `app/schemas/digest_types.py` | 修改 | 新增 `AddTweetRequest` + `AddTweetResponse` |
| `app/api/digest.py` | 修改 | 新增 `POST /add-tweet` 路由 |
| `tests/test_add_tweet_api.py` | 新增 | 完整测试套件（16 个场景） |

**无需修改**: models（Tweet 已有 source 字段）、Alembic（无新字段）、process_service.py（`process_single_tweet_by_id` 已存在于 L112）、heat_calculator.py（纯函数直接调用）。

## 数据流

```
POST /api/digest/add-tweet {"tweet_url": "https://x.com/user/status/123"}
  │
  ├─ [前置] DigestService._get_current_draft(digest_date)
  │   └─ 无 draft → 409 | status != draft → 409
  │
  ├─ [M1] FetchService.fetch_single_tweet(tweet_url, digest_date)
  │   ├─ _parse_tweet_id(url) → tweet_id           # 400
  │   ├─ SELECT tweet_id 去重                        # 409
  │   ├─ XApiFetcher.fetch_single_tweet(tweet_id)   # 502
  │   │   └─ GET /tweets/:id → _parse_tweet → RawTweet
  │   ├─ _find_or_create_account(author_id, url)
  │   └─ Tweet(source='manual', is_ai_relevant=True) → db.add + flush
  │
  ├─ [M2] ProcessService.process_single_tweet_by_id(tweet.id)  # 已有方法
  │   ├─ Claude API → {title, translation, comment}
  │   ├─ tweet.is_processed = True
  │   └─ 失败 → 502 JSONResponse（推文已入库，不建 item）
  │
  ├─ [M3] DigestService.add_manual_tweet_item(tweet, digest_date)
  │   ├─ _calculate_manual_heat: base_score + normalize(已有范围) + 截断[0,100]
  │   │   ai_importance_score 固定 50
  │   ├─ display_order = max(existing) + 1
  │   ├─ _create_tweet_item → DigestItem (snapshot_*)
  │   ├─ digest.item_count += 1
  │   └─ _rerender_markdown(digest)
  │
  └─ 200 {"message": "补录成功", "item": DigestItemResponse}
```

## 各文件具体改动

### 1. `app/fetcher/base.py` — 新增抽象方法

```python
@abstractmethod
async def fetch_single_tweet(self, tweet_id: str) -> RawTweet: ...
```

### 2. `app/fetcher/x_api.py` — 实现 fetch_single_tweet

使用 X API v2 `GET /tweets/:id`，复用现有 `_request_with_retry` + `_parse_tweet`。
- `tweet.fields` 需加 `author_id`（单条查询不默认返回）
- 返回 RawTweet，异常由上层处理

### 3. `app/services/fetch_service.py` — 新增方法

**`_parse_tweet_id(url) -> str | None`**: 正则提取，支持 x.com / twitter.com

**`TweetAlreadyExistsError`**: 自定义异常

**`fetch_single_tweet(tweet_url, digest_date) -> Tweet`**:
1. 解析 URL → tweet_id
2. DB 去重检查（tweet_id UNIQUE）
3. X API 抓取 + ApiCostLog
4. `_find_or_create_account`（先 twitter_user_id → 再 handle → 创建临时账号 is_active=False）
5. `_raw_to_model` + `source="manual"` + db.add

### 4. `app/services/digest_service.py` — 新增方法

**`add_manual_tweet_item(tweet, digest_date) -> DigestItem`**:
1. `_get_current_draft` 校验
2. `_calculate_manual_heat` 计算热度
3. `max(display_order) + 1`
4. `_create_tweet_item` 创建快照
5. `item_count += 1` + `_rerender_markdown`

**`_calculate_manual_heat(tweet, account, digest_date)`**:
- base_score = `calculate_base_score(likes, rt, replies, weight, hours)`
- ai_importance_score = 50.0
- `_get_existing_base_scores(digest_date)` → 查询已有推文 base_heat_score
- normalize: `(base - min) / (max - min) * 100`，截断 [0, 100]
- 已有 < 2 条或 min == max → normalized = 50.0
- heat_score = `round(normalized * 0.7 + 50 * 0.3, 2)`

### 5. `app/schemas/digest_types.py` — 新增模型

```python
class AddTweetRequest(BaseModel):
    tweet_url: str = Field(min_length=1, max_length=500)

class AddTweetResponse(BaseModel):
    message: str
    item: DigestItemResponse
```

### 6. `app/api/digest.py` — 新增路由

`POST /add-tweet`，路由内手动构造 3 个 Service（共享 db session），前置检查草稿。
- AI 失败用 `JSONResponse(502)` 保证推文入库 commit
- 其他错误用 `HTTPException from None`

## 错误处理矩阵

| 场景 | 状态码 | 消息 | 实现 |
|------|--------|------|------|
| URL 无效 | 400 | "无效的推文URL" | HTTPException |
| 推文已存在 | 409 | "该推文已存在" | HTTPException |
| 无草稿 | 409 | "今日草稿尚未生成..." | HTTPException |
| 非 draft | 409 | "当前版本不可编辑" | HTTPException |
| X API 失败 | 502 | "推文抓取失败" | HTTPException |
| AI 加工失败 | 502 | "推文已入库但AI加工失败..." | **JSONResponse** |

## 热度计算核心逻辑

1. 正常计算 `base_score`（复用 heat_calculator 纯函数）
2. `ai_importance_score` 固定 50（不调全局分析）
3. 查询当日已处理推文的 `base_heat_score` 作为 min/max 参照
4. 单点映射到已有范围，超出截断 [0, 100]
5. **不重算已有推文** — 只算新推文的 heat_score

## 测试策略（16 个场景）

| 编号 | 场景 | 预期 |
|------|------|------|
| T1 | 正常补录完整链路 | 200, Tweet(source='manual'), DigestItem, display_order=max+1 |
| T2 | URL 格式无效 | 400 |
| T3 | tweet_id 已存在 | 409 |
| T4 | 当日无草稿 | 409 |
| T5 | 草稿 status=published | 409 |
| T6 | X API 失败 | 502 |
| T7 | AI 加工失败 | 502, Tweet 保留(is_processed=False), 无 DigestItem |
| T8 | normalize: 已有 1 条 → normalized=50 | heat_score=50.0 |
| T9 | normalize: base > max → 截断 100 | heat_score 正确 |
| T10 | normalize: base < min → 截断 0 | heat_score 正确 |
| T11 | 作者不在大V列表 → 创建临时账号 | is_active=False |
| T12 | twitter.com 旧域名 | 正常解析 |
| T13 | 未认证 | 401 |
| T14 | item_count 更新 | +1 |
| T15 | Markdown 重渲染 | content_markdown 含新条目 |
| T16 | URL 带查询参数 | 正常解析 tweet_id |

Mock: X API → AsyncMock patch `XApiFetcher.fetch_single_tweet`；Claude → AsyncMock；时间 → patch `get_today_digest_date`

## TDD 实施顺序

1. 写 `tests/test_add_tweet_api.py` 骨架（所有测试标记 + 预置数据 fixture）
2. `app/fetcher/base.py` + `app/fetcher/x_api.py` — fetch_single_tweet
3. `app/services/fetch_service.py` — URL 解析 + 去重 + 入库
4. `app/schemas/digest_types.py` — AddTweetRequest/Response
5. `app/api/digest.py` — POST /add-tweet 路由（先跑 M1 部分测试）
6. `app/services/digest_service.py` — add_manual_tweet_item + 热度计算
7. 完善路由中 M3 调用，跑全部测试
8. 质量门禁全部通过

## 验证

```bash
uv run pytest tests/test_add_tweet_api.py -v     # 本 US 测试
uv run pytest                                       # 全量测试
uv run ruff check .                                 # Lint
uv run ruff format --check .                        # 格式化
uv run pyright                                      # 类型检查
```

---

## 执行结果

### 交付物清单

| 文件 | 操作 | 行数 |
|------|------|------|
| `app/fetcher/base.py` | 修改 | +14 |
| `app/fetcher/x_api.py` | 修改 | +44 |
| `app/services/fetch_service.py` | 修改 | +118 |
| `app/services/digest_service.py` | 修改 | +99 |
| `app/schemas/digest_types.py` | 修改 | +14 |
| `app/api/digest.py` | 修改 | +68 |
| `tests/test_add_tweet_api.py` | 新增 | +695 |
| `docs/plans/us-016-manual-add-tweet.md` | 新增 | 计划文件 |
| `docs/spec/user-stories.md` | 修改 | 状态更新 |

### 偏离项

| 编号 | 计划 | 实际 | 原因 |
|------|------|------|------|
| 1 | 测试 16 个场景 | 实际 18 个（URL 解析 6 + API 9 + 热度 3） | URL 解析拆为独立 TestParseTweetId 类 6 个单元测试 |
| 2 | X API 抓取失败用 httpx.HTTPStatusError | 改用宽泛 except Exception | 简化错误匹配，fetcher 内部可能抛多种异常 |

### 问题与修复

| 问题 | 解决 |
|------|------|
| 测试中 tweet_id 用 `existing_1` 等非数字字符串，正则 `(\d+)` 无法匹配 | 改为纯数字 ID `100001`/`100002`/`100003` |
| 同理 `new_777` 含下划线不匹配 | 改为 `777777` |

### 质量门禁

| 门禁 | 结果 |
|------|------|
| ruff check | ✅ All checks passed |
| ruff format | ✅ 130 files already formatted |
| lint-imports | ✅ 4 contracts kept, 0 broken |
| pyright | ✅ 0 errors, 0 warnings |
| pytest | ✅ 511 passed (含 18 新增) |

### PR 链接

https://github.com/neuer/zhixi/pull/27
