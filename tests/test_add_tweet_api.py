"""US-016: 手动补录推文 — API 集成测试。"""

from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import create_jwt
from app.database import get_db
from app.main import app
from app.models.account import TwitterAccount
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse
from app.schemas.fetcher_types import PublicMetrics, RawTweet
from app.services.fetch_service import _parse_tweet_url
from tests.factories import (
    create_account,
    create_digest,
    create_digest_item,
    create_tweet,
    seed_config_keys,
)

DIGEST_DATE = date(2026, 3, 21)
TWEET_URL = "https://x.com/testuser/status/999888777"
TWEET_ID = "999888777"


# ──────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────


def _mock_raw_tweet() -> RawTweet:
    """构造 mock X API 返回的 RawTweet。"""
    return RawTweet(
        tweet_id=TWEET_ID,
        author_id="uid_test",
        text="Exciting new AI model released today!",
        created_at=datetime(2026, 3, 21, 2, 0, 0, tzinfo=UTC),
        public_metrics=PublicMetrics(like_count=100, retweet_count=20, reply_count=10),
        referenced_tweets=[],
        media_urls=[],
        tweet_url=f"https://x.com/uid_test/status/{TWEET_ID}",
    )


def _mock_claude_response() -> ClaudeResponse:
    """构造 mock Claude API 响应。"""
    return ClaudeResponse(
        content='{"title": "AI重大突破", "translation": "今日发布了令人激动的AI新模型", "comment": "值得关注的技术进展"}',
        input_tokens=500,
        output_tokens=200,
        model="claude-sonnet-4-20250514",
        duration_ms=1500,
        estimated_cost=0.005,
    )


async def _seed_environment(db: AsyncSession) -> tuple[TwitterAccount, DailyDigest, list[Tweet]]:
    """预置完整测试环境：config + account + tweets(已处理) + digest + items。"""
    await seed_config_keys(
        db,
        top_n="10",
        min_articles="1",
        push_time="08:00",
        push_days="1,2,3,4,5,6,7",
        display_mode="simple",
        publish_mode="manual",
    )

    account = await create_account(
        db,
        twitter_handle="testuser",
        twitter_user_id="uid_test",
        display_name="Test User",
        weight=2.0,
    )

    tweet_time = datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC)
    tweets: list[Tweet] = []
    for i, (base_score, hs) in enumerate([(10.0, 40.0), (50.0, 60.0), (100.0, 85.0)], start=1):
        t = await create_tweet(
            db,
            account,
            tweet_id=f"{100000 + i}",
            text=f"Existing tweet {i}",
            digest_date=DIGEST_DATE,
            tweet_time=tweet_time,
            likes=50,
            retweets=10,
            replies=5,
            is_processed=True,
            title=f"标题{i}",
            translated_text=f"翻译{i}",
            ai_comment=f"点评{i}",
            base_heat_score=base_score,
            ai_importance_score=70.0,
            heat_score=hs,
        )
        tweets.append(t)

    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        item_count=3,
        summary="今日AI摘要",
        content_markdown="# 测试",
    )

    for i, t in enumerate(tweets, start=1):
        await create_digest_item(
            db,
            digest,
            item_ref_id=t.id,
            display_order=i,
            snapshot_title=t.title,
            snapshot_translation=t.translated_text,
            snapshot_comment=t.ai_comment,
            snapshot_heat_score=t.heat_score or 0,
            snapshot_author_name=account.display_name,
            snapshot_author_handle=account.twitter_handle,
            snapshot_tweet_url=t.tweet_url,
            snapshot_tweet_time=t.tweet_time,
        )

    return account, digest, tweets


# ──────────────────────────────────────────────────
# 辅助：构造带认证的客户端
# ──────────────────────────────────────────────────


def _make_mock_fetcher(raw_tweet: RawTweet | None = None, error: Exception | None = None):
    """构造 mock XApiFetcher（支持 async with 上下文管理器）。"""
    mock = AsyncMock()
    if error:
        mock.fetch_single_tweet = AsyncMock(side_effect=error)
    else:
        mock.fetch_single_tweet = AsyncMock(return_value=raw_tweet or _mock_raw_tweet())
    mock.close = AsyncMock()
    # 支持 async with 用法
    mock.__aenter__ = AsyncMock(return_value=mock)
    mock.__aexit__ = AsyncMock(return_value=False)
    return mock


def _make_mock_claude(success: bool = True):
    """构造 mock ClaudeClient。"""
    mock = AsyncMock()
    if success:
        mock.complete = AsyncMock(return_value=_mock_claude_response())
    else:
        from app.clients.claude_client import ClaudeAPIError

        mock.complete = AsyncMock(side_effect=ClaudeAPIError("Claude API 错误"))
    return mock


# ──────────────────────────────────────────────────
# 单元测试: URL 解析
# ──────────────────────────────────────────────────


class TestParseTweetUrl:
    """_parse_tweet_url 单元测试。"""

    def test_x_com_url(self):
        result = _parse_tweet_url("https://x.com/elonmusk/status/123456")
        assert result == ("elonmusk", "123456")

    def test_twitter_com_url(self):
        result = _parse_tweet_url("https://twitter.com/elonmusk/status/789012")
        assert result == ("elonmusk", "789012")

    def test_with_query_params(self):
        result = _parse_tweet_url("https://x.com/user/status/111?s=20&t=abc")
        assert result == ("user", "111")

    def test_invalid_url_no_status(self):
        assert _parse_tweet_url("https://x.com/elonmusk") is None

    def test_invalid_url_random(self):
        assert _parse_tweet_url("not a url") is None

    def test_with_trailing_whitespace(self):
        result = _parse_tweet_url("  https://x.com/user/status/555  ")
        assert result == ("user", "555")


# ──────────────────────────────────────────────────
# API 集成测试
# ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestAddTweetApi:
    """POST /api/digest/add-tweet 集成测试。"""

    async def test_success_full_flow(self, db: AsyncSession):
        """T1: 正常补录完整链路。"""
        account, digest, existing_tweets = await _seed_environment(db)

        mock_fetcher = _make_mock_fetcher()
        mock_claude = _make_mock_claude()

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client", AsyncMock(return_value=mock_claude)
            ),
            patch("app.services.fetch_service.get_fetcher", return_value=mock_fetcher),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.fetch_service.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": TWEET_URL})

        app.dependency_overrides.clear()

        assert resp.status_code == 200
        data = resp.json()
        assert data["message"] == "补录成功"
        assert data["item"]["snapshot_title"] == "AI重大突破"
        assert data["item"]["display_order"] == 4  # max(3) + 1

        # 验证 DB 状态
        tweet_result = await db.execute(select(Tweet).where(Tweet.tweet_id == TWEET_ID))
        tweet = tweet_result.scalar_one()
        assert tweet.source == "manual"
        assert tweet.is_ai_relevant is True
        assert tweet.is_processed is True
        assert tweet.ai_importance_score == 50.0
        assert tweet.title == "AI重大突破"

        # 验证 digest item_count
        digest_result = await db.execute(select(DailyDigest).where(DailyDigest.id == digest.id))
        updated_digest = digest_result.scalar_one()
        assert updated_digest.item_count == 4

    async def test_invalid_url(self, db: AsyncSession):
        """T2: URL 格式无效 → 400。"""
        await _seed_environment(db)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client",
                AsyncMock(return_value=_make_mock_claude()),
            ),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": "not-a-valid-url"})

        app.dependency_overrides.clear()
        assert resp.status_code == 400
        assert "无效的推文URL" in resp.json()["detail"]

    async def test_tweet_already_exists(self, db: AsyncSession):
        """T3: tweet_id 已存在 → 409。"""
        account, digest, existing_tweets = await _seed_environment(db)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        # URL 对应的 tweet_id 已在数据库中（100001）
        existing_url = f"https://x.com/testuser/status/{existing_tweets[0].tweet_id}"  # "100001"

        mock_fetcher = _make_mock_fetcher()

        with (
            patch(
                "app.clients.claude_client.get_claude_client",
                AsyncMock(return_value=_make_mock_claude()),
            ),
            patch("app.services.fetch_service.get_fetcher", return_value=mock_fetcher),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.fetch_service.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": existing_url})

        app.dependency_overrides.clear()
        assert resp.status_code == 409
        assert "该推文已存在" in resp.json()["detail"]

    async def test_no_draft(self, db: AsyncSession):
        """T4: 当日无草稿 → 409。"""
        # 只创建 config，不创建 digest
        await seed_config_keys(db, top_n="10", min_articles="1")

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client",
                AsyncMock(return_value=_make_mock_claude()),
            ),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": TWEET_URL})

        app.dependency_overrides.clear()
        assert resp.status_code == 409
        assert "今日草稿尚未生成" in resp.json()["detail"]

    async def test_draft_published(self, db: AsyncSession):
        """T5: 草稿已发布 → 409。"""
        await seed_config_keys(db, top_n="10")
        await create_digest(db, digest_date=DIGEST_DATE, status="published", item_count=0)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client",
                AsyncMock(return_value=_make_mock_claude()),
            ),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": TWEET_URL})

        app.dependency_overrides.clear()
        assert resp.status_code == 409
        assert "当前版本不可编辑" in resp.json()["detail"]

    async def test_x_api_failure(self, db: AsyncSession):
        """T6: X API 抓取失败 → 502。"""
        await _seed_environment(db)

        mock_fetcher = _make_mock_fetcher(error=httpx.HTTPError("X API down"))

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client",
                AsyncMock(return_value=_make_mock_claude()),
            ),
            patch("app.services.fetch_service.get_fetcher", return_value=mock_fetcher),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.fetch_service.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": TWEET_URL})

        app.dependency_overrides.clear()
        assert resp.status_code == 502
        assert "推文抓取失败" in resp.json()["detail"]

    async def test_ai_processing_failure(self, db: AsyncSession):
        """T7: AI 加工失败 → 502, 推文保留但无 DigestItem。"""
        await _seed_environment(db)

        mock_fetcher = _make_mock_fetcher()
        mock_claude = _make_mock_claude(success=False)

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client", AsyncMock(return_value=mock_claude)
            ),
            patch("app.services.fetch_service.get_fetcher", return_value=mock_fetcher),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.fetch_service.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post("/api/digest/add-tweet", json={"tweet_url": TWEET_URL})

        app.dependency_overrides.clear()
        assert resp.status_code == 502
        assert "推文已入库但AI加工失败" in resp.json()["detail"]

        # 推文应已入库（is_processed=False）
        tweet_result = await db.execute(select(Tweet).where(Tweet.tweet_id == TWEET_ID))
        tweet = tweet_result.scalar_one()
        assert tweet.source == "manual"
        assert tweet.is_processed is False

        # 不应有新的 DigestItem
        items_result = await db.execute(select(DigestItem))
        items = items_result.scalars().all()
        assert len(items) == 3  # 只有预置的 3 条

    async def test_unauthenticated(self, db: AsyncSession):
        """T13: 未认证 → 401。"""

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            resp = await c.post("/api/digest/add-tweet", json={"tweet_url": TWEET_URL})

        app.dependency_overrides.clear()
        assert resp.status_code == 401

    async def test_unknown_author_creates_temp_account(self, db: AsyncSession):
        """T11: 推文作者不在大V列表 → 创建临时账号。"""
        # 只创建环境，不创建 testuser 账号——让系统自动创建
        await seed_config_keys(
            db, top_n="10", min_articles="1", display_mode="simple", publish_mode="manual"
        )
        await create_digest(db, digest_date=DIGEST_DATE, item_count=0, content_markdown="")

        # 用一个不存在的 author
        raw = RawTweet(
            tweet_id="777777",
            author_id="uid_unknown",
            text="Unknown author tweet",
            created_at=datetime(2026, 3, 21, 2, 0, 0, tzinfo=UTC),
            public_metrics=PublicMetrics(like_count=10, retweet_count=2, reply_count=1),
            referenced_tweets=[],
            media_urls=[],
            tweet_url="https://x.com/uid_unknown/status/777777",
        )
        mock_fetcher = _make_mock_fetcher(raw_tweet=raw)
        mock_claude = _make_mock_claude()

        async def override_get_db():
            yield db

        app.dependency_overrides[get_db] = override_get_db
        token, _ = create_jwt("admin")
        headers = {"Authorization": f"Bearer {token}"}

        with (
            patch(
                "app.clients.claude_client.get_claude_client", AsyncMock(return_value=mock_claude)
            ),
            patch("app.services.fetch_service.get_fetcher", return_value=mock_fetcher),
            patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.fetch_service.get_today_digest_date", return_value=DIGEST_DATE),
            patch("app.services.digest_service.get_today_digest_date", return_value=DIGEST_DATE),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", headers=headers
            ) as c:
                resp = await c.post(
                    "/api/digest/add-tweet",
                    json={"tweet_url": "https://x.com/unknownuser/status/777777"},
                )

        app.dependency_overrides.clear()
        assert resp.status_code == 200

        # 验证创建了临时账号
        acct_result = await db.execute(
            select(TwitterAccount).where(TwitterAccount.twitter_handle == "unknownuser")
        )
        acct = acct_result.scalar_one()
        assert acct.is_active is False
        assert acct.weight == 1.0


# ──────────────────────────────────────────────────
# 热度计算边界测试
# ──────────────────────────────────────────────────


@pytest.mark.asyncio
class TestManualHeatCalculation:
    """手动补录推文的热度计算边界情况。"""

    async def test_normalize_with_few_existing(self, db: AsyncSession):
        """T8: 已有推文不足 2 条 → normalized=50。"""
        from app.services.digest_service import DigestService

        await seed_config_keys(db, top_n="10")

        account = await create_account(
            db,
            twitter_handle="user1",
            display_name="User 1",
        )

        # 只有 1 条已处理推文
        await create_tweet(
            db,
            account,
            tweet_id="only_one",
            text="Only one",
            digest_date=DIGEST_DATE,
            tweet_time=datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC),
            likes=50,
            retweets=10,
            replies=5,
            is_processed=True,
            base_heat_score=50.0,
            heat_score=50.0,
        )

        # 构造新推文（不入库，只测计算）
        new_tweet = Tweet(
            tweet_id="manual_1",
            account_id=account.id,
            digest_date=DIGEST_DATE,
            original_text="Manual tweet",
            tweet_time=datetime(2026, 3, 21, 2, 0, 0, tzinfo=UTC),
            likes=100,
            retweets=20,
            replies=10,
            source="manual",
        )

        svc = DigestService(db, claude_client=AsyncMock())
        await svc._calculate_manual_heat(new_tweet, account, DIGEST_DATE)

        # 不足 2 条已有推文 → normalized=50
        from app.processor.heat_calculator import calculate_heat_score

        expected = calculate_heat_score(50.0, 50.0)
        assert new_tweet.heat_score == expected
        assert new_tweet.ai_importance_score == 50.0

    async def test_normalize_clamp_high(self, db: AsyncSession):
        """T9: base_score > max → normalized 截断为 100。"""
        from app.services.digest_service import DigestService

        account = await create_account(
            db,
            twitter_handle="user2",
            display_name="User 2",
        )

        # 2 条已有推文，base_heat_score 范围 [10, 50]
        for i, bs in enumerate([10.0, 50.0], start=1):
            await create_tweet(
                db,
                account,
                tweet_id=f"clamp_h_{i}",
                text=f"Tweet {i}",
                digest_date=DIGEST_DATE,
                tweet_time=datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC),
                likes=10,
                retweets=2,
                replies=1,
                is_processed=True,
                base_heat_score=bs,
                heat_score=50.0,
            )

        # 新推文 base_score 远超 max=50（用超高互动量）
        new_tweet = Tweet(
            tweet_id="manual_high",
            account_id=account.id,
            digest_date=DIGEST_DATE,
            original_text="Very popular",
            tweet_time=datetime(2026, 3, 21, 5, 0, 0, tzinfo=UTC),
            likes=10000,
            retweets=5000,
            replies=2000,
            source="manual",
        )

        svc = DigestService(db, claude_client=AsyncMock())
        await svc._calculate_manual_heat(new_tweet, account, DIGEST_DATE)

        # normalized 应被截断为 100
        from app.processor.heat_calculator import calculate_heat_score

        expected = calculate_heat_score(100.0, 50.0)
        assert new_tweet.heat_score == expected

    async def test_normalize_clamp_low(self, db: AsyncSession):
        """T10: base_score < min → normalized 截断为 0。"""
        from app.services.digest_service import DigestService

        account = await create_account(
            db,
            twitter_handle="user3",
            display_name="User 3",
        )

        # 2 条已有推文，base_heat_score 范围 [100, 500]
        for i, bs in enumerate([100.0, 500.0], start=1):
            await create_tweet(
                db,
                account,
                tweet_id=f"clamp_l_{i}",
                text=f"Tweet {i}",
                digest_date=DIGEST_DATE,
                tweet_time=datetime(2026, 3, 20, 10, 0, 0, tzinfo=UTC),
                likes=10,
                retweets=2,
                replies=1,
                is_processed=True,
                base_heat_score=bs,
                heat_score=50.0,
            )

        # 新推文 base_score 低于 min=100（几乎没有互动 + 时间衰减大）
        new_tweet = Tweet(
            tweet_id="manual_low",
            account_id=account.id,
            digest_date=DIGEST_DATE,
            original_text="Unpopular",
            tweet_time=datetime(2026, 3, 19, 0, 0, 0, tzinfo=UTC),  # 很早的推文
            likes=1,
            retweets=0,
            replies=0,
            source="manual",
        )

        svc = DigestService(db, claude_client=AsyncMock())
        await svc._calculate_manual_heat(new_tweet, account, DIGEST_DATE)

        # base_score 应远低于 100 → normalized 截断为 0
        from app.processor.heat_calculator import calculate_heat_score

        expected = calculate_heat_score(0.0, 50.0)
        assert new_tweet.heat_score == expected
