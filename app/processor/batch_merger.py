"""多批分析结果合并与 AI 去重（US-020）。

将多批全局分析的 AnalysisResult 合并为去重输入格式，
调用 Claude API 执行轻量去重。

编号说明：
- R.1.5b 是去重专用 prompt 编号，与 R.1.5（Thread 翻译 prompt）无关。
  "b" 后缀表示 batch-dedup。
"""

import json
import logging

from app.clients.claude_client import ClaudeClient
from app.processor.json_validator import validate_and_fix
from app.processor.merger_prompts import DEDUP_PROMPT, DEDUP_SCHEMA
from app.schemas.client_types import ClaudeResponse
from app.schemas.processor_types import AnalysisResult

logger = logging.getLogger(__name__)


def merge_analysis_results(results: list[AnalysisResult]) -> dict[str, object]:
    """将多批 AnalysisResult 合并为 R.1.5b 去重输入格式。

    - filtered_ids: 取所有批次并集
    - topics: 直接拼接，附加 batch 标记（从 1 开始编号）
    - filtered_count: 合并后 filtered_ids 的长度
    """
    all_filtered: set[str] = set()
    all_topics: list[dict[str, object]] = []

    for batch_idx, result in enumerate(results, start=1):
        all_filtered.update(result.filtered_ids)

        for topic in result.topics:
            topic_dict: dict[str, object] = {
                "type": topic.type,
                "ai_importance_score": topic.ai_importance_score,
                "tweet_ids": topic.tweet_ids,
                "batch": batch_idx,
            }
            if topic.topic_label is not None:
                topic_dict["topic_label"] = topic.topic_label
            if topic.merged_text is not None:
                topic_dict["merged_text"] = topic.merged_text
            if topic.reason is not None:
                topic_dict["reason"] = topic.reason
            all_topics.append(topic_dict)

    filtered_list = sorted(all_filtered)
    return {
        "filtered_ids": filtered_list,
        "filtered_count": len(filtered_list),
        "topics": all_topics,
    }


async def run_dedup_analysis(
    claude_client: ClaudeClient,
    merged_data: dict[str, object],
) -> tuple[AnalysisResult, ClaudeResponse]:
    """执行 R.1.5b 去重 AI 调用。

    Args:
        claude_client: Claude API 客户端
        merged_data: merge_analysis_results() 的输出

    Returns:
        (AnalysisResult, ClaudeResponse) — 去重后的分析结果 + API 响应元数据

    Raises:
        JsonValidationError: AI 输出无法解析
        ClaudeAPIError: API 调用失败
    """
    merged_json = json.dumps(merged_data, ensure_ascii=False)
    prompt = DEDUP_PROMPT.format(merged_analysis_json=merged_json)

    response = await claude_client.complete(prompt, max_tokens=4096)

    parsed = validate_and_fix(response.content, DEDUP_SCHEMA)

    result = AnalysisResult.from_parsed(parsed)

    return result, response
