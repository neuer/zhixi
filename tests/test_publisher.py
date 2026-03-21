"""US-037 测试 — 微信客户端空壳 + publish_mode 分支。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig
from app.models.digest import DailyDigest
from app.publisher.wechat_client import WechatClient, get_wechat_client


class TestWechatClient:
    """微信客户端空壳测试。"""

    def test_get_access_token_not_implemented(self) -> None:
        """get_access_token 应 raise NotImplementedError。"""
        client = WechatClient(app_id="test_id", app_secret="test_secret")
        with pytest.raises(NotImplementedError, match="微信API自动发布功能将在公众号认证后实现"):
            client.get_access_token()

    def test_upload_article_not_implemented(self) -> None:
        """upload_article 应 raise NotImplementedError。"""
        client = WechatClient(app_id="test_id", app_secret="test_secret")
        with pytest.raises(NotImplementedError, match="微信API自动发布功能将在公众号认证后实现"):
            client.upload_article(title="标题", content="内容", cover_url="https://example.com")

    def test_send_mass_not_implemented(self) -> None:
        """send_mass 应 raise NotImplementedError。"""
        client = WechatClient(app_id="test_id", app_secret="test_secret")
        with pytest.raises(NotImplementedError, match="微信API自动发布功能将在公众号认证后实现"):
            client.send_mass(media_id="media_123")

    def test_get_wechat_client_unconfigured(self) -> None:
        """WECHAT_APP_ID 为空时 get_wechat_client 应 raise ValueError。"""
        with pytest.raises(ValueError, match="微信API未配置"):
            get_wechat_client(app_id="", app_secret="")

    def test_get_wechat_client_partial_config(self) -> None:
        """只配置了 APP_ID 没配置 SECRET 也应 raise ValueError。"""
        with pytest.raises(ValueError, match="微信API未配置"):
            get_wechat_client(app_id="some_id", app_secret="")

    def test_get_wechat_client_configured(self) -> None:
        """完整配置时应返回 WechatClient 实例。"""
        client = get_wechat_client(app_id="test_id", app_secret="test_secret")
        assert isinstance(client, WechatClient)


class TestMarkPublishedModes:
    """mark-published 路由 publish_mode 分支测试。"""

    async def _create_draft(self, db: AsyncSession) -> DailyDigest:
        """创建测试草稿。"""
        from app.config import get_today_digest_date

        digest = DailyDigest(
            digest_date=get_today_digest_date(),
            version=1,
            is_current=True,
            status="draft",
            content_markdown="# 测试",
        )
        db.add(digest)
        await db.flush()
        return digest

    async def test_mark_published_api_mode_returns_501(
        self, authed_client: AsyncClient, db: AsyncSession, seeded_db: AsyncSession
    ) -> None:
        """publish_mode=api 时 mark-published 应返回 501。"""
        # 设置 publish_mode 为 api
        stmt = select(SystemConfig).where(SystemConfig.key == "publish_mode")
        result = await db.execute(stmt)
        config = result.scalar_one()
        config.value = "api"
        await db.flush()

        # 创建草稿
        await self._create_draft(db)

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 501
        assert "微信API自动发布功能将在公众号认证后实现" in resp.json()["detail"]

    async def test_mark_published_manual_mode_success(
        self, authed_client: AsyncClient, db: AsyncSession, seeded_db: AsyncSession
    ) -> None:
        """publish_mode=manual 时 mark-published 应正常标记。"""
        digest = await self._create_draft(db)

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200
        assert resp.json()["message"] == "发布成功"

        # 验证 DB 状态
        result = await db.execute(select(DailyDigest).where(DailyDigest.id == digest.id))
        updated = result.scalar_one()
        assert updated.status == "published"
        assert updated.published_at is not None
