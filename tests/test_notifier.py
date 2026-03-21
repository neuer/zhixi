"""通知服务测试 — US-029 企业微信 Webhook。"""

import json

import httpx
import pytest
import respx
from httpx import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.notifier import _validate_webhook_url, send_alert
from app.models.config import SystemConfig

WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=test-key"


async def _seed_webhook_url(db: AsyncSession, url: str = WEBHOOK_URL) -> None:
    """预置 webhook URL 到 system_config。"""
    db.add(SystemConfig(key="notification_webhook_url", value=url, description="webhook"))
    await db.flush()


# ── 正常发送 ────────────────────────────────────────────────


@respx.mock
async def test_send_alert_posts_to_webhook(db: AsyncSession) -> None:
    """URL 已配置 → 发送 POST 请求到 webhook。"""
    await _seed_webhook_url(db)

    route = respx.post(WEBHOOK_URL).mock(return_value=Response(200, json={"errcode": 0}))

    await send_alert("Pipeline 失败", "fetch 阶段异常: timeout", db)

    assert route.called


@respx.mock
async def test_send_alert_payload_format(db: AsyncSession) -> None:
    """payload 符合企业微信格式：msgtype=text + 【智曦告警】前缀。"""
    await _seed_webhook_url(db)

    route = respx.post(WEBHOOK_URL).mock(return_value=Response(200, json={"errcode": 0}))

    await send_alert("测试标题", "测试内容", db)

    request = route.calls.last.request
    payload = json.loads(request.content)
    assert payload["msgtype"] == "text"
    assert "【智曦告警】测试标题" in payload["text"]["content"]
    assert "测试内容" in payload["text"]["content"]


@respx.mock
async def test_send_alert_includes_timestamp(db: AsyncSession) -> None:
    """content 包含时间信息。"""
    await _seed_webhook_url(db)

    route = respx.post(WEBHOOK_URL).mock(return_value=Response(200, json={"errcode": 0}))

    await send_alert("告警", "消息", db)

    request = route.calls.last.request
    payload = json.loads(request.content)
    content = payload["text"]["content"]
    # 应包含 UTC 时间格式
    assert "UTC" in content


# ── 跳过发送 ────────────────────────────────────────────────


@respx.mock
async def test_send_alert_skips_empty_url(db: AsyncSession) -> None:
    """URL 为空字符串 → 不发送 HTTP 请求。"""
    await _seed_webhook_url(db, url="")

    route = respx.post(WEBHOOK_URL).mock(return_value=Response(200))

    await send_alert("告警", "消息", db)

    assert not route.called


@respx.mock
async def test_send_alert_skips_no_config(db: AsyncSession) -> None:
    """system_config 无 webhook key → 不发送。"""
    # 不 seed 任何 config
    route = respx.post(WEBHOOK_URL).mock(return_value=Response(200))

    await send_alert("告警", "消息", db)

    assert not route.called


# ── 失败容错 ────────────────────────────────────────────────


@respx.mock
async def test_send_alert_logs_on_http_error(db: AsyncSession) -> None:
    """webhook 返回 500 → 不抛异常，仅记录日志。"""
    await _seed_webhook_url(db)

    respx.post(WEBHOOK_URL).mock(return_value=Response(500, text="Internal Server Error"))

    # 不应抛出异常
    await send_alert("告警", "消息", db)


@respx.mock
async def test_send_alert_logs_on_timeout(db: AsyncSession) -> None:
    """网络超时 → 不抛异常，仅记录日志。"""
    await _seed_webhook_url(db)

    respx.post(WEBHOOK_URL).mock(side_effect=httpx.ConnectTimeout("timeout"))

    # 不应抛出异常
    await send_alert("告警", "消息", db)


# ── SSRF 防护测试 ────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "https://0.0.0.0/hook",
        "https://[::]/hook",
        "https://0177.0.0.1/hook",
        "https://0x7f.0.0.1/hook",
        "https://0x7f000001/hook",
        "https://2130706433/hook",
        "https://[::1]/hook",
        "https://[::ffff:127.0.0.1]/hook",
        "https://localhost/hook",
        "https://127.0.0.1/hook",
    ],
)
def test_validate_webhook_url_blocks_ssrf_variants(url: str) -> None:
    """SSRF 变形地址均被拦截。"""
    assert _validate_webhook_url(url) is False


def test_validate_webhook_url_allows_public() -> None:
    """公网域名 URL 允许通过。"""
    assert _validate_webhook_url("https://qyapi.weixin.qq.com/cgi-bin/webhook/send") is True


def test_validate_webhook_url_blocks_private_ip() -> None:
    """RFC 1918 私有 IP 被拦截。"""
    assert _validate_webhook_url("https://10.0.0.1/hook") is False
    assert _validate_webhook_url("https://192.168.1.1/hook") is False
