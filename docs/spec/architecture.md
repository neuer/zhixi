# 系统架构

> 模块划分、依赖关系、工程基础设施、API 契约。
> 数据模型详见 `docs/spec/data-model.md`，目录结构详见 `docs/spec/directory-structure.md`。

---

## 模块划分

```
┌─────────────────────────────────────────────────────────────┐
│                     API 路由层 (app/api/)                     │
│   规则：不含业务逻辑。简单CRUD可通过crud.py操作DB             │
│         涉及业务逻辑的操作必须调用Service层                   │
├─────────────────────────────────────────────────────────────┤
│                  Service 编排层 (app/services/)               │
│   规则：编排业务流程、管理事务、更新状态                      │
│         是操作数据库的主要入口（除简单CRUD外）                 │
├─────────────────────────────────────────────────────────────┤
│  M1 Fetcher  │ M2 Processor │ M3 Digest  │ M4 Publisher     │
│  数据采集     │ AI 内容加工   │ 草稿组装    │ 内容发布         │
│  app/fetcher/ │ app/processor/│ app/digest/ │ app/publisher/  │
├─────────────────────────────────────────────────────────────┤
│       M5 共享基础设施 (app/clients/ + crud.py + auth.py)      │
│  claude_client / gemini_client / notifier / crud.py           │
├─────────────────────────────────────────────────────────────┤
│              M6 Admin 前端 (admin/src/)                        │
│              Vue 3 + TypeScript + Vant 4 + Vite               │
└─────────────────────────────────────────────────────────────┘
```

### M1: 数据采集 (Fetcher)

**位置**: `app/fetcher/` + `app/services/fetch_service.py`

**职责**: 调用 X API 抓取推文、分类推文类型、去重入库、单条抓取（手动补录）
**禁止**: 不做 AI 过滤/翻译/标题/点评，不操作 topics/daily_digest/digest_items 表

**对外接口**:
```python
class FetchService:
    def run_daily_fetch(self, digest_date: date) -> FetchResult: ...
    def fetch_single_tweet(self, tweet_url: str, digest_date: date) -> Tweet: ...

class BaseFetcher(ABC):
    @abstractmethod
    def fetch_user_tweets(self, user_id: str, since: datetime, until: datetime) -> list[RawTweet]: ...

def classify_tweet(raw_tweet: RawTweet) -> TweetType: ...
# 保留: ORIGINAL + SELF_REPLY + QUOTE | 排除: RETWEET + REPLY
```

**数据所有权**: tweets, twitter_accounts, fetch_log

### M2: AI 内容加工 (Processor)

**位置**: `app/processor/` + `app/services/process_service.py`

**职责**: 全局分析、逐条/逐话题 AI 加工（含 Thread 专用 Prompt）、热度分计算、JSON 校验
**禁止**: 不操作 daily_digest/digest_items 表

**对外接口**:
```python
class ProcessService:
    def run_daily_process(self, digest_date: date) -> ProcessResult: ...
    def process_single_tweet(self, tweet_id: int) -> None: ...

def calculate_base_score(likes, retweets, replies, author_weight, hours_since_post) -> float: ...
def normalize_scores(scores: list[float]) -> list[float]: ...
def calculate_heat_score(normalized_base, ai_importance) -> float: ...
def calculate_topic_heat(member_base_scores: list[float], ai_importance) -> float: ...
def validate_and_fix(raw_text: str, schema: dict) -> dict: ...
```

**数据所有权**: topics（创建/更新）、tweets（更新 AI 字段和热度）

### M3: 草稿组装 (Digest)

**位置**: `app/digest/` + `app/services/digest_service.py`

**职责**: 导读摘要、digest + items 创建（含快照）、Markdown 渲染、封面图、版本管理、编辑操作（只改快照）
**禁止**: 不做 AI 内容加工（但 regenerate 会调用 M2）

**对外接口**:
```python
class DigestService:
    def generate_daily_digest(self, digest_date: date) -> DailyDigest: ...
    def regenerate_digest(self, digest_date: date) -> DailyDigest: ...
    def edit_item(self, digest_date, item_type, item_ref_id, updates) -> DigestItem: ...
    def edit_summary(self, digest_date: date, summary: str) -> None: ...
    def reorder_items(self, digest_date, items: list[ReorderInput]) -> None: ...
    def exclude_item(self, digest_date, item_type, item_ref_id) -> None: ...
    def restore_item(self, digest_date, item_type, item_ref_id) -> None: ...
    def add_item_to_digest(self, digest_date, tweet_id) -> DigestItem: ...

def render_markdown(digest, items) -> str: ...
```

**数据所有权**: daily_digest, digest_items

### M4: 内容发布 (Publisher)

**位置**: `app/publisher/` + `app/services/publish_service.py`

**职责**: 手动/API发布、状态管理 | MVP: wechat_client.py 为空壳（NotImplementedError）

```python
class PublishService:
    def publish(self, digest_date: date) -> PublishResult: ...
    def mark_published(self, digest_date: date) -> None: ...
    def get_markdown(self, digest_date: date) -> str: ...
```

### M5: 共享基础设施

**位置**: `app/clients/`, `app/crud.py`, `app/auth.py`, `app/database.py`, `app/config.py`

**crud.py 边界**: 仅限无状态、无副作用、无 if/else 业务判断的简单读写。

```python
class ClaudeClient:
    def complete(self, prompt, system=None, max_tokens=4096) -> ClaudeResponse: ...
    # 自动注入安全声明，返回元数据（Service 层负责写 api_cost_log）

class Notifier:
    def send_alert(self, title, message) -> bool: ...
    # 企业微信 webhook

def create_jwt(username) -> str: ...
def verify_jwt(token) -> dict: ...
def create_preview_token(digest_id) -> str: ...
def verify_preview_token(token) -> int | None: ...
```

### M6: 管理后台前端

**技术栈**: Vue 3 + TypeScript + Vant 4 + Vite + axios | 全中文界面 | 移动端优先

**状态管理**: 不使用 Pinia/Vuex。组件级 `ref()`/`reactive()` + API 调用。JWT token 存 `localStorage('zhixi_token')`。

| 路由 | 组件 | 认证 |
|------|------|------|
| `/setup` | Setup.vue | 无 |
| `/login` | Login.vue | 无 |
| `/dashboard` | Dashboard.vue | JWT |
| `/accounts` | Accounts.vue | JWT |
| `/digest` | Digest.vue | JWT |
| `/digest/edit/:type/:id` | DigestEdit.vue | JWT |
| `/history` | History.vue | JWT |
| `/history/:id` | HistoryDetail.vue | JWT |
| `/settings` | Settings.vue | JWT |
| `/preview` | Preview.vue | preview token |

---

## 模块依赖关系

```
Service 调用链 (CLI pipeline):
    fetch_service.run_daily_fetch()        → M1 fetcher/*
        ↓
    process_service.run_daily_process()    → M2 processor/* + M5 claude_client
        ↓
    digest_service.generate_daily_digest() → M3 digest/* + M5 clients/*

Web API 调用链:
    POST /api/manual/fetch      → 检查锁 → M1 fetch_service
    POST /api/digest/regenerate → 检查锁 → M3 → M2(内部) → M3
    POST /api/digest/add-tweet  → M1 fetch_single + M2 process_single + M3 add_item
    PUT  /api/digest/item/*     → M3 digest_service.edit_item() (只改快照)
    POST /api/digest/publish    → 检查锁 → M4 publish_service

Service 操作的 DB 表:
    fetch_service   → tweets, twitter_accounts, fetch_log, api_cost_log, job_runs
    process_service → tweets, topics, api_cost_log, job_runs
    digest_service  → daily_digest, digest_items, api_cost_log, job_runs
    publish_service → daily_digest
```

---

## 工程基础设施

### 数据库会话管理

异步 SQLAlchemy + aiosqlite。详见 `app/database.py`。

```python
# app/database.py
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy import event
from collections.abc import AsyncGenerator

class Base(DeclarativeBase):
    pass

# .env 中 DATABASE_URL=sqlite:///data/zhixi.db
# 运行时自动转换为 sqlite+aiosqlite:///data/zhixi.db
def get_async_url(url: str) -> str:
    return url.replace("sqlite:///", "sqlite+aiosqlite:///")

engine = create_async_engine(get_async_url(settings.DATABASE_URL), echo=False)

# WAL 模式 + busy_timeout（通过底层同步连接事件设置）
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()

async_session = async_sessionmaker(
    engine, class_=AsyncSession, expire_on_commit=False
)

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
```

**规则**:
- 所有路由和 Service 方法为 `async def`
- DB 操作用 `await session.execute(...)` / `await session.flush()` 等
- 事务由 `get_db` 依赖统一管理：正常结束自动 commit，异常自动 rollback
- Service 内需要细粒度事务控制时可手动 `await self.db.flush()`（写入但不提交）

### Service 层依赖注入

构造函数注入 `AsyncSession`，通过 FastAPI `Depends` 组装。

```python
# app/api/deps.py
def get_digest_service(db: AsyncSession = Depends(get_db)) -> DigestService:
    return DigestService(db)

def get_process_service(db: AsyncSession = Depends(get_db)) -> ProcessService:
    return ProcessService(db, claude_client=get_claude_client())
```

**需要多个 Service 协作时**（如 add-tweet 需要 fetch + process + digest）:

```python
@router.post("/add-tweet")
async def add_tweet(
    db: AsyncSession = Depends(get_db),
    body: AddTweetRequest,
):
    fetch_svc = FetchService(db)
    process_svc = ProcessService(db, claude_client=get_claude_client())
    digest_svc = DigestService(db)

    tweet = await fetch_svc.fetch_single_tweet(body.tweet_url, ...)
    await process_svc.process_single_tweet(tweet.id)
    item = await digest_svc.add_item_to_digest(...)
    return {"message": "补录成功", "item": item}
```

**Client 注入**: 无状态外部客户端用模块级惰性单例

```python
# app/clients/claude_client.py
_client: ClaudeClient | None = None

def get_claude_client() -> ClaudeClient:
    global _client
    if _client is None:
        _client = ClaudeClient(
            api_key=settings.ANTHROPIC_API_KEY,
            model=settings.CLAUDE_MODEL,
        )
    return _client
```

**依赖文件位置**: `app/api/deps.py` 集中管理所有依赖工厂函数，避免循环导入。

**API 成本记录职责分工**: `ClaudeClient.complete()` 返回 `ClaudeResponse`（含 input_tokens, output_tokens, duration_ms），**由调用方（Service 层）负责写入 `api_cost_log`**。ClaudeClient 本身不持有 db session，不直接操作数据库。同理 Gemini/X API client 返回调用元数据，Service 层负责记录。

### CLI 异步适配

Typer 不原生支持 async，通过 `asyncio.run()` 桥接。CLI 中 `async_session()` 自行管理事务（不经过 FastAPI 的 `get_db` 依赖）。

```python
# app/cli.py
@app.command()
def pipeline():
    asyncio.run(_run_pipeline())

async def _run_pipeline():
    async with async_session() as db:
        try:
            fetch_svc = FetchService(db)
            process_svc = ProcessService(db, claude_client=get_claude_client())
            digest_svc = DigestService(db)
            await fetch_svc.run_daily_fetch(digest_date)
            await process_svc.run_daily_process(digest_date)
            await digest_svc.generate_daily_digest(digest_date)
            await db.commit()
        except Exception:
            await db.rollback()
            raise
```

### FastAPI 应用骨架

```python
# app/main.py
@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()

app = FastAPI(title="智曦 API", version="1.0.0", lifespan=lifespan)

# CORS 仅 DEBUG 模式
if settings.DEBUG:
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], ...)

# 8 组路由注册
app.include_router(setup_router,     prefix="/api/setup",     tags=["初始化"])
app.include_router(auth_router,      prefix="/api/auth",      tags=["认证"])
app.include_router(accounts_router,  prefix="/api/accounts",  tags=["大V管理"])
app.include_router(digest_router,    prefix="/api/digest",    tags=["日报"])
app.include_router(manual_router,    prefix="/api/manual",    tags=["手动操作"])
app.include_router(settings_router,  prefix="/api/settings",  tags=["设置"])
app.include_router(dashboard_router, prefix="/api/dashboard", tags=["仪表盘"])
app.include_router(history_router,   prefix="/api/history",   tags=["历史记录"])

# Vue SPA 静态文件（生产环境）
ADMIN_DIST = Path("admin/dist")
if ADMIN_DIST.exists():
    app.mount("/assets", StaticFiles(directory=ADMIN_DIST / "assets"), name="static")
    @app.get("/{path:path}")
    async def spa_fallback(path: str):
        file_path = ADMIN_DIST / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(file_path)
        return FileResponse(ADMIN_DIST / "index.html")
```

### Alembic 配置

```python
# alembic/env.py
from app.database import Base, engine
from app.models import *  # noqa: F401
target_metadata = Base.metadata

def run_migrations_online():
    connectable = engine.sync_engine
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()
```

`app/models/__init__.py` 集中注册所有模型类。`alembic.ini` 的 `sqlalchemy.url` 留空，由 env.py 从 engine 获取。

### 前端开发环境

```typescript
// admin/vite.config.ts
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { fileURLToPath, URL } from 'node:url'

export default defineConfig({
  plugins: [vue()],
  server: { proxy: { '/api': 'http://localhost:8000' } },
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } }
})
```

**开发启动**:
1. 终端 1: `cd admin && bun dev` → Vite（默认 5173）
2. 终端 2: `uvicorn app.main:app --reload --port 8000`
3. 浏览器访问 `http://localhost:5173`，API 自动代理到 8000

### Preview Token 实现

```python
# app/auth.py
import secrets
PREVIEW_TOKEN_EXPIRY_HOURS = 24

def generate_preview_token() -> tuple[str, datetime]:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(hours=PREVIEW_TOKEN_EXPIRY_HOURS)
    return token, expires_at
```

规范中 "UUID+HMAC" 的意图是不可猜测性，`token_urlsafe(32)` 提供等价的密码学安全随机性，实现更简洁。

**验证流程**:
1. 收到 token → 查询 `daily_digest.preview_token == token`
2. 检查 `preview_expires_at > utcnow()`
3. 检查 `is_current == true`（版本切换后旧 token 自动失效）
4. 任一不满足 → 403 `{"detail": "链接已失效或过期"}`

### 登录限流器

```python
# app/auth.py
from dataclasses import dataclass

@dataclass
class LoginAttempt:
    fail_count: int = 0
    locked_until: datetime | None = None

# 内存计数器（进程重启归零，MVP 可接受）
_login_attempts: dict[str, LoginAttempt] = {}
LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)

def check_login_rate_limit(username: str) -> bool:
    """返回 True 表示允许登录，False 表示被锁定"""
    attempt = _login_attempts.get(username)
    if not attempt:
        return True
    if attempt.locked_until and datetime.utcnow() < attempt.locked_until:
        return False
    # 锁定时间已过，重置
    if attempt.locked_until and datetime.utcnow() >= attempt.locked_until:
        _login_attempts.pop(username, None)
    return True

def record_login_failure(username: str):
    attempt = _login_attempts.setdefault(username, LoginAttempt())
    attempt.fail_count += 1
    if attempt.fail_count >= LOCKOUT_THRESHOLD:
        attempt.locked_until = datetime.utcnow() + LOCKOUT_DURATION

def record_login_success(username: str):
    _login_attempts.pop(username, None)
```

### config.py Settings 类

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    X_API_BEARER_TOKEN: str
    ANTHROPIC_API_KEY: str
    CLAUDE_MODEL: str = "claude-sonnet-4-20250514"
    CLAUDE_INPUT_PRICE_PER_MTOK: float = 3.0
    CLAUDE_OUTPUT_PRICE_PER_MTOK: float = 15.0
    GEMINI_API_KEY: str = ""
    WECHAT_APP_ID: str = ""
    WECHAT_APP_SECRET: str = ""
    JWT_SECRET_KEY: str
    JWT_EXPIRE_HOURS: int = 72
    DATABASE_URL: str = "sqlite:///data/zhixi.db"
    DEBUG: bool = False
    TIMEZONE: str = "Asia/Shanghai"
    LOG_LEVEL: str = "INFO"
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    DOMAIN: str = ""
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}

settings = Settings()
```

**必填项缺失**: `X_API_BEARER_TOKEN`、`ANTHROPIC_API_KEY`、`JWT_SECRET_KEY` 为空时 Pydantic 启动即抛 `ValidationError`。

**业务配置**从 DB system_config 读取:
```python
async def get_system_config(db: AsyncSession, key: str, default: str = "") -> str:
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    config = result.scalar_one_or_none()
    return config.value if config else default
```

### 测试基础设施

```python
# tests/conftest.py
@pytest_asyncio.fixture
async def db_engine():
    test_engine = create_async_engine("sqlite+aiosqlite://", echo=False)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield test_engine
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()

@pytest_asyncio.fixture
async def db(db_engine) -> AsyncGenerator[AsyncSession, None]:
    factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session

@pytest_asyncio.fixture
async def client(db: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_get_db():
        yield db
    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
```

**预置数据 fixture**:

```python
@pytest_asyncio.fixture
async def seeded_db(db: AsyncSession) -> AsyncSession:
    """写入 system_config 默认数据的 session"""
    from app.models.config import SystemConfig
    defaults = [
        SystemConfig(key="push_time", value="08:00"),
        SystemConfig(key="push_days", value="1,2,3,4,5,6,7"),
        SystemConfig(key="top_n", value="10"),
        SystemConfig(key="min_articles", value="1"),
        # ...其余默认配置
    ]
    db.add_all(defaults)
    await db.commit()
    return db
```

**Mock 策略**:

| 外部依赖 | Mock 方式 | 说明 |
|----------|----------|------|
| Claude API | `unittest.mock.AsyncMock` patch `ClaudeClient.complete` | 返回预设的 `ClaudeResponse` |
| X API | `respx` mock httpx 请求 | 返回预设的 X API JSON |
| Notifier | `unittest.mock.AsyncMock` patch `Notifier.send_alert` | 验证调用参数 |
| 时间 | `freezegun.freeze_time` | 固定 `get_today_digest_date()` 返回值 |

**LLM Mock 数据管理**:

- Mock 响应数据（Claude 全局分析输出、逐条加工输出等）集中存放在 `tests/fixtures/` 目录下
- 按模块和场景组织：`tests/fixtures/analyzer/global_analysis_response.json`、`tests/fixtures/translator/single_tweet_response.json` 等
- 测试中通过 `conftest.py` 加载 fixture 文件，避免在测试函数中硬编码大段 JSON
- fixture 文件必须与 spec 中定义的 JSON Schema 保持一致

**pytest 配置**:

```toml
# pyproject.toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

### 热度公式

`hours_since_post` 参考时间点固定为 **digest_date 当日北京时间 06:00**。

```python
engagement = likes * 1 + retweets * 3 + replies * 2
base_score = engagement * author_weight * exp(-0.05 * hours)
# 归一化后: heat_score = normalized_base * 0.7 + ai_importance * 0.3
```

### API 成本估算

```python
estimated_cost = (input_tokens * price_per_mtok / 1_000_000
                  + output_tokens * price_per_mtok / 1_000_000)
```

默认 $3/$15 per MTok，可通过环境变量覆盖。保留 6 位小数。

### 响应格式约定

| 场景 | 状态码 | 响应体 |
|------|--------|--------|
| 操作成功（有消息） | 200 | `{"message": "操作描述", ...}` |
| 创建成功 | 201 | 资源对象 |
| 查询成功 | 200 | 数据对象 |
| 客户端错误 | 400/422 | `{"detail": "错误描述"}` |
| 未认证 | 401 | `{"detail": "登录已过期，请重新登录"}` |
| 无权限 | 403 | `{"detail": "链接已失效或过期"}` |
| 资源冲突 | 409 | `{"detail": "当前有任务在运行中，请稍后再试"}` |
| 登录锁定 | 423 | `{"detail": "登录失败次数过多，请15分钟后再试"}` |
| 服务端错误 | 500/502 | `{"detail": "错误描述"}` |

**规则**: 错误统一用 `HTTPException`。所有中文消息面向终端用户。

### 分页约定

`page` + `page_size`，默认 `page=1, page_size=20`，上限 100。

```json
{"items": [...], "total": 45, "page": 1, "page_size": 20}
```

---

## API 契约

### X API 端点

**抓取推文**: `GET /2/users/{id}/tweets`
- 参数: `exclude=retweets`, `max_results=100`, `start_time`, `end_time`, `tweet.fields=created_at,public_metrics,attachments,referenced_tweets`, `expansions=attachments.media_keys,referenced_tweets.id`, `media.fields=url,type`
- 分页: `meta.next_token` → `pagination_token`，最多 5 页
- 解析要点:
  - `data[].referenced_tweets[].type` 决定推文类型
  - 自回复判断: `referenced_tweets.type == "replied_to"` 且 `includes.tweets` 中父推文 `author_id` 与当前推文作者相同
  - `includes.media[].url` 提取图片 URL，通过 `media_key` 关联
  - `meta.next_token` 用于分页

**响应结构示例**:
```json
{
  "data": [{
    "id": "1234567890",
    "text": "This is a tweet about AI...",
    "created_at": "2026-03-18T10:30:00.000Z",
    "public_metrics": {"like_count": 150, "retweet_count": 30, "reply_count": 12, "quote_count": 5},
    "referenced_tweets": [{"type": "replied_to", "id": "1234567889"}],
    "attachments": {"media_keys": ["media_001"]}
  }],
  "includes": {
    "tweets": [{"id": "1234567889", "author_id": "user_sama", "text": "Parent tweet..."}],
    "media": [{"media_key": "media_001", "type": "photo", "url": "https://pbs.twimg.com/media/xxx.jpg"}]
  },
  "meta": {"result_count": 10, "next_token": "abc123"}
}
```

**单条查询**: `GET /2/tweets/{id}`（参数同上，`data` 为单个对象而非数组）
- URL 解析: 正则 `/status/(\d+)/`

**用户信息**: `GET /2/users/by/username/{handle}`
- 参数: `user.fields=name,description,profile_image_url,public_metrics`
- 认证: `Authorization: Bearer {X_API_BEARER_TOKEN}`

```json
{
  "data": {
    "id": "123456789",
    "name": "Andrej Karpathy",
    "username": "karpathy",
    "description": "AI researcher, educator...",
    "profile_image_url": "https://pbs.twimg.com/profile_images/xxx.jpg",
    "public_metrics": {"followers_count": 950000, "following_count": 500, "tweet_count": 5000}
  }
}
```

- 映射: data.id→twitter_user_id, data.name→display_name, data.username→twitter_handle, data.description→bio, data.profile_image_url→avatar_url, data.public_metrics.followers_count→followers_count
- 失败: 404/网络错误 → 502 `{"detail": "X API拉取失败", "allow_manual": true}`

### 后端 API 端点

#### 初始化与认证

```
POST /api/setup/init
  请求: {"password": "Admin123", "notification_webhook_url": "..."}
  成功: 200 {"message": "初始化完成"}
  错误: 422 "密码强度不足" | 403 "系统已完成初始化"

POST /api/auth/login
  请求: {"username": "admin", "password": "xxx"}
  成功: 200 {"token": "eyJ...", "expires_at": "..."}
  错误: 401 "用户名或密码错误" | 423 "登录失败次数过多"
```

#### 大V管理

```
GET  /api/accounts → 列表
POST /api/accounts
  请求: {"twitter_handle": "karpathy", "weight": 1.3}
  成功: 201 account
  错误: 409 "该账号已存在" | 502 {"detail": "X API拉取失败", "allow_manual": true}
PUT  /api/accounts/{id} → {"weight": 1.5, "is_active": false}
DELETE /api/accounts/{id} → 软删除（is_active=false）
```

#### 日报操作

```
GET  /api/digest/today → {digest, items[], low_content_warning}
PUT  /api/digest/item/{item_type}/{item_ref_id} → 编辑快照
PUT  /api/digest/summary → 编辑导读
PUT  /api/digest/reorder → {items: [{id, display_order, is_pinned}]}
POST /api/digest/exclude/{type}/{id}
POST /api/digest/restore/{type}/{id}
POST /api/digest/add-tweet → {"tweet_url": "..."}
POST /api/digest/regenerate → 同步执行
POST /api/digest/preview-link → {"preview_url": "...", "expires_at": "..."}
GET  /api/digest/preview/{token} → 同 today 结构
GET  /api/digest/markdown → content_markdown 文本
POST /api/digest/mark-published
POST /api/digest/publish → 根据 publish_mode 分支
```

#### 手动操作

```
POST /api/manual/fetch → {"message": "抓取完成", "job_run_id": 16, "new_tweets": 5}
POST /api/manual/generate-cover → 手动触发封面图
```

#### 设置

```
GET /api/settings → 业务配置（不含密钥）
PUT /api/settings → 部分更新
GET /api/settings/api-status → {x_api, claude_api, gemini_api, wechat_api}
```

API 状态检测: 每个 5 秒超时，`asyncio.gather` 并发，总耗时 ≤10 秒。status: ok/error/unconfigured。

Ping 方式: X API→`GET /2/users/me`, Claude→`models.list()`, Gemini→`list_models()`, WeChat→跳过(MVP)。

**GET /api/settings 响应**:
```json
{"push_time":"08:00","push_days":[1,2,3,4,5,6,7],"top_n":10,"min_articles":1,
 "publish_mode":"manual","enable_cover_generation":false,"cover_generation_timeout":30,
 "notification_webhook_url":""}
```
`push_days` 从 DB 逗号字符串转整数数组。PUT 接受相同结构的部分更新。

**GET /api/settings/api-status 响应**:
```json
{"x_api":{"status":"ok","latency_ms":230},"claude_api":{"status":"ok","latency_ms":450},
 "gemini_api":{"status":"unconfigured"},"wechat_api":{"status":"unconfigured"}}
```

#### Dashboard

```
GET /api/dashboard/overview → {today, recent_7_days, alerts}
GET /api/dashboard/api-costs → {today, this_month}
GET /api/dashboard/api-costs/daily → 30天趋势
GET /api/dashboard/logs?level=INFO&limit=100 → {logs: [...]}
```

**api-costs 响应**:
```json
{"today":{"total_cost":0.85,"by_service":[{"service":"claude","call_count":25,"total_tokens":150000,"estimated_cost":0.82}]},
 "this_month":{"total_cost":18.50,"by_service":[...]}}
```

**api-costs/daily 响应**: 最近30天按日期降序。
```json
{"days":[{"date":"2026-03-18","total_cost":1.20,"claude_cost":1.15,"x_cost":0.05}]}
```

**logs 响应**: 每行一个 JSON 对象（JSON Lines 格式），按 level 过滤，默认100条，上限500。
```json
{"logs":[{"timestamp":"2026-03-18T22:05:30Z","level":"INFO","message":"Pipeline started","module":"fetch_service"}]}
```

**alerts 生成逻辑**: 从 job_runs 表生成，近7天 pipeline/fetch 类型 failed 记录，按 started_at 降序。

#### 手动填写表单字段（大V添加 X API 失败时）

| 字段 | 必填 | 说明 |
|------|------|------|
| twitter_handle | 是 | 已由用户输入 |
| display_name | 是 | 显示名称 |
| bio | 否 | 简介 |

后端检测到 `display_name` 存在时跳过 X API 拉取。`twitter_user_id`/`avatar_url`/`followers_count` 留空。

#### 编辑 API 请求字段映射

**tweet 类型**: `PUT /api/digest/item/tweet/{id}`

| 请求字段 | 对应 snapshot | 说明 |
|---------|-------------|------|
| title | snapshot_title | 标题 |
| translation | snapshot_translation | 翻译 |
| comment | snapshot_comment | 点评 |

**topic (aggregated) 类型**: `PUT /api/digest/item/topic/{id}`

| 请求字段 | 对应 snapshot | 说明 |
|---------|-------------|------|
| title | snapshot_title | 话题标题 |
| summary | snapshot_summary | 综合摘要 |
| perspectives | snapshot_perspectives | JSON 数组 |
| comment | snapshot_comment | 编辑点评 |

**topic (thread) 类型**: `PUT /api/digest/item/topic/{id}`

| 请求字段 | 对应 snapshot | 说明 |
|---------|-------------|------|
| title | snapshot_title | 标题 |
| translation | snapshot_translation | Thread 翻译 |
| comment | snapshot_comment | 点评 |

所有字段可选（partial update）。

#### 历史

```
GET /api/history?page=1&page_size=20 → 分页，每日期一条
    版本选择: published → is_current → max version
GET /api/history/{id} → 完整信息 + items 快照
```

### 前端 API 封装

> **API 类型来自 `packages/openapi-client`**（由 `@hey-api/openapi-ts` 从后端 OpenAPI 生成）。`admin/src/api/index.ts` 只负责 axios 基础配置（baseURL、JWT 拦截、错误处理），具体 API 调用使用生成客户端的类型约束请求和响应。禁止在前端手写 API 响应类型。

```typescript
// admin/src/api/index.ts
import axios, { type AxiosError } from 'axios'
import { showToast } from 'vant'
import router from '@/router'

interface ApiError {
  detail: string
}

const api = axios.create({
  baseURL: '/api',
  timeout: 300000,
  headers: { 'Content-Type': 'application/json' }
})

api.interceptors.request.use(config => {
  const token = localStorage.getItem('zhixi_token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

api.interceptors.response.use(
  response => response,
  (error: AxiosError<ApiError>) => {
    const status = error.response?.status
    const detail = error.response?.data?.detail ?? '未知错误'
    if (status === 401) {
      localStorage.removeItem('zhixi_token')
      router.push('/login')
      showToast('登录已过期，请重新登录')
    } else if (status === 409) {
      showToast(detail)
    } else if (status === 423) {
      showToast(detail)
    } else {
      showToast(`操作失败：${detail}`)
    }
    return Promise.reject(error)
  }
)
export default api
```

### 路由守卫

```typescript
// router/index.ts
const WHITE_LIST = ['/setup', '/login', '/preview']
let setupStatus: boolean | null = null  // 模块级缓存

router.beforeEach(async (to) => {
  if (WHITE_LIST.some(path => to.path.startsWith(path))) return true
  if (setupStatus === null) {
    const { data } = await api.get<{ need_setup: boolean }>('/setup/status')
    setupStatus = data.need_setup
  }
  if (setupStatus) return '/setup'
  const token = localStorage.getItem('zhixi_token')
  if (!token) return '/login'
  return true
})
```

**Setup 完成后**: 将 `setupStatus` 置为 `false`，然后 `router.push('/login')`。

**`/preview` 路由**: mounted 时从 URL 读取 token 参数，调用 `GET /api/digest/preview/{token}`。token 无效时展示"链接已失效"提示页。
