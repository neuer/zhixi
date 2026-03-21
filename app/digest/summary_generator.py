"""导读摘要生成器（US-023）。"""

import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeAPIError, ClaudeClient
from app.clients.notifier import send_alert
from app.digest.summary_prompts import (
    DEFAULT_SUMMARY,
    EMPTY_DAY_SUMMARY,
    SUMMARY_PROMPT_TEMPLATE,
)
from app.models.digest_item import DigestItem
from app.schemas.client_types import ClaudeResponse
from app.schemas.enums import ItemType

logger = logging.getLogger(__name__)


def _serialize_top_items(items: list[DigestItem]) -> str:
    """将 digest_items 序列化为 R.1.6 导读摘要输入 JSON。

    type 组合规则：
    - item_type="tweet" → "tweet"
    - item_type="topic" + snapshot_topic_type="aggregated" → "topic_aggregated"
    - item_type="topic" + snapshot_topic_type="thread" → "topic_thread"
    """
    articles: list[dict[str, object]] = []
    for item in items:
        if item.item_type == ItemType.TWEET:
            article_type = "tweet"
        else:
            article_type = f"topic_{item.snapshot_topic_type or 'aggregated'}"
        articles.append(
            {
                "title": item.snapshot_title or "",
                "heat_score": item.snapshot_heat_score,
                "type": article_type,
            }
        )
    return json.dumps(articles, ensure_ascii=False, indent=2)


async def generate_summary(
    claude_client: ClaudeClient,
    top_items: list[DigestItem],
    *,
    db: AsyncSession | None = None,
) -> tuple[str, ClaudeResponse | None, bool]:
    """生成导读摘要。

    Args:
        claude_client: Claude API 客户端。
        top_items: TOP 5 digest_items（已按 heat_score 降序）。
        db: 可选 AsyncSession，用于发送降级告警。

    Returns:
        (summary_text, claude_response, degraded)。失败时 degraded=True。
    """
    if not top_items:
        logger.info("无可用条目，使用空日导读摘要")
        return EMPTY_DAY_SUMMARY, None, False

    top_articles_json = _serialize_top_items(top_items)
    prompt = SUMMARY_PROMPT_TEMPLATE.format(top_articles_json=top_articles_json)

    try:
        response = await claude_client.complete(prompt, max_tokens=512)
        summary = response.content.strip()
        logger.info("导读摘要生成成功，长度=%d", len(summary))
        return summary, response, False
    except ClaudeAPIError:
        logger.warning("Claude API 调用失败，使用默认导读摘要", exc_info=True)
        if db is not None:
            await send_alert("摘要生成降级", "Claude API 调用失败，已使用默认导读摘要", db)
        return DEFAULT_SUMMARY, None, True
    except (TimeoutError, OSError):
        logger.warning("导读摘要生成异常（网络/IO 错误），使用默认导读摘要", exc_info=True)
        if db is not None:
            await send_alert("摘要生成降级", "导读摘要生成异常（网络/IO），已使用默认导读摘要", db)
        return DEFAULT_SUMMARY, None, True
