# P0 第二批实施计划：US-003/006/011/012/047/053

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 完成 P0 阶段剩余的可启动 US — 推文分类器、BaseFetcher 抽象基类、SQLite 备份/清理、定时任务调度。

**Architecture:** 四个独立模块，互不依赖，可并行实施。推文分类器（纯函数）和 BaseFetcher（抽象+httpx）属于 M1 Fetcher 层；备份服务属于 M5 基础设施；定时调度属于运维配置。所有模块遵循 TDD 工作流。

**Tech Stack:** Python 3.12+ / FastAPI / SQLAlchemy 2.x / aiosqlite / httpx / pytest / respx

---

## 文件结构

| 操作 | 文件路径 | 职责 |
|------|---------|------|
| 修改 | `app/fetcher/tweet_classifier.py` | 推文分类纯函数 `classify_tweet()` |
| 修改 | `app/fetcher/base.py` | `BaseFetcher` ABC + `RawTweet` 解析辅助 |
| 修改 | `app/fetcher/x_api.py` | `XApiFetcher(BaseFetcher)` — httpx 调用 X API |
| 修改 | `app/fetcher/third_party.py` | 空壳 `ThirdPartyFetcher` + TODO |
| 修改 | `app/fetcher/__init__.py` | 导出 `get_fetcher()` 工厂函数 |
| 修改 | `app/services/backup_service.py` | `BackupService` — sqlite3 backup API + 清理逻辑 |
| 修改 | `app/cli.py` | 实现 `_run_backup()` / `_run_cleanup()` |
| 创建 | `crontab` | supercronic 调度配置 |
| 创建 | `tests/test_tweet_classifier.py` | 分类器测试（US-047） |
| 创建 | `tests/test_fetcher.py` | BaseFetcher + XApiFetcher 测试 |
| 创建 | `tests/test_backup.py` | 备份与清理测试（US-053） |

---

## Task 1: US-012 + US-047 — 推文分类器

**Files:**
- Modify: `app/fetcher/tweet_classifier.py`
- Create: `tests/test_tweet_classifier.py`

### Step 1: 编写失败测试 — 覆盖全部 5 种类型

- [ ] **Step 1.1: 创建测试文件，编写 10+ 个测试用例**

> **注意**: `classify_tweet` 仅负责分类，过滤逻辑（使用 `KEEP_TYPES` 集合）将在 US-013 的 fetch_service 中实现。

```python
# tests/test_tweet_classifier.py
"""推文分类器测试（US-047）。"""

from datetime import UTC, datetime

from app.fetcher.tweet_classifier import classify_tweet
from app.schemas.fetcher_types import PublicMetrics, RawTweet, ReferencedTweet, TweetType


def _make_tweet(
    referenced_tweets: list[ReferencedTweet] | None = None,
    author_id: str = "user_123",
) -> RawTweet:
    """构造测试用 RawTweet。"""
    return RawTweet(
        tweet_id="t_1",
        author_id=author_id,
        text="test tweet",
        created_at=datetime(2026, 3, 18, 10, 0, 0, tzinfo=UTC),
        public_metrics=PublicMetrics(),
        referenced_tweets=referenced_tweets or [],
    )


# --- ORIGINAL（无 referenced_tweets）---

class TestOriginal:
    def test_no_references(self) -> None:
        tweet = _make_tweet()
        assert classify_tweet(tweet) == TweetType.ORIGINAL

    def test_empty_references(self) -> None:
        tweet = _make_tweet(referenced_tweets=[])
        assert classify_tweet(tweet) == TweetType.ORIGINAL


# --- SELF_REPLY（replied_to 且同作者）---

class TestSelfReply:
    def test_same_author_reply(self) -> None:
        tweet = _make_tweet(
            author_id="user_123",
            referenced_tweets=[ReferencedTweet(type="replied_to", id="t_0", author_id="user_123")],
        )
        assert classify_tweet(tweet) == TweetType.SELF_REPLY

    def test_thread_continuation(self) -> None:
        tweet = _make_tweet(
            author_id="alice",
            referenced_tweets=[ReferencedTweet(type="replied_to", id="t_parent", author_id="alice")],
        )
        assert classify_tweet(tweet) == TweetType.SELF_REPLY


# --- REPLY（replied_to 且非同作者）---

class TestReply:
    def test_different_author_reply(self) -> None:
        tweet = _make_tweet(
            author_id="user_123",
            referenced_tweets=[ReferencedTweet(type="replied_to", id="t_0", author_id="other_user")],
        )
        assert classify_tweet(tweet) == TweetType.REPLY

    def test_reply_to_stranger(self) -> None:
        tweet = _make_tweet(
            author_id="bob",
            referenced_tweets=[ReferencedTweet(type="replied_to", id="t_x", author_id="charlie")],
        )
        assert classify_tweet(tweet) == TweetType.REPLY


# --- QUOTE（quoted 类型）---

class TestQuote:
    def test_quote_tweet(self) -> None:
        tweet = _make_tweet(
            referenced_tweets=[ReferencedTweet(type="quoted", id="t_0", author_id="anyone")],
        )
        assert classify_tweet(tweet) == TweetType.QUOTE

    def test_quote_self(self) -> None:
        tweet = _make_tweet(
            author_id="user_123",
            referenced_tweets=[ReferencedTweet(type="quoted", id="t_0", author_id="user_123")],
        )
        assert classify_tweet(tweet) == TweetType.QUOTE


# --- RETWEET（retweeted 类型）---

class TestRetweet:
    def test_retweet(self) -> None:
        tweet = _make_tweet(
            referenced_tweets=[ReferencedTweet(type="retweeted", id="t_0", author_id="anyone")],
        )
        assert classify_tweet(tweet) == TweetType.RETWEET

    def test_retweet_self(self) -> None:
        tweet = _make_tweet(
            author_id="user_123",
            referenced_tweets=[ReferencedTweet(type="retweeted", id="t_0", author_id="user_123")],
        )
        assert classify_tweet(tweet) == TweetType.RETWEET
```

- [ ] **Step 1.2: 运行测试验证全部失败**

Run: `uv run pytest tests/test_tweet_classifier.py -v`
Expected: FAIL — `classify_tweet` 尚未定义

### Step 2: 实现分类器

- [ ] **Step 2.1: 编写 classify_tweet 函数**

```python
# app/fetcher/tweet_classifier.py
"""推文分类器 — 根据 referenced_tweets 判断推文类型。"""

from app.schemas.fetcher_types import RawTweet, TweetType


def classify_tweet(raw_tweet: RawTweet) -> TweetType:
    """根据 referenced_tweets 字段分类推文。

    - 无 referenced_tweets → ORIGINAL
    - replied_to + 同作者 → SELF_REPLY
    - replied_to + 非同作者 → REPLY
    - quoted → QUOTE
    - retweeted → RETWEET
    """
    if not raw_tweet.referenced_tweets:
        return TweetType.ORIGINAL

    ref = raw_tweet.referenced_tweets[0]

    if ref.type == "retweeted":
        return TweetType.RETWEET

    if ref.type == "quoted":
        return TweetType.QUOTE

    if ref.type == "replied_to":
        if ref.author_id == raw_tweet.author_id:
            return TweetType.SELF_REPLY
        return TweetType.REPLY

    return TweetType.ORIGINAL
```

- [ ] **Step 2.2: 运行测试验证全部通过**

Run: `uv run pytest tests/test_tweet_classifier.py -v`
Expected: 10 tests PASS

- [ ] **Step 2.3: 运行 lint + 类型检查**

Run: `uv run ruff check app/fetcher/tweet_classifier.py tests/test_tweet_classifier.py && uv run pyright app/fetcher/tweet_classifier.py`

- [ ] **Step 2.4: 提交**

```bash
git add app/fetcher/tweet_classifier.py tests/test_tweet_classifier.py
git commit -m "feat(fetcher): US-012+047 推文分类器及测试"
```

---

## Task 2: US-011 — BaseFetcher 抽象基类

**Files:**
- Modify: `app/fetcher/base.py`
- Modify: `app/fetcher/x_api.py`
- Modify: `app/fetcher/third_party.py`
- Modify: `app/fetcher/__init__.py`
- Create: `tests/test_fetcher.py`

### Step 1: 编写测试

- [ ] **Step 1.1: 创建 XApiFetcher 测试（使用 respx mock）**

```python
# tests/test_fetcher.py
"""BaseFetcher + XApiFetcher 测试（US-011）。"""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.fetcher.base import BaseFetcher
from app.fetcher.x_api import XApiFetcher
from app.schemas.fetcher_types import RawTweet


class TestBaseFetcherIsAbstract:
    """BaseFetcher 不可直接实例化。"""

    def test_cannot_instantiate(self) -> None:
        with pytest.raises(TypeError):
            BaseFetcher()  # type: ignore[abstract]


class TestXApiFetcherParsing:
    """XApiFetcher X API 响应解析。"""

    @respx.mock
    async def test_fetch_user_tweets_basic(self) -> None:
        """正常单页响应 — 解析 data + includes。"""
        api_response = {
            "data": [
                {
                    "id": "111",
                    "text": "Hello AI world",
                    "created_at": "2026-03-18T10:00:00.000Z",
                    "public_metrics": {
                        "like_count": 100,
                        "retweet_count": 20,
                        "reply_count": 5,
                        "quote_count": 3,
                    },
                }
            ],
            "meta": {"result_count": 1},
        }
        respx.get("https://api.x.com/2/users/u1/tweets").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        fetcher = XApiFetcher(bearer_token="test_token")
        since = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        until = datetime(2026, 3, 18, 21, 59, 59, tzinfo=UTC)

        result = await fetcher.fetch_user_tweets("u1", since, until)

        assert len(result) == 1
        assert result[0].tweet_id == "111"
        assert result[0].text == "Hello AI world"
        assert result[0].public_metrics.like_count == 100

    @respx.mock
    async def test_fetch_with_referenced_tweets(self) -> None:
        """带 referenced_tweets 的响应 — author_id 从 includes.tweets 提取。"""
        api_response = {
            "data": [
                {
                    "id": "222",
                    "text": "My reply",
                    "created_at": "2026-03-18T11:00:00.000Z",
                    "public_metrics": {
                        "like_count": 10,
                        "retweet_count": 2,
                        "reply_count": 1,
                        "quote_count": 0,
                    },
                    "referenced_tweets": [{"type": "replied_to", "id": "221"}],
                }
            ],
            "includes": {
                "tweets": [{"id": "221", "author_id": "same_author"}]
            },
            "meta": {"result_count": 1},
        }
        respx.get("https://api.x.com/2/users/u1/tweets").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        fetcher = XApiFetcher(bearer_token="test_token")
        since = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        until = datetime(2026, 3, 18, 21, 59, 59, tzinfo=UTC)

        result = await fetcher.fetch_user_tweets("u1", since, until)

        assert len(result) == 1
        assert result[0].referenced_tweets[0].author_id == "same_author"

    @respx.mock
    async def test_fetch_with_media(self) -> None:
        """带 media 的响应 — 从 includes.media 提取 URL。"""
        api_response = {
            "data": [
                {
                    "id": "333",
                    "text": "Check this image",
                    "created_at": "2026-03-18T12:00:00.000Z",
                    "public_metrics": {
                        "like_count": 50,
                        "retweet_count": 10,
                        "reply_count": 3,
                        "quote_count": 1,
                    },
                    "attachments": {"media_keys": ["mk_1"]},
                }
            ],
            "includes": {
                "media": [
                    {"media_key": "mk_1", "type": "photo", "url": "https://pbs.twimg.com/media/img.jpg"}
                ]
            },
            "meta": {"result_count": 1},
        }
        respx.get("https://api.x.com/2/users/u1/tweets").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        fetcher = XApiFetcher(bearer_token="test_token")
        since = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        until = datetime(2026, 3, 18, 21, 59, 59, tzinfo=UTC)

        result = await fetcher.fetch_user_tweets("u1", since, until)

        assert result[0].media_urls == ["https://pbs.twimg.com/media/img.jpg"]

    @respx.mock
    async def test_fetch_pagination(self) -> None:
        """分页 — 最多跟 5 页 next_token。"""
        page1 = {
            "data": [{"id": "p1", "text": "page1", "created_at": "2026-03-18T10:00:00.000Z",
                       "public_metrics": {"like_count": 1, "retweet_count": 0, "reply_count": 0, "quote_count": 0}}],
            "meta": {"result_count": 1, "next_token": "tok2"},
        }
        page2 = {
            "data": [{"id": "p2", "text": "page2", "created_at": "2026-03-18T10:00:00.000Z",
                       "public_metrics": {"like_count": 1, "retweet_count": 0, "reply_count": 0, "quote_count": 0}}],
            "meta": {"result_count": 1},
        }
        route = respx.get("https://api.x.com/2/users/u1/tweets")
        route.side_effect = [
            httpx.Response(200, json=page1),
            httpx.Response(200, json=page2),
        ]
        fetcher = XApiFetcher(bearer_token="test_token")
        since = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        until = datetime(2026, 3, 18, 21, 59, 59, tzinfo=UTC)

        result = await fetcher.fetch_user_tweets("u1", since, until)

        assert len(result) == 2
        assert route.call_count == 2

    @respx.mock
    async def test_fetch_empty_response(self) -> None:
        """无推文 — 返回空列表。"""
        api_response = {"meta": {"result_count": 0}}
        respx.get("https://api.x.com/2/users/u1/tweets").mock(
            return_value=httpx.Response(200, json=api_response)
        )
        fetcher = XApiFetcher(bearer_token="test_token")
        since = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        until = datetime(2026, 3, 18, 21, 59, 59, tzinfo=UTC)

        result = await fetcher.fetch_user_tweets("u1", since, until)

        assert result == []

    @respx.mock
    async def test_pagination_max_5_pages(self) -> None:
        """分页上限 5 页。"""
        pages = []
        for i in range(6):
            page = {
                "data": [{"id": f"t{i}", "text": f"page{i}", "created_at": "2026-03-18T10:00:00.000Z",
                           "public_metrics": {"like_count": 0, "retweet_count": 0, "reply_count": 0, "quote_count": 0}}],
                "meta": {"result_count": 1, "next_token": f"tok{i + 1}"},
            }
            pages.append(httpx.Response(200, json=page))
        route = respx.get("https://api.x.com/2/users/u1/tweets")
        route.side_effect = pages
        fetcher = XApiFetcher(bearer_token="test_token")
        since = datetime(2026, 3, 17, 22, 0, 0, tzinfo=UTC)
        until = datetime(2026, 3, 18, 21, 59, 59, tzinfo=UTC)

        result = await fetcher.fetch_user_tweets("u1", since, until)

        assert len(result) == 5  # 最多 5 页
        assert route.call_count == 5


class TestGetFetcher:
    """工厂函数测试。"""

    def test_get_fetcher_returns_base_fetcher(self) -> None:
        from app.fetcher import get_fetcher
        from app.fetcher.base import BaseFetcher
        fetcher = get_fetcher(bearer_token="test")
        assert isinstance(fetcher, BaseFetcher)
```

- [ ] **Step 1.2: 运行测试验证失败**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: FAIL — `BaseFetcher`、`XApiFetcher` 尚未实现

### Step 2: 实现 BaseFetcher

- [ ] **Step 2.1: 编写 BaseFetcher 抽象基类**

```python
# app/fetcher/base.py
"""BaseFetcher 抽象基类 — 定义推文抓取接口。"""

from abc import ABC, abstractmethod
from datetime import datetime

from app.schemas.fetcher_types import RawTweet


class BaseFetcher(ABC):
    """推文抓取器抽象基类。"""

    @abstractmethod
    async def fetch_user_tweets(
        self, user_id: str, since: datetime, until: datetime
    ) -> list[RawTweet]:
        """抓取指定用户在时间窗口内的推文。

        Args:
            user_id: X 平台用户 ID
            since: 起始时间（UTC）
            until: 截止时间（UTC）

        Returns:
            原始推文列表
        """
```

### Step 3: 实现 XApiFetcher

- [ ] **Step 3.1: 编写 XApiFetcher**

```python
# app/fetcher/x_api.py
"""XApiFetcher — 通过 X API v2 抓取推文。"""

import logging
from datetime import datetime

import httpx

from app.fetcher.base import BaseFetcher
from app.schemas.fetcher_types import PublicMetrics, RawTweet, ReferencedTweet

logger = logging.getLogger(__name__)

X_API_BASE = "https://api.x.com/2"
MAX_PAGES = 5


class XApiFetcher(BaseFetcher):
    """X API v2 推文抓取器。"""

    def __init__(self, bearer_token: str) -> None:
        self._bearer_token = bearer_token
        self._client = httpx.AsyncClient(
            base_url=X_API_BASE,
            headers={"Authorization": f"Bearer {bearer_token}"},
            timeout=30.0,
        )

    async def fetch_user_tweets(
        self, user_id: str, since: datetime, until: datetime
    ) -> list[RawTweet]:
        """调用 GET /2/users/{id}/tweets 抓取推文，支持分页。"""
        all_tweets: list[RawTweet] = []
        params: dict[str, str | int] = {
            "exclude": "retweets",
            "max_results": 100,
            "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "end_time": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "tweet.fields": "created_at,public_metrics,attachments,referenced_tweets",
            "expansions": "attachments.media_keys,referenced_tweets.id",
            "media.fields": "url,type",
        }
        pagination_token: str | None = None

        for page in range(MAX_PAGES):
            if pagination_token:
                params["pagination_token"] = pagination_token

            resp = await self._client.get(f"/users/{user_id}/tweets", params=params)
            resp.raise_for_status()
            body = resp.json()

            data = body.get("data", [])
            if not data:
                break

            includes = body.get("includes", {})
            include_tweets_map = {
                t["id"]: t.get("author_id", "")
                for t in includes.get("tweets", [])
            }
            media_map = {
                m["media_key"]: m.get("url", "")
                for m in includes.get("media", [])
                if m.get("url")
            }

            for item in data:
                tweet = self._parse_tweet(item, include_tweets_map, media_map, user_id)
                if tweet:
                    all_tweets.append(tweet)

            next_token = body.get("meta", {}).get("next_token")
            if not next_token:
                break
            pagination_token = next_token

        return all_tweets

    def _parse_tweet(
        self,
        item: dict,
        include_tweets_map: dict[str, str],
        media_map: dict[str, str],
        author_id: str,
    ) -> RawTweet | None:
        """将 X API 单条数据解析为 RawTweet。"""
        try:
            metrics = item.get("public_metrics", {})
            referenced = []
            for ref in item.get("referenced_tweets", []):
                ref_author = include_tweets_map.get(ref["id"], "")
                referenced.append(
                    ReferencedTweet(type=ref["type"], id=ref["id"], author_id=ref_author)
                )

            media_urls = []
            media_keys = item.get("attachments", {}).get("media_keys", [])
            for key in media_keys:
                url = media_map.get(key)
                if url:
                    media_urls.append(url)

            return RawTweet(
                tweet_id=item["id"],
                author_id=author_id,
                text=item["text"],
                created_at=item["created_at"],
                public_metrics=PublicMetrics(
                    like_count=metrics.get("like_count", 0),
                    retweet_count=metrics.get("retweet_count", 0),
                    reply_count=metrics.get("reply_count", 0),
                ),
                referenced_tweets=referenced,
                media_urls=media_urls,
            )
        except (KeyError, ValueError) as e:
            logger.warning("Skipping malformed tweet: %s — %s", item.get("id", "?"), e)
            return None

    async def close(self) -> None:
        """关闭 HTTP 客户端。"""
        await self._client.aclose()
```

- [ ] **Step 3.2: 更新 third_party.py 空壳**

```python
# app/fetcher/third_party.py
"""第三方数据源适配器（预留空壳）。"""

from datetime import datetime

from app.fetcher.base import BaseFetcher
from app.schemas.fetcher_types import RawTweet


class ThirdPartyFetcher(BaseFetcher):
    """第三方数据源抓取器（Phase 2 实现）。"""

    async def fetch_user_tweets(
        self, user_id: str, since: datetime, until: datetime
    ) -> list[RawTweet]:
        # TODO: Phase 2 实现第三方数据源接入
        raise NotImplementedError("第三方数据源抓取功能将在 Phase 2 实现")
```

- [ ] **Step 3.3: 更新 __init__.py 导出工厂函数**

```python
# app/fetcher/__init__.py
"""M1 数据采集模块。"""

from app.fetcher.base import BaseFetcher
from app.fetcher.x_api import XApiFetcher


def get_fetcher(bearer_token: str) -> BaseFetcher:
    """创建推文抓取器实例。"""
    return XApiFetcher(bearer_token=bearer_token)
```

- [ ] **Step 3.4: 运行测试验证通过**

Run: `uv run pytest tests/test_fetcher.py -v`
Expected: ALL PASS

- [ ] **Step 3.5: 运行 lint + 类型检查**

Run: `uv run ruff check app/fetcher/ tests/test_fetcher.py && uv run pyright app/fetcher/`

- [ ] **Step 3.6: 提交**

```bash
git add app/fetcher/ tests/test_fetcher.py
git commit -m "feat(fetcher): US-011 BaseFetcher 抽象基类 + XApiFetcher 实现"
```

---

## Task 3: US-003 + US-053 — SQLite 备份与清理

**Files:**
- Modify: `app/services/backup_service.py`
- Modify: `app/cli.py`
- Create: `tests/test_backup.py`

### Step 1: 编写测试

- [ ] **Step 1.1: 创建备份与清理测试**

```python
# tests/test_backup.py
"""备份与清理测试（US-053）。"""

import re
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun
from app.services.backup_service import BackupService


@pytest.fixture
def backup_dir(tmp_path: Path) -> Path:
    """临时备份目录。"""
    d = tmp_path / "backups"
    d.mkdir()
    return d


@pytest.fixture
def logs_dir(tmp_path: Path) -> Path:
    """临时日志目录。"""
    d = tmp_path / "logs"
    d.mkdir()
    return d


@pytest.fixture
def real_db(tmp_path: Path) -> Path:
    """创建一个真实的 SQLite 数据库文件用于备份测试。"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE test_table (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO test_table VALUES (1, 'test_data')")
    conn.commit()
    conn.close()
    return db_path


class TestBackup:
    """备份功能测试。"""

    async def test_backup_creates_file(
        self, real_db: Path, backup_dir: Path, db: AsyncSession
    ) -> None:
        """备份生成正确格式的文件名 zhixi_YYYYMMDD_HHMMSS.db。"""
        svc = BackupService(db)
        result = await svc.run_backup(
            db_path=str(real_db), backup_dir=str(backup_dir)
        )

        backup_files = list(backup_dir.glob("zhixi_*.db"))
        assert len(backup_files) == 1
        assert re.match(r"zhixi_\d{8}_\d{6}\.db", backup_files[0].name)
        assert result.success is True

    async def test_backup_file_is_valid_sqlite(
        self, real_db: Path, backup_dir: Path, db: AsyncSession
    ) -> None:
        """备份文件是有效的 SQLite 数据库。"""
        svc = BackupService(db)
        await svc.run_backup(db_path=str(real_db), backup_dir=str(backup_dir))

        backup_files = list(backup_dir.glob("zhixi_*.db"))
        conn = sqlite3.connect(str(backup_files[0]))
        cursor = conn.execute("SELECT name FROM test_table WHERE id = 1")
        assert cursor.fetchone()[0] == "test_data"
        conn.close()

    async def test_backup_writes_job_run_completed(
        self, real_db: Path, backup_dir: Path, db: AsyncSession
    ) -> None:
        """成功备份写入 job_runs status=completed。"""
        svc = BackupService(db)
        await svc.run_backup(db_path=str(real_db), backup_dir=str(backup_dir))
        await db.flush()

        result = await db.execute(
            select(JobRun).where(JobRun.job_type == "backup")
        )
        job = result.scalar_one()
        assert job.status == "completed"

    async def test_backup_writes_job_run_failed(
        self, backup_dir: Path, db: AsyncSession
    ) -> None:
        """备份失败写入 job_runs status=failed。"""
        svc = BackupService(db)
        result = await svc.run_backup(
            db_path="/nonexistent/path.db", backup_dir=str(backup_dir)
        )

        assert result.success is False
        await db.flush()
        row = await db.execute(
            select(JobRun).where(JobRun.job_type == "backup")
        )
        job = row.scalar_one()
        assert job.status == "failed"
        assert job.error_message is not None


class TestCleanup:
    """清理功能测试。"""

    async def test_cleanup_removes_old_backups(
        self, backup_dir: Path, db: AsyncSession
    ) -> None:
        """清理 31 天前的备份文件。"""
        import os
        import time

        old_file = backup_dir / "zhixi_20260101_060000.db"
        old_file.touch()
        old_ts = (datetime.now(UTC) - timedelta(days=31)).timestamp()
        os.utime(str(old_file), (old_ts, old_ts))

        recent_file = backup_dir / "zhixi_20260318_060000.db"
        recent_file.touch()

        svc = BackupService(db)
        await svc.run_cleanup(
            backup_dir=str(backup_dir), logs_dir=str(backup_dir)
        )

        assert not old_file.exists()
        assert recent_file.exists()

    async def test_cleanup_keeps_recent_backups(
        self, backup_dir: Path, db: AsyncSession
    ) -> None:
        """保留 30 天内的备份文件。"""
        for i in range(5):
            f = backup_dir / f"zhixi_2026031{i}_060000.db"
            f.touch()

        svc = BackupService(db)
        await svc.run_cleanup(
            backup_dir=str(backup_dir), logs_dir=str(backup_dir)
        )

        assert len(list(backup_dir.glob("zhixi_*.db"))) == 5

    async def test_cleanup_removes_old_logs(
        self, backup_dir: Path, logs_dir: Path, db: AsyncSession
    ) -> None:
        """清理过期日志文件。"""
        import os

        old_log = logs_dir / "app_20260101.log"
        old_log.touch()
        old_ts = (datetime.now(UTC) - timedelta(days=31)).timestamp()
        os.utime(str(old_log), (old_ts, old_ts))

        recent_log = logs_dir / "app_20260318.log"
        recent_log.touch()

        svc = BackupService(db)
        await svc.run_cleanup(
            backup_dir=str(backup_dir), logs_dir=str(logs_dir)
        )

        assert not old_log.exists()
        assert recent_log.exists()
```

- [ ] **Step 1.2: 运行测试验证失败**

Run: `uv run pytest tests/test_backup.py -v`
Expected: FAIL — `BackupService` 方法未实现

### Step 2: 实现 BackupService

- [ ] **Step 2.1: 编写 BackupService**

```python
# app/services/backup_service.py
"""备份服务 — sqlite3 backup API + 过期文件清理。"""

import logging
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job_run import JobRun

logger = logging.getLogger(__name__)

RETENTION_DAYS = 30


class BackupResult(BaseModel):
    """备份操作结果。"""

    success: bool
    file_path: str = ""
    error: str = ""


class BackupService:
    """数据库备份与过期文件清理。"""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def run_backup(
        self,
        db_path: str = "data/zhixi.db",
        backup_dir: str = "data/backups",
    ) -> BackupResult:
        """执行 SQLite 在线备份。使用 sqlite3 官方 backup API，WAL 模式下不阻塞 Web 服务。

        注意：sqlite3.connect/backup 是阻塞调用，在 async 函数中直接执行。
        MVP 可接受：备份仅通过 CLI 调用（非 Web 请求），且 SQLite 备份通常极快。
        """
        now = datetime.now(UTC)
        job = JobRun(
            job_type="backup",
            trigger_source="manual",
            status="running",
            started_at=now,
        )
        self._db.add(job)
        await self._db.flush()

        Path(backup_dir).mkdir(parents=True, exist_ok=True)
        timestamp = now.strftime("%Y%m%d_%H%M%S")
        dest_path = os.path.join(backup_dir, f"zhixi_{timestamp}.db")

        try:
            source = sqlite3.connect(db_path)
            target = sqlite3.connect(dest_path)
            source.backup(target)
            source.close()
            target.close()

            job.status = "completed"
            job.finished_at = datetime.now(UTC)
            logger.info("Backup completed: %s", dest_path)
            return BackupResult(success=True, file_path=dest_path)

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.finished_at = datetime.now(UTC)
            logger.error("Backup failed: %s", e)
            return BackupResult(success=False, error=str(e))

    async def run_cleanup(
        self,
        backup_dir: str = "data/backups",
        logs_dir: str = "data/logs",
    ) -> int:
        """清理超过 RETENTION_DAYS 天的备份文件和日志文件。返回删除文件数。"""
        cutoff = datetime.now(UTC) - timedelta(days=RETENTION_DAYS)
        cutoff_ts = cutoff.timestamp()
        removed = 0

        for directory in [backup_dir, logs_dir]:
            dir_path = Path(directory)
            if not dir_path.exists():
                continue
            for f in dir_path.iterdir():
                if not f.is_file():
                    continue
                if f.name.startswith("."):
                    continue
                if f.stat().st_mtime < cutoff_ts:
                    f.unlink()
                    logger.info("Removed expired file: %s", f)
                    removed += 1

        logger.info("Cleanup complete: removed %d files", removed)
        return removed
```

- [ ] **Step 2.2: 运行测试验证通过**

Run: `uv run pytest tests/test_backup.py -v`
Expected: ALL PASS

### Step 3: 实现 CLI 子命令

- [ ] **Step 3.1: 更新 cli.py 的 backup 和 cleanup 命令**

```python
# app/cli.py — 更新 _run_backup() 和 _run_cleanup()

async def _run_backup() -> None:
    """执行数据库备份。"""
    from app.database import async_session_factory
    from app.services.backup_service import BackupService

    async with async_session_factory() as db:
        try:
            svc = BackupService(db)
            result = await svc.run_backup()
            await db.commit()
            if result.success:
                typer.echo(f"Backup completed: {result.file_path}")
            else:
                typer.echo(f"Backup failed: {result.error}", err=True)
                raise typer.Exit(code=1)
        except Exception:
            await db.rollback()
            raise


async def _run_cleanup() -> None:
    """清理过期备份和日志文件。"""
    from app.services.backup_service import BackupService
    from app.database import async_session_factory

    async with async_session_factory() as db:
        try:
            svc = BackupService(db)
            removed = await svc.run_cleanup()
            await db.commit()
            typer.echo(f"Cleanup completed: removed {removed} files")
        except Exception:
            await db.rollback()
            raise
```

- [ ] **Step 3.2: 运行 lint + 类型检查**

Run: `uv run ruff check app/services/backup_service.py app/cli.py tests/test_backup.py && uv run pyright app/services/backup_service.py`

- [ ] **Step 3.3: 运行全部测试**

Run: `uv run pytest tests/test_backup.py -v`
Expected: ALL PASS

- [ ] **Step 3.4: 提交**

```bash
git add app/services/backup_service.py app/cli.py tests/test_backup.py
git commit -m "feat(infra): US-003+053 SQLite 备份/清理服务及测试"
```

---

## Task 4: US-006 — 定时任务调度

**Files:**
- Create: `crontab`

### Step 1: 创建 crontab 文件

- [ ] **Step 1.1: 编写 crontab**

```cron
# 智曦定时任务调度（supercronic 执行）
# 所有时间为 UTC，注释标注对应北京时间

# UTC 20:00 = 北京 04:00 — 清理过期备份和日志
0 20 * * * cd /app && python -m app.cli cleanup >> /app/data/logs/cron.log 2>&1

# UTC 21:00 = 北京 05:00 — 数据库备份
0 21 * * * cd /app && python -m app.cli backup >> /app/data/logs/cron.log 2>&1

# UTC 22:00 = 北京 06:00 — 每日主流程（抓取 → AI 加工 → 草稿生成）
0 22 * * * cd /app && python -m app.cli pipeline >> /app/data/logs/cron.log 2>&1
```

- [ ] **Step 1.2: 验证 crontab 格式**

Run: `cat crontab` — 确认 3 条调度规则存在，时间正确

- [ ] **Step 1.3: 运行 lint**

Run: `uv run ruff check app/cli.py`

- [ ] **Step 1.4: 提交**

```bash
git add crontab
git commit -m "feat(infra): US-006 定时任务调度 crontab 配置"
```

---

## Task 5: 质量门禁 + 全量测试

- [ ] **Step 5.1: 运行全部测试**

Run: `uv run pytest -v`
Expected: ALL PASS

- [ ] **Step 5.2: 运行 lint + 类型检查 + 模块边界**

Run: `uv run ruff check . && uv run ruff format --check . && uv run lint-imports && uv run pyright`
Expected: ALL PASS

- [ ] **Step 5.3: 最终提交（如有修复）**

---

## 执行结果

### 交付物清单
- [x] `app/fetcher/tweet_classifier.py` — classify_tweet 纯函数（US-012）
- [x] `tests/test_tweet_classifier.py` — 12 个测试用例（US-047，超出最低要求 10 个）
- [x] `app/fetcher/base.py` — BaseFetcher ABC（US-011）
- [x] `app/fetcher/x_api.py` — XApiFetcher 实现，httpx + 分页 + 解析（US-011）
- [x] `app/fetcher/third_party.py` — ThirdPartyFetcher 空壳（US-011）
- [x] `app/fetcher/__init__.py` — get_fetcher() 工厂函数（US-011）
- [x] `tests/test_fetcher.py` — 8 个测试用例（US-011）
- [x] `app/services/backup_service.py` — BackupService（US-003）
- [x] `app/cli.py` — _run_backup/_run_cleanup 实现（US-003）
- [x] `tests/test_backup.py` — 7 个测试用例（US-053）
- [x] `crontab` — 3 条调度规则（US-006）

### 与计划的偏离项
- 子代理在 US-012 测试中增加了 2 个额外边界用例（12 个 vs 计划 10 个），提升了覆盖率
- US-011 测试结构为函数级而非类级组织，功能等价

### 遇到的问题与修复
- 无阻塞问题

### 质量门禁结果
- pytest: 51 passed (0.42s)
- ruff check: All checks passed
- ruff format: 80 files formatted
- lint-imports: 4 contracts KEPT, 0 broken
- pyright: 0 errors, 0 warnings

### PR 链接
- 待推送后创建
