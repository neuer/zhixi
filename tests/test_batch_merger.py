"""batch_merger 单元测试（US-020）。"""

import json
from unittest.mock import AsyncMock

import pytest

from app.processor.batch_merger import merge_analysis_results, run_dedup_analysis
from app.schemas.client_types import ClaudeResponse
from app.schemas.processor_types import AnalysisResult, TopicResult


def _make_analysis(
    filtered_ids: list[str] | None = None,
    topics: list[TopicResult] | None = None,
) -> AnalysisResult:
    """构造 AnalysisResult。"""
    return AnalysisResult(
        filtered_ids=filtered_ids or [],
        filtered_count=len(filtered_ids or []),
        topics=topics or [],
    )


def _mock_claude_response(content: str) -> ClaudeResponse:
    """构造 ClaudeResponse。"""
    return ClaudeResponse(
        content=content,
        input_tokens=1000,
        output_tokens=500,
        model="claude-sonnet-4-20250514",
        duration_ms=2000,
        estimated_cost=0.0105,
    )


def _get_topics(merged: dict[str, object]) -> list[dict[str, object]]:
    """提取合并结果中的 topics 列表（类型安全）。"""
    topics = merged["topics"]
    assert isinstance(topics, list)
    return topics


def _get_filtered_ids(merged: dict[str, object]) -> list[str]:
    """提取合并结果中的 filtered_ids（类型安全）。"""
    ids = merged["filtered_ids"]
    assert isinstance(ids, list)
    return ids


class TestMergeAnalysisResults:
    """合并多批分析结果。"""

    def test_single_result_passthrough(self) -> None:
        """单批结果直接通过。"""
        result = _make_analysis(
            filtered_ids=["f1"],
            topics=[
                TopicResult(type="single", ai_importance_score=70, tweet_ids=["t1"]),
            ],
        )
        merged = merge_analysis_results([result])
        assert _get_filtered_ids(merged) == ["f1"]
        topics = _get_topics(merged)
        assert len(topics) == 1
        assert topics[0]["batch"] == 1

    def test_filtered_ids_union(self) -> None:
        """多批 filtered_ids 取并集。"""
        r1 = _make_analysis(filtered_ids=["f1", "f2"])
        r2 = _make_analysis(filtered_ids=["f2", "f3"])
        merged = merge_analysis_results([r1, r2])
        assert set(_get_filtered_ids(merged)) == {"f1", "f2", "f3"}

    def test_filtered_count_matches(self) -> None:
        """filtered_count 等于合并后 filtered_ids 长度。"""
        r1 = _make_analysis(filtered_ids=["f1"])
        r2 = _make_analysis(filtered_ids=["f2"])
        merged = merge_analysis_results([r1, r2])
        assert merged["filtered_count"] == len(_get_filtered_ids(merged))

    def test_topics_with_batch_tag(self) -> None:
        """topics 拼接并标记 batch 编号。"""
        r1 = _make_analysis(
            topics=[TopicResult(type="single", ai_importance_score=70, tweet_ids=["t1"])],
        )
        r2 = _make_analysis(
            topics=[
                TopicResult(
                    type="aggregated",
                    topic_label="GPT-5",
                    ai_importance_score=85,
                    tweet_ids=["t2", "t3"],
                    reason="Related tweets",
                ),
            ],
        )
        merged = merge_analysis_results([r1, r2])
        topics = _get_topics(merged)
        assert len(topics) == 2
        assert topics[0]["batch"] == 1
        assert topics[1]["batch"] == 2

    def test_topic_fields_preserved(self) -> None:
        """topic 原有字段保留。"""
        r1 = _make_analysis(
            topics=[
                TopicResult(
                    type="thread",
                    ai_importance_score=80,
                    tweet_ids=["t1", "t2"],
                    merged_text="Thread text",
                    reason="Thread reason",
                ),
            ],
        )
        merged = merge_analysis_results([r1])
        topics = _get_topics(merged)
        topic = topics[0]
        assert topic["type"] == "thread"
        assert topic["ai_importance_score"] == 80
        assert topic["tweet_ids"] == ["t1", "t2"]
        assert topic["merged_text"] == "Thread text"

    def test_empty_results(self) -> None:
        """空结果合并。"""
        r1 = _make_analysis()
        r2 = _make_analysis()
        merged = merge_analysis_results([r1, r2])
        assert _get_filtered_ids(merged) == []
        assert _get_topics(merged) == []


class TestRunDedupAnalysis:
    """AI 去重调用。"""

    @pytest.mark.asyncio
    async def test_dedup_returns_analysis_result(self) -> None:
        """去重正确解析为 AnalysisResult。"""
        dedup_output = json.dumps(
            {
                "filtered_ids": ["f1"],
                "filtered_count": 1,
                "topics": [
                    {
                        "type": "aggregated",
                        "topic_label": "GPT-5 发布",
                        "ai_importance_score": 90,
                        "tweet_ids": ["t1", "t2"],
                        "reason": "合并后保留高分话题",
                    },
                    {
                        "type": "single",
                        "ai_importance_score": 70,
                        "tweet_ids": ["t3"],
                        "reason": None,
                    },
                ],
            },
            ensure_ascii=False,
        )

        from app.clients.claude_client import ClaudeClient

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(return_value=_mock_claude_response(dedup_output))

        merged_data = merge_analysis_results(
            [
                _make_analysis(
                    filtered_ids=["f1"],
                    topics=[
                        TopicResult(type="single", ai_importance_score=70, tweet_ids=["t1"]),
                        TopicResult(type="single", ai_importance_score=70, tweet_ids=["t3"]),
                    ],
                ),
                _make_analysis(
                    topics=[
                        TopicResult(type="single", ai_importance_score=90, tweet_ids=["t2"]),
                    ],
                ),
            ]
        )

        result, response = await run_dedup_analysis(client, merged_data)

        assert isinstance(result, AnalysisResult)
        assert result.filtered_ids == ["f1"]
        assert len(result.topics) == 2
        assert result.topics[0].type == "aggregated"
        assert result.topics[0].ai_importance_score == 90
        assert response.input_tokens == 1000

    @pytest.mark.asyncio
    async def test_dedup_calls_claude_with_prompt(self) -> None:
        """去重调用 Claude 时包含正确的 Prompt。"""
        dedup_output = json.dumps(
            {
                "filtered_ids": [],
                "filtered_count": 0,
                "topics": [],
            }
        )

        from app.clients.claude_client import ClaudeClient

        client = AsyncMock(spec=ClaudeClient)
        client.complete = AsyncMock(return_value=_mock_claude_response(dedup_output))

        merged_data = merge_analysis_results([_make_analysis()])
        await run_dedup_analysis(client, merged_data)

        client.complete.assert_called_once()
        call_args = client.complete.call_args
        prompt = call_args[0][0]
        assert "智曦" in prompt
        assert "去重" in prompt or "重复" in prompt
