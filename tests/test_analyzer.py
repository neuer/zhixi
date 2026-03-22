"""全局分析器测试（US-019）。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from app.clients.claude_client import ClaudeClient
from app.models.account import TwitterAccount
from app.models.tweet import Tweet
from app.processor.analyzer import run_global_analysis
from app.processor.analyzer_prompts import (
    serialize_tweets_for_analysis,
)
from app.processor.json_validator import JsonValidationError
from app.schemas.client_types import ClaudeResponse

# ──────────────────────────────────────────────────
# 测试辅助
# ──────────────────────────────────────────────────

# I-28: 使用绝对路径，避免对 cwd 的隐式依赖
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "analyzer" / "global_analysis_response.json"


def _load_fixture() -> str:
    with open(FIXTURE_PATH) as f:
        return f.read()


def _make_tweet(
    tweet_id: str = "t1",
    account_id: int = 1,
    text: str = "AI is changing the world",
    tweet_time: datetime | None = None,
    likes: int = 100,
    retweets: int = 20,
    replies: int = 10,
    is_quote: bool = False,
    quoted_text: str | None = None,
    is_self_reply: bool = False,
    tweet_url: str = "https://x.com/test/status/123",
) -> Tweet:
    return Tweet(
        tweet_id=tweet_id,
        account_id=account_id,
        original_text=text,
        tweet_time=tweet_time or datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        likes=likes,
        retweets=retweets,
        replies=replies,
        is_quote_tweet=is_quote,
        quoted_text=quoted_text,
        is_self_thread_reply=is_self_reply,
        tweet_url=tweet_url,
    )


def _make_account(
    account_id: int = 1,
    handle: str = "testuser",
    display_name: str = "Test User",
    bio: str = "AI researcher",
) -> TwitterAccount:
    account = TwitterAccount(
        twitter_handle=handle,
        display_name=display_name,
        bio=bio,
    )
    account.id = account_id
    return account


def _mock_claude_response(content: str) -> ClaudeResponse:
    return ClaudeResponse(
        content=content,
        input_tokens=1000,
        output_tokens=500,
        model="claude-sonnet-4-20250514",
        duration_ms=2000,
        estimated_cost=0.0105,
    )


def _mock_client(response_text: str) -> AsyncMock:
    client = AsyncMock(spec=ClaudeClient)
    client.complete = AsyncMock(
        return_value=_mock_claude_response(response_text),
    )
    return client


# ──────────────────────────────────────────────────
# 序列化测试
# ──────────────────────────────────────────────────


class TestSerializeTweets:
    """推文序列化为 R.1.1b 格式。"""

    def test_basic_serialization(self):
        """序列化包含所有 R.1.1b 字段。"""
        tweet = _make_tweet(tweet_id="abc123")
        account = _make_account()
        accounts_map = {1: account}

        result = serialize_tweets_for_analysis([tweet], accounts_map)

        assert len(result) == 1
        item = result[0]
        assert item["id"] == "abc123"
        assert item["author"] == "Test User"
        assert item["handle"] == "testuser"
        assert item["bio"] == "AI researcher"
        assert item["text"] == "AI is changing the world"
        assert item["likes"] == 100
        assert item["retweets"] == 20
        assert item["replies"] == 10
        assert item["url"] == "https://x.com/test/status/123"
        assert item["is_quote"] is False
        assert item["quoted_text"] is None
        assert item["is_self_reply"] is False

    def test_descending_order_by_tweet_time(self):
        """推文按 tweet_time 降序排列。"""
        t1 = _make_tweet(
            tweet_id="old",
            tweet_time=datetime(2026, 3, 19, 8, 0, 0, tzinfo=UTC),
        )
        t2 = _make_tweet(
            tweet_id="new",
            tweet_time=datetime(2026, 3, 19, 12, 0, 0, tzinfo=UTC),
        )
        accounts_map = {1: _make_account()}

        result = serialize_tweets_for_analysis([t1, t2], accounts_map)

        assert result[0]["id"] == "new"
        assert result[1]["id"] == "old"

    def test_quote_tweet_fields(self):
        """quote tweet 正确序列化 is_quote 和 quoted_text。"""
        tweet = _make_tweet(
            is_quote=True,
            quoted_text="Original tweet being quoted",
        )
        accounts_map = {1: _make_account()}

        result = serialize_tweets_for_analysis([tweet], accounts_map)

        assert result[0]["is_quote"] is True
        assert result[0]["quoted_text"] == "Original tweet being quoted"

    def test_missing_account_uses_empty_strings(self):
        """找不到对应 account 时用空字符串。"""
        tweet = _make_tweet(account_id=999)
        accounts_map: dict[int, TwitterAccount] = {}

        result = serialize_tweets_for_analysis([tweet], accounts_map)

        assert result[0]["author"] == ""
        assert result[0]["handle"] == ""
        assert result[0]["bio"] == ""

    def test_time_format_iso8601(self):
        """时间格式为 ISO 8601 UTC。"""
        tweet = _make_tweet(
            tweet_time=datetime(2026, 3, 19, 14, 30, 0, tzinfo=UTC),
        )
        accounts_map = {1: _make_account()}

        result = serialize_tweets_for_analysis([tweet], accounts_map)

        assert result[0]["time"] == "2026-03-19T14:30:00Z"


# ──────────────────────────────────────────────────
# 全局分析测试
# ──────────────────────────────────────────────────


class TestRunGlobalAnalysis:
    """run_global_analysis() 调用与解析。"""

    async def test_normal_analysis_returns_result(self):
        """正常分析返回 AnalysisResult + ClaudeResponse。"""
        fixture = _load_fixture()
        client = _mock_client(fixture)

        analysis, response = await run_global_analysis(client, "[mock tweets]")

        assert analysis.filtered_count == 1
        assert len(analysis.filtered_ids) == 1
        assert analysis.filtered_ids[0] == "tweet_filtered_1"
        assert len(analysis.topics) == 3
        assert response.input_tokens == 1000

    async def test_aggregated_topic_parsed(self):
        """正确解析 aggregated 类型话题。"""
        fixture = _load_fixture()
        client = _mock_client(fixture)

        analysis, _ = await run_global_analysis(client, "[mock tweets]")

        agg = next(t for t in analysis.topics if t.type == "aggregated")
        assert agg.topic_label == "GPT-5 发布"
        assert agg.ai_importance_score == 90
        assert set(agg.tweet_ids) == {"tweet_agg_1", "tweet_agg_2"}

    async def test_thread_topic_has_merged_text(self):
        """thread 类型包含 merged_text。"""
        fixture = _load_fixture()
        client = _mock_client(fixture)

        analysis, _ = await run_global_analysis(client, "[mock tweets]")

        thread = next(t for t in analysis.topics if t.type == "thread")
        assert thread.merged_text is not None
        assert "AI safety" in thread.merged_text
        assert thread.ai_importance_score == 80

    async def test_single_topic_parsed(self):
        """single 类型正确解析。"""
        fixture = _load_fixture()
        client = _mock_client(fixture)

        analysis, _ = await run_global_analysis(client, "[mock tweets]")

        single = next(t for t in analysis.topics if t.type == "single")
        assert single.ai_importance_score == 70
        assert single.tweet_ids == ["tweet_single_1"]
        assert single.merged_text is None

    async def test_prompt_contains_tweets_json(self):
        """prompt 中包含传入的推文 JSON。"""
        fixture = _load_fixture()
        client = _mock_client(fixture)

        await run_global_analysis(client, '{"test": "data"}')

        call_args = client.complete.call_args
        prompt = call_args.kwargs.get("prompt") or call_args[0][0]
        assert '{"test": "data"}' in prompt

    async def test_invalid_json_raises_error(self):
        """AI 返回无效 JSON 抛出 JsonValidationError。"""
        client = _mock_client("this is not json at all !!!")

        with pytest.raises(JsonValidationError):
            await run_global_analysis(client, "[]")

    async def test_markdown_wrapped_json_accepted(self):
        """AI 用 markdown 包裹 JSON 仍可解析。"""
        fixture = _load_fixture()
        wrapped = f"```json\n{fixture}\n```"
        client = _mock_client(wrapped)

        analysis, _ = await run_global_analysis(client, "[]")

        assert len(analysis.topics) == 3

    async def test_empty_topics_returns_empty_list(self):
        """AI 返回空 topics 列表。"""
        content = json.dumps({"filtered_ids": [], "filtered_count": 0, "topics": []})
        client = _mock_client(content)

        analysis, _ = await run_global_analysis(client, "[]")

        assert analysis.topics == []
        assert analysis.filtered_ids == []
