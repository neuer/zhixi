"""导读摘要生成器测试（US-023）。"""

import json
from unittest.mock import AsyncMock

import pytest

from app.clients.claude_client import ClaudeAPIError, ClaudeClient
from app.digest.summary_generator import generate_summary
from app.digest.summary_prompts import DEFAULT_SUMMARY
from app.models.digest_item import DigestItem
from app.schemas.client_types import ClaudeResponse


def _mock_claude_response(content: str) -> ClaudeResponse:
    """构造模拟 ClaudeResponse。"""
    return ClaudeResponse(
        content=content,
        input_tokens=200,
        output_tokens=80,
        model="claude-sonnet-4-20250514",
        duration_ms=1500,
        estimated_cost=0.0018,
    )


def _make_digest_item(
    *,
    item_type: str = "tweet",
    snapshot_title: str = "测试标题",
    snapshot_heat_score: float = 80.0,
    snapshot_topic_type: str | None = None,
) -> DigestItem:
    """构造测试 DigestItem（仅需 snapshot 字段）。"""
    item = DigestItem(
        digest_id=1,
        item_type=item_type,
        item_ref_id=1,
        display_order=1,
        snapshot_title=snapshot_title,
        snapshot_heat_score=snapshot_heat_score,
        snapshot_topic_type=snapshot_topic_type,
    )
    return item


@pytest.mark.asyncio
async def test_generate_summary_normal() -> None:
    """正常生成摘要。"""
    client = AsyncMock(spec=ClaudeClient)
    summary_text = "今日 AI 领域迎来重大突破，OpenAI 发布 GPT-5！🚀"
    client.complete = AsyncMock(return_value=_mock_claude_response(summary_text))

    items = [
        _make_digest_item(snapshot_title="OpenAI 发布 GPT-5", snapshot_heat_score=95.0),
        _make_digest_item(snapshot_title="谷歌推出 Gemini 2", snapshot_heat_score=85.0),
    ]

    summary, response = await generate_summary(client, items)
    assert summary == summary_text
    assert response is not None
    assert response.content == summary_text
    client.complete.assert_called_once()


@pytest.mark.asyncio
async def test_generate_summary_prompt_format() -> None:
    """验证 Prompt 中 top_articles_json 序列化格式。"""
    client = AsyncMock(spec=ClaudeClient)
    client.complete = AsyncMock(return_value=_mock_claude_response("摘要"))

    items = [
        _make_digest_item(
            item_type="tweet",
            snapshot_title="GPT-5 发布",
            snapshot_heat_score=95.0,
        ),
        _make_digest_item(
            item_type="topic",
            snapshot_title="多家公司讨论 AI 安全",
            snapshot_heat_score=85.0,
            snapshot_topic_type="aggregated",
        ),
        _make_digest_item(
            item_type="topic",
            snapshot_title="Karpathy 长文分析 Transformer",
            snapshot_heat_score=75.0,
            snapshot_topic_type="thread",
        ),
    ]

    await generate_summary(client, items)

    # 验证传入 complete 的 prompt 中包含正确的 JSON 格式
    call_args = client.complete.call_args
    prompt: str = call_args.args[0] if call_args.args else call_args.kwargs["prompt"]

    # 解析 prompt 中的 JSON 部分
    json_start = prompt.index("[")
    json_end = prompt.rindex("]") + 1
    articles = json.loads(prompt[json_start:json_end])

    assert len(articles) == 3
    assert articles[0]["type"] == "tweet"
    assert articles[1]["type"] == "topic_aggregated"
    assert articles[2]["type"] == "topic_thread"
    assert articles[0]["title"] == "GPT-5 发布"
    assert articles[0]["heat_score"] == 95.0


@pytest.mark.asyncio
async def test_generate_summary_claude_api_error_fallback() -> None:
    """Claude API 失败时降级为默认文案。"""
    client = AsyncMock(spec=ClaudeClient)
    client.complete = AsyncMock(side_effect=ClaudeAPIError("API 超时"))

    items = [
        _make_digest_item(snapshot_title="测试", snapshot_heat_score=80.0),
    ]

    summary, response = await generate_summary(client, items)
    assert summary == DEFAULT_SUMMARY
    assert response is None


@pytest.mark.asyncio
async def test_generate_summary_empty_items() -> None:
    """空 items 列表返回默认文案，不调用 Claude。"""
    client = AsyncMock(spec=ClaudeClient)

    summary, response = await generate_summary(client, [])
    assert summary == DEFAULT_SUMMARY
    assert response is None
    client.complete.assert_not_called()
