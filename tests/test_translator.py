"""逐条/逐话题 AI 加工测试（US-021）。"""

from unittest.mock import AsyncMock

import pytest

from app.clients.claude_client import ClaudeClient
from app.processor.json_validator import JsonValidationError
from app.processor.translator import (
    process_aggregated_topic,
    process_single_tweet,
    process_thread,
)
from app.schemas.client_types import ClaudeResponse

# ──────────────────────────────────────────────────
# 测试辅助
# ──────────────────────────────────────────────────

FIXTURE_DIR = "tests/fixtures/translator"


def _load_fixture(name: str) -> str:
    with open(f"{FIXTURE_DIR}/{name}") as f:
        return f.read()


def _mock_claude_response(content: str) -> ClaudeResponse:
    return ClaudeResponse(
        content=content,
        input_tokens=800,
        output_tokens=400,
        model="claude-sonnet-4-20250514",
        duration_ms=1500,
        estimated_cost=0.0084,
    )


def _mock_client(response_text: str) -> AsyncMock:
    client = AsyncMock(spec=ClaudeClient)
    client.complete = AsyncMock(
        return_value=_mock_claude_response(response_text),
    )
    return client


# ──────────────────────────────────────────────────
# 单条推文加工测试
# ──────────────────────────────────────────────────


class TestProcessSingleTweet:
    """单条推文加工（R.1.3）。"""

    async def test_returns_title_translation_comment(self):
        """返回包含 title, translation, comment 的 dict。"""
        fixture = _load_fixture("single_tweet_response.json")
        client = _mock_client(fixture)

        result, response = await process_single_tweet(
            client,
            {
                "author_name": "Sam Altman",
                "author_handle": "sama",
                "author_bio": "CEO of OpenAI",
                "tweet_time": "2026-03-19T10:00:00Z",
                "likes": 5000,
                "retweets": 1200,
                "replies": 300,
                "original_text": "GPT-5 is here.",
            },
        )

        assert "title" in result
        assert "translation" in result
        assert "comment" in result
        assert result["title"] == "OpenAI发布GPT-5模型"
        assert response.input_tokens == 800

    async def test_prompt_contains_author_info(self):
        """prompt 中包含作者信息。"""
        fixture = _load_fixture("single_tweet_response.json")
        client = _mock_client(fixture)

        await process_single_tweet(
            client,
            {
                "author_name": "Karpathy",
                "author_handle": "karpathy",
                "author_bio": "AI researcher",
                "tweet_time": "2026-03-19T10:00:00Z",
                "likes": 100,
                "retweets": 20,
                "replies": 10,
                "original_text": "Test tweet",
            },
        )

        prompt = client.complete.call_args.kwargs.get("prompt") or client.complete.call_args[0][0]
        assert "Karpathy" in prompt
        assert "@karpathy" in prompt
        assert "AI researcher" in prompt

    async def test_invalid_json_raises_error(self):
        """无效 JSON 响应抛出异常。"""
        client = _mock_client("not valid json")

        with pytest.raises(JsonValidationError):
            await process_single_tweet(
                client,
                {
                    "author_name": "X",
                    "author_handle": "x",
                    "author_bio": "",
                    "tweet_time": "",
                    "likes": 0,
                    "retweets": 0,
                    "replies": 0,
                    "original_text": "",
                },
            )


# ──────────────────────────────────────────────────
# 聚合话题加工测试
# ──────────────────────────────────────────────────


class TestProcessAggregatedTopic:
    """聚合话题加工（R.1.4）。"""

    async def test_returns_full_topic_result(self):
        """返回含 title, summary, perspectives, comment 的 dict。"""
        fixture = _load_fixture("topic_response.json")
        client = _mock_client(fixture)

        result, response = await process_aggregated_topic(client, '[{"author":"Sam"}]')

        assert "title" in result
        assert "summary" in result
        assert "perspectives" in result
        assert "comment" in result
        assert isinstance(result["perspectives"], list)
        assert len(result["perspectives"]) == 2
        assert result["perspectives"][0]["author"] == "Sam Altman"

    async def test_prompt_contains_tweets_json(self):
        """prompt 中包含推文 JSON。"""
        fixture = _load_fixture("topic_response.json")
        client = _mock_client(fixture)

        await process_aggregated_topic(client, '[{"author":"test data"}]')

        prompt = client.complete.call_args.kwargs.get("prompt") or client.complete.call_args[0][0]
        assert "test data" in prompt

    async def test_invalid_json_raises_error(self):
        """无效 JSON 响应抛出异常。"""
        client = _mock_client("broken")

        with pytest.raises(JsonValidationError):
            await process_aggregated_topic(client, "[]")


# ──────────────────────────────────────────────────
# Thread 加工测试
# ──────────────────────────────────────────────────


class TestProcessThread:
    """Thread 加工（R.1.5）。"""

    async def test_returns_title_translation_comment(self):
        """返回含 title, translation, comment 的 dict。"""
        fixture = _load_fixture("thread_response.json")
        client = _mock_client(fixture)

        result, response = await process_thread(
            client,
            {
                "author_name": "Andrej Karpathy",
                "author_handle": "karpathy",
                "author_bio": "AI researcher",
                "thread_start_time": "2026-03-19T08:00:00Z",
                "thread_end_time": "2026-03-19T08:30:00Z",
                "tweet_count": 5,
                "total_likes": 3000,
                "total_retweets": 800,
                "total_replies": 200,
                "merged_text": "Thread about AI safety...",
            },
        )

        assert result["title"] == "Karpathy解读AI安全现状"
        assert "translation" in result
        assert "comment" in result
        assert response.duration_ms == 1500

    async def test_prompt_contains_merged_text(self):
        """prompt 中包含 merged_text。"""
        fixture = _load_fixture("thread_response.json")
        client = _mock_client(fixture)

        await process_thread(
            client,
            {
                "author_name": "Test",
                "author_handle": "test",
                "author_bio": "",
                "thread_start_time": "",
                "thread_end_time": "",
                "tweet_count": 2,
                "total_likes": 0,
                "total_retweets": 0,
                "total_replies": 0,
                "merged_text": "UNIQUE_THREAD_CONTENT_FOR_TEST",
            },
        )

        prompt = client.complete.call_args.kwargs.get("prompt") or client.complete.call_args[0][0]
        assert "UNIQUE_THREAD_CONTENT_FOR_TEST" in prompt

    async def test_invalid_json_raises_error(self):
        """无效 JSON 响应抛出异常。"""
        client = _mock_client("{invalid")

        with pytest.raises(JsonValidationError):
            await process_thread(
                client,
                {
                    "author_name": "",
                    "author_handle": "",
                    "author_bio": "",
                    "thread_start_time": "",
                    "thread_end_time": "",
                    "tweet_count": 0,
                    "total_likes": 0,
                    "total_retweets": 0,
                    "total_replies": 0,
                    "merged_text": "",
                },
            )
