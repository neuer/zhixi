"""ProcessService 集成测试（US-019 + US-020 + US-021）。"""

import json
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeClient
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.topic import Topic
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse
from app.services.process_service import ProcessService

# ──────────────────────────────────────────────────
# 测试辅助
# ──────────────────────────────────────────────────

DIGEST_DATE = date(2026, 3, 19)


def _load_fixture(path: str) -> str:
    with open(path) as f:
        return f.read()


def _mock_claude_response(content: str) -> ClaudeResponse:
    return ClaudeResponse(
        content=content,
        input_tokens=1000,
        output_tokens=500,
        model="claude-sonnet-4-20250514",
        duration_ms=2000,
        estimated_cost=0.0105,
    )


ANALYSIS_FIXTURE = _load_fixture("tests/fixtures/analyzer/global_analysis_response.json")
SINGLE_FIXTURE = _load_fixture("tests/fixtures/translator/single_tweet_response.json")
TOPIC_FIXTURE = _load_fixture("tests/fixtures/translator/topic_response.json")
THREAD_FIXTURE = _load_fixture("tests/fixtures/translator/thread_response.json")


async def _seed_account(db: AsyncSession, **overrides: object) -> TwitterAccount:
    """创建测试账号。"""
    defaults: dict[str, object] = {
        "twitter_handle": "testuser",
        "display_name": "Test User",
        "bio": "AI researcher",
        "weight": 1.0,
        "is_active": True,
    }
    defaults.update(overrides)
    account = TwitterAccount(**defaults)
    db.add(account)
    await db.flush()
    return account


async def _seed_tweet(
    db: AsyncSession,
    account: TwitterAccount,
    tweet_id: str = "t1",
    text: str = "AI tweet",
    tweet_time: datetime | None = None,
    likes: int = 100,
    retweets: int = 20,
    replies: int = 10,
    is_quote: bool = False,
    is_self_reply: bool = False,
) -> Tweet:
    """创建测试推文。"""
    tweet = Tweet(
        tweet_id=tweet_id,
        account_id=account.id,
        digest_date=DIGEST_DATE,
        original_text=text,
        tweet_time=tweet_time or datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        likes=likes,
        retweets=retweets,
        replies=replies,
        is_quote_tweet=is_quote,
        is_self_thread_reply=is_self_reply,
        tweet_url=f"https://x.com/{account.twitter_handle}/status/{tweet_id}",
        source="auto",
    )
    db.add(tweet)
    await db.flush()
    return tweet


def _make_process_service(
    db: AsyncSession,
    analysis_response: str = ANALYSIS_FIXTURE,
    single_response: str = SINGLE_FIXTURE,
    topic_response: str = TOPIC_FIXTURE,
    thread_response: str = THREAD_FIXTURE,
) -> ProcessService:
    """构造 ProcessService，mock ClaudeClient 按顺序返回响应。"""
    client = AsyncMock(spec=ClaudeClient)

    responses = [
        _mock_claude_response(analysis_response),  # 全局分析
        _mock_claude_response(single_response),  # 单条加工
        _mock_claude_response(topic_response),  # 聚合加工
        _mock_claude_response(thread_response),  # Thread 加工
    ]
    client.complete = AsyncMock(side_effect=responses)

    return ProcessService(db, claude_client=client)


# ──────────────────────────────────────────────────
# 测试用例
# ──────────────────────────────────────────────────


class TestProcessServiceZeroTweets:
    """0 条推文边界。"""

    async def test_no_tweets_returns_empty_result(self, db: AsyncSession):
        """无待处理推文返回空结果。"""
        client = AsyncMock(spec=ClaudeClient)
        svc = ProcessService(db, claude_client=client)

        result = await svc.run_daily_process(DIGEST_DATE)

        assert result.processed_count == 0
        assert result.filtered_count == 0
        assert result.topic_count == 0
        assert result.failed_count == 0
        client.complete.assert_not_called()


class TestProcessServiceFullFlow:
    """完整流程测试：过滤 + Topic 创建 + 加工 + 热度。"""

    @pytest_asyncio.fixture
    async def seeded_data(self, db: AsyncSession):
        """预置 6 条推文，匹配 fixture 中的 tweet_id。"""
        account = await _seed_account(db)
        account2 = await _seed_account(
            db,
            twitter_handle="user2",
            display_name="User Two",
            bio="Developer",
        )

        # filtered 推文
        filtered = await _seed_tweet(
            db,
            account,
            tweet_id="tweet_filtered_1",
            text="Just had a great lunch",
            likes=5,
            retweets=0,
            replies=1,
        )

        # single 推文
        single = await _seed_tweet(
            db,
            account,
            tweet_id="tweet_single_1",
            text="New breakthrough in AI reasoning",
            likes=200,
            retweets=50,
            replies=30,
        )

        # aggregated 推文
        agg1 = await _seed_tweet(
            db,
            account,
            tweet_id="tweet_agg_1",
            text="GPT-5 is amazing",
            likes=500,
            retweets=100,
            replies=50,
        )
        agg2 = await _seed_tweet(
            db,
            account2,
            tweet_id="tweet_agg_2",
            text="GPT-5 analysis",
            likes=300,
            retweets=80,
            replies=40,
        )

        # thread 推文
        thread1 = await _seed_tweet(
            db,
            account,
            tweet_id="tweet_thread_1",
            text="Thread part 1",
            likes=150,
            retweets=30,
            replies=20,
            is_self_reply=False,
            tweet_time=datetime(2026, 3, 19, 8, 0, 0, tzinfo=UTC),
        )
        thread2 = await _seed_tweet(
            db,
            account,
            tweet_id="tweet_thread_2",
            text="Thread part 2",
            likes=80,
            retweets=15,
            replies=10,
            is_self_reply=True,
            tweet_time=datetime(2026, 3, 19, 8, 30, 0, tzinfo=UTC),
        )

        await db.commit()
        return {
            "account": account,
            "account2": account2,
            "filtered": filtered,
            "single": single,
            "agg1": agg1,
            "agg2": agg2,
            "thread1": thread1,
            "thread2": thread2,
        }

    async def test_full_flow_counts(self, db: AsyncSession, seeded_data: dict):
        """完整流程返回正确的统计数。"""
        svc = _make_process_service(db)

        result = await svc.run_daily_process(DIGEST_DATE)

        # 1 filtered, 1 single + 1 aggregated + 1 thread = 3 processed items
        assert result.filtered_count == 1
        assert result.topic_count == 2  # aggregated + thread
        assert result.failed_count == 0

    async def test_filtered_tweets_marked(self, db: AsyncSession, seeded_data: dict):
        """被过滤推文标记 is_ai_relevant=false。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_filtered_1")
        filtered = (await db.execute(stmt)).scalar_one()
        assert filtered.is_ai_relevant is False

    async def test_topic_created_for_aggregated(self, db: AsyncSession, seeded_data: dict):
        """aggregated 类型创建 Topic 记录。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(Topic).where(Topic.type == "aggregated")
        topic = (await db.execute(stmt)).scalar_one()
        assert topic.digest_date == DIGEST_DATE
        assert topic.topic_label == "GPT-5 发布"
        assert topic.ai_importance_score == 90

    async def test_topic_created_for_thread(self, db: AsyncSession, seeded_data: dict):
        """thread 类型创建 Topic 记录。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(Topic).where(Topic.type == "thread")
        topic = (await db.execute(stmt)).scalar_one()
        assert topic.digest_date == DIGEST_DATE
        assert topic.ai_importance_score == 80

    async def test_tweets_linked_to_topics(self, db: AsyncSession, seeded_data: dict):
        """推文正确关联到 topic_id。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        # aggregated 推文
        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_agg_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.topic_id is not None

        # thread 推文
        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_thread_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.topic_id is not None

        # single 推文无 topic_id
        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_single_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.topic_id is None

    async def test_ai_importance_score_written(self, db: AsyncSession, seeded_data: dict):
        """ai_importance_score 正确写入。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        # single 推文: 直接取 70
        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_single_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.ai_importance_score == 70

        # aggregated 成员: 取话题分 90
        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_agg_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.ai_importance_score == 90

    async def test_single_tweet_ai_fields_updated(self, db: AsyncSession, seeded_data: dict):
        """单条推文 AI 字段正确更新。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_single_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.title == "OpenAI发布GPT-5模型"
        assert t.translated_text is not None
        assert t.ai_comment is not None
        assert t.is_processed is True

    async def test_aggregated_topic_fields_updated(self, db: AsyncSession, seeded_data: dict):
        """聚合话题 AI 字段正确更新。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(Topic).where(Topic.type == "aggregated")
        topic = (await db.execute(stmt)).scalar_one()
        assert topic.title == "GPT-5引发行业热议"
        assert topic.summary is not None
        assert topic.perspectives is not None
        assert topic.ai_comment is not None

        # perspectives 是 JSON
        perspectives = json.loads(topic.perspectives)
        assert isinstance(perspectives, list)

    async def test_thread_topic_translation_in_summary(self, db: AsyncSession, seeded_data: dict):
        """Thread 翻译写入 topics.summary。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(Topic).where(Topic.type == "thread")
        topic = (await db.execute(stmt)).scalar_one()
        assert topic.title == "Karpathy解读AI安全现状"
        assert topic.summary is not None  # translation → summary
        assert topic.ai_comment is not None

    async def test_heat_scores_calculated(self, db: AsyncSession, seeded_data: dict):
        """热度分正确计算。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        # single 推文有 heat_score > 0
        stmt = select(Tweet).where(Tweet.tweet_id == "tweet_single_1")
        t = (await db.execute(stmt)).scalar_one()
        assert t.base_heat_score > 0
        assert t.heat_score > 0

        # topic 也有 heat_score
        stmt = select(Topic).where(Topic.type == "aggregated")
        topic = (await db.execute(stmt)).scalar_one()
        assert topic.heat_score > 0

    async def test_api_cost_logged(self, db: AsyncSession, seeded_data: dict):
        """API 调用成本正确记录。"""
        svc = _make_process_service(db)
        await svc.run_daily_process(DIGEST_DATE)

        stmt = select(ApiCostLog).where(ApiCostLog.service == "claude")
        logs = (await db.execute(stmt)).scalars().all()

        # 至少 4 条：全局分析 + single + topic + thread
        assert len(logs) >= 4
        call_types = {log.call_type for log in logs}
        assert "global_analysis" in call_types
        assert "single_process" in call_types
        assert "topic_process" in call_types
        assert "thread_process" in call_types


class TestProcessServiceFailures:
    """失败场景。"""

    @pytest_asyncio.fixture
    async def one_tweet(self, db: AsyncSession):
        """预置 1 条推文。"""
        account = await _seed_account(db)
        tweet = await _seed_tweet(db, account, tweet_id="only_tweet")
        await db.commit()
        return tweet

    async def test_analysis_failure_retries_once(self, db: AsyncSession, one_tweet: Tweet):
        """全局分析失败重试 1 次。"""
        from app.clients.claude_client import ClaudeAPIError

        client = AsyncMock(spec=ClaudeClient)
        # 第一次失败，第二次成功
        simple_result = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 50, "tweet_ids": ["only_tweet"]}
                ],
            }
        )
        client.complete = AsyncMock(
            side_effect=[
                ClaudeAPIError("temporary error"),
                _mock_claude_response(simple_result),
                _mock_claude_response(SINGLE_FIXTURE),
            ]
        )

        svc = ProcessService(db, claude_client=client)
        result = await svc.run_daily_process(DIGEST_DATE)

        # 第一次失败 + 第二次成功 = complete 被调用 ≥2 次
        assert client.complete.call_count >= 2
        assert result.processed_count >= 0

    async def test_analysis_failure_twice_raises(self, db: AsyncSession, one_tweet: Tweet):
        """全局分析连续 2 次失败抛出异常。"""
        from app.clients.claude_client import ClaudeAPIError

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(side_effect=ClaudeAPIError("persistent error"))

        svc = ProcessService(db, claude_client=client)

        with pytest.raises(ClaudeAPIError):
            await svc.run_daily_process(DIGEST_DATE)

    async def test_single_process_failure_skips(self, db: AsyncSession, one_tweet: Tweet):
        """单条加工失败跳过，is_processed 保持 false。"""
        from app.clients.claude_client import ClaudeAPIError

        simple_analysis = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 60, "tweet_ids": ["only_tweet"]}
                ],
            }
        )

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(
            side_effect=[
                _mock_claude_response(simple_analysis),  # 全局分析成功
                ClaudeAPIError("fail 1"),  # 单条加工失败
                ClaudeAPIError("fail 2"),  # 重试 1
                ClaudeAPIError("fail 3"),  # 重试 2
            ]
        )

        svc = ProcessService(db, claude_client=client)
        result = await svc.run_daily_process(DIGEST_DATE)

        assert result.failed_count == 1

        stmt = select(Tweet).where(Tweet.tweet_id == "only_tweet")
        tweet = (await db.execute(stmt)).scalar_one()
        assert tweet.is_processed is False


class TestProcessServiceEmptyTopics:
    """AI 返回空 topics。"""

    async def test_empty_topics_all_as_single(self, db: AsyncSession):
        """空 topics 列表 → 所有推文作为 single 处理。"""
        account = await _seed_account(db)
        await _seed_tweet(db, account, tweet_id="solo_tweet")
        await db.commit()

        empty_analysis = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [],
            }
        )

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(
            side_effect=[
                _mock_claude_response(empty_analysis),
                _mock_claude_response(SINGLE_FIXTURE),
            ]
        )

        svc = ProcessService(db, claude_client=client)
        result = await svc.run_daily_process(DIGEST_DATE)

        assert result.topic_count == 0
        # solo_tweet 应被 fallback 为 single 处理
        stmt = select(Tweet).where(Tweet.tweet_id == "solo_tweet")
        tweet = (await db.execute(stmt)).scalar_one()
        assert tweet.is_processed is True


class TestBatchProcessing:
    """分批处理策略（US-020）。"""

    @pytest_asyncio.fixture
    async def two_tweets(self, db: AsyncSession):
        """预置 2 条推文，不同账号。"""
        account1 = await _seed_account(db, twitter_handle="heavy", weight=3.0)
        account2 = await _seed_account(
            db,
            twitter_handle="light",
            display_name="Light User",
            weight=1.0,
        )
        t1 = await _seed_tweet(db, account1, tweet_id="heavy_t1", text="Heavy tweet")
        t2 = await _seed_tweet(db, account2, tweet_id="light_t1", text="Light tweet")
        await db.commit()
        return {"account1": account1, "account2": account2, "t1": t1, "t2": t2}

    async def test_single_batch_no_dedup(
        self,
        db: AsyncSession,
        two_tweets: dict,
    ):
        """单批时 Claude 只调全局分析 + 逐条加工，不调去重。"""
        single_analysis = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 60, "tweet_ids": ["heavy_t1"]},
                    {"type": "single", "ai_importance_score": 50, "tweet_ids": ["light_t1"]},
                ],
            }
        )

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(
            side_effect=[
                _mock_claude_response(single_analysis),  # 全局分析
                _mock_claude_response(SINGLE_FIXTURE),  # heavy_t1 加工
                _mock_claude_response(SINGLE_FIXTURE),  # light_t1 加工
            ]
        )

        # 默认 100K limit 不会触发分批
        svc = ProcessService(db, claude_client=client)
        result = await svc.run_daily_process(DIGEST_DATE)

        # 全局分析 + 2 条 single 加工 = 3 次调用，无去重
        assert client.complete.call_count == 3
        assert result.processed_count == 2

        # 确认没有 dedup_analysis 成本记录
        stmt = select(ApiCostLog).where(ApiCostLog.call_type == "dedup_analysis")
        dedup_logs = (await db.execute(stmt)).scalars().all()
        assert len(dedup_logs) == 0

    async def test_multi_batch_triggers_dedup(self, db: AsyncSession, two_tweets: dict):
        """多批时触发去重 AI 调用。"""
        # 每批各一条推文的分析结果
        batch1_analysis = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 70, "tweet_ids": ["heavy_t1"]},
                ],
            }
        )
        batch2_analysis = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 60, "tweet_ids": ["light_t1"]},
                ],
            }
        )
        dedup_result = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 70, "tweet_ids": ["heavy_t1"]},
                    {"type": "single", "ai_importance_score": 60, "tweet_ids": ["light_t1"]},
                ],
            }
        )

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(
            side_effect=[
                _mock_claude_response(batch1_analysis),  # 第 1 批全局分析
                _mock_claude_response(batch2_analysis),  # 第 2 批全局分析
                _mock_claude_response(dedup_result),  # 去重
                _mock_claude_response(SINGLE_FIXTURE),  # heavy_t1 加工
                _mock_claude_response(SINGLE_FIXTURE),  # light_t1 加工
            ]
        )

        svc = ProcessService(db, claude_client=client)

        # 用极小 token_limit 强制分批
        with patch(
            "app.services.process_service.split_into_batches",
            wraps=None,
        ) as mock_split:
            # 直接返回两个批次
            from app.processor.batch_strategy import split_into_batches as real_split

            mock_split.side_effect = lambda tweets, accts, **kw: real_split(
                tweets,
                accts,
                token_limit=50,
            )

            result = await svc.run_daily_process(DIGEST_DATE)

        # 2 批分析 + 1 去重 + 2 单条加工 = 5 次
        assert client.complete.call_count == 5
        assert result.processed_count == 2

    async def test_dedup_cost_recorded(self, db: AsyncSession, two_tweets: dict):
        """去重 API 调用成本记入 api_cost_log。"""
        batch1 = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 70, "tweet_ids": ["heavy_t1"]}
                ],
            }
        )
        batch2 = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 60, "tweet_ids": ["light_t1"]}
                ],
            }
        )
        dedup = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [
                    {"type": "single", "ai_importance_score": 70, "tweet_ids": ["heavy_t1"]},
                    {"type": "single", "ai_importance_score": 60, "tweet_ids": ["light_t1"]},
                ],
            }
        )

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(
            side_effect=[
                _mock_claude_response(batch1),
                _mock_claude_response(batch2),
                _mock_claude_response(dedup),
                _mock_claude_response(SINGLE_FIXTURE),
                _mock_claude_response(SINGLE_FIXTURE),
            ]
        )

        svc = ProcessService(db, claude_client=client)

        with patch(
            "app.services.process_service.split_into_batches",
        ) as mock_split:
            from app.processor.batch_strategy import split_into_batches as real_split

            mock_split.side_effect = lambda tweets, accts, **kw: real_split(
                tweets,
                accts,
                token_limit=50,
            )
            await svc.run_daily_process(DIGEST_DATE)

        # 确认有 dedup_analysis 成本记录
        stmt = select(ApiCostLog).where(ApiCostLog.call_type == "dedup_analysis")
        dedup_logs = (await db.execute(stmt)).scalars().all()
        assert len(dedup_logs) == 1
        assert dedup_logs[0].success is True
