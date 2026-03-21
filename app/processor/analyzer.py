"""全局分析器 — 第一步 AI 加工（US-019）。

调用 Claude API 执行全局分析 Prompt（R.1.2），
识别无关推文、Thread、聚合话题，并评估 AI 重要性分。
"""

import logging

from app.clients.claude_client import ClaudeClient
from app.processor.analyzer_prompts import GLOBAL_ANALYSIS_PROMPT, GLOBAL_ANALYSIS_SCHEMA
from app.processor.json_validator import validate_and_fix
from app.schemas.client_types import ClaudeResponse
from app.schemas.processor_types import AnalysisResult

logger = logging.getLogger(__name__)


async def run_global_analysis(
    claude_client: ClaudeClient,
    tweets_json: str,
) -> tuple[AnalysisResult, ClaudeResponse]:
    """执行全局分析。

    Args:
        claude_client: Claude API 客户端
        tweets_json: R.1.1b 格式序列化的推文 JSON 字符串

    Returns:
        (AnalysisResult, ClaudeResponse) — 分析结果 + API 响应元数据

    Raises:
        JsonValidationError: AI 输出无法解析
        ClaudeAPIError: API 调用失败
    """
    prompt = GLOBAL_ANALYSIS_PROMPT.format(tweets_json=tweets_json)

    response = await claude_client.complete(prompt, max_tokens=4096)

    parsed = validate_and_fix(response.content, GLOBAL_ANALYSIS_SCHEMA)

    result = AnalysisResult.from_parsed(parsed)

    return result, response
