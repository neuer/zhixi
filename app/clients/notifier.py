"""通知服务 — 企业微信 webhook（US-029 实现）。"""

import ipaddress
import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_system_config

logger = logging.getLogger(__name__)

WEBHOOK_CONFIG_KEY = "notification_webhook_url"


def _validate_webhook_url(url: str) -> bool:
    """校验 webhook URL，禁止内网地址以防 SSRF 攻击。

    Returns:
        True 表示 URL 安全可用，False 表示被拒绝。
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # 禁止 localhost
    if hostname in ("localhost", "127.0.0.1", "::1"):
        return False

    try:
        addr = ipaddress.ip_address(hostname)
    except ValueError:
        # 不是 IP 地址（域名），允许通过
        return True

    # 禁止私有/保留/回环/链路本地地址
    return not (addr.is_private or addr.is_reserved or addr.is_loopback or addr.is_link_local)


async def send_alert(title: str, message: str, db: AsyncSession) -> None:
    """发送告警到企业微信 webhook。

    从 system_config 读取 webhook URL。
    URL 为空时静默跳过。发送失败仅记录日志，不抛异常。

    Args:
        title: 告警标题（如 "Pipeline 失败"）
        message: 告警详情（含失败环节、错误摘要）
        db: 数据库 session（用于读取 system_config）
    """
    url = await get_system_config(db, WEBHOOK_CONFIG_KEY)
    if not url:
        logger.debug("通知 webhook URL 未配置，跳过发送")
        return

    if not _validate_webhook_url(url):
        logger.error("Webhook URL 校验失败（疑似内网地址），已拒绝发送: url=%s", url)
        return

    now_str = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S UTC")
    content = f"【智曦告警】{title}\n时间: {now_str}\n{message}"
    payload = {
        "msgtype": "text",
        "text": {"content": content},
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, json=payload)
            resp.raise_for_status()
            logger.info("告警发送成功: title=%s", title)
    except httpx.HTTPError:
        logger.warning("告警发送失败（不影响主流程）: title=%s", title, exc_info=True)
    except Exception:
        logger.warning("告警发送异常（不影响主流程）: title=%s", title, exc_info=True)
