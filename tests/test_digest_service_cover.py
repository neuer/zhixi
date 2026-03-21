"""DigestService 封面图集成测试。"""

from datetime import date, datetime
from unittest.mock import AsyncMock, patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import TwitterAccount
from app.models.config import SystemConfig
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse


async def _seed_data(db: AsyncSession, digest_date: date) -> None:
    """写入测试所需的基础数据。"""
    # system_config
    configs = [
        SystemConfig(key="top_n", value="10"),
        SystemConfig(key="min_articles", value="1"),
        SystemConfig(key="enable_cover_generation", value="true"),
        SystemConfig(key="cover_generation_timeout", value="30"),
    ]
    db.add_all(configs)

    # account + tweet
    account = TwitterAccount(
        id=1,
        twitter_user_id="u1",
        twitter_handle="testuser",
        display_name="Test User",
        weight=1.0,
        is_active=True,
    )
    db.add(account)
    await db.flush()

    tweet = Tweet(
        tweet_id="t1",
        account_id=1,
        original_text="Test tweet about AI",
        tweet_time=datetime(2026, 3, 19, 10, 0, 0),
        tweet_url="https://x.com/testuser/status/t1",
        likes=100,
        retweets=50,
        replies=10,
        title="AI 新突破",
        translated_text="AI 新突破翻译",
        ai_comment="这是一条重要的 AI 新闻",
        ai_importance_score=8,
        heat_score=85.0,
        is_processed=True,
        digest_date=digest_date,
    )
    db.add(tweet)
    await db.flush()


class TestDigestServiceCoverIntegration:
    """DigestService 封面图集成测试。"""

    async def test_cover_generation_enabled(self, db: AsyncSession) -> None:
        """enable_cover_generation=true 时调用 cover_generator。"""
        digest_date = date(2026, 3, 19)
        await _seed_data(db, digest_date)

        mock_claude = AsyncMock()
        mock_claude.complete.return_value = ClaudeResponse(
            content="今日 AI 领域精彩纷呈",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet",
            duration_ms=500,
            estimated_cost=0.001,
        )

        from app.services.digest_service import DigestService

        svc = DigestService(db, claude_client=mock_claude)

        with patch(
            "app.services.digest_service.generate_cover_image",
            new_callable=AsyncMock,
            return_value="data/covers/cover_20260319.png",
        ) as mock_cover:
            digest = await svc.generate_daily_digest(digest_date)

            mock_cover.assert_called_once()
            assert digest.cover_image_path == "data/covers/cover_20260319.png"

    async def test_cover_generation_disabled(self, db: AsyncSession) -> None:
        """enable_cover_generation=false 时跳过封面图生成。"""
        digest_date = date(2026, 3, 19)
        await _seed_data(db, digest_date)

        # 覆盖配置为 false
        from sqlalchemy import update

        from app.models.config import SystemConfig

        await db.execute(
            update(SystemConfig)
            .where(SystemConfig.key == "enable_cover_generation")
            .values(value="false")
        )

        mock_claude = AsyncMock()
        mock_claude.complete.return_value = ClaudeResponse(
            content="今日 AI 领域精彩纷呈",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet",
            duration_ms=500,
            estimated_cost=0.001,
        )

        from app.services.digest_service import DigestService

        svc = DigestService(db, claude_client=mock_claude)

        with patch(
            "app.services.digest_service.generate_cover_image",
            new_callable=AsyncMock,
        ) as mock_cover:
            digest = await svc.generate_daily_digest(digest_date)

            mock_cover.assert_not_called()
            assert digest.cover_image_path is None

    async def test_cover_generation_no_gemini_client(self, db: AsyncSession) -> None:
        """GEMINI_API_KEY 未配置时跳过。"""
        digest_date = date(2026, 3, 19)
        await _seed_data(db, digest_date)

        mock_claude = AsyncMock()
        mock_claude.complete.return_value = ClaudeResponse(
            content="今日 AI 领域精彩纷呈",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet",
            duration_ms=500,
            estimated_cost=0.001,
        )

        from app.services.digest_service import DigestService

        svc = DigestService(db, claude_client=mock_claude)

        with (
            patch(
                "app.services.digest_service.get_gemini_client",
                return_value=None,
            ),
            patch(
                "app.services.digest_service.generate_cover_image",
                new_callable=AsyncMock,
            ) as mock_cover,
        ):
            digest = await svc.generate_daily_digest(digest_date)

            mock_cover.assert_not_called()
            assert digest.cover_image_path is None

    async def test_cover_generation_failure_not_blocking(self, db: AsyncSession) -> None:
        """封面图生成失败不阻塞草稿生成。"""
        digest_date = date(2026, 3, 19)
        await _seed_data(db, digest_date)

        mock_claude = AsyncMock()
        mock_claude.complete.return_value = ClaudeResponse(
            content="今日 AI 领域精彩纷呈",
            input_tokens=100,
            output_tokens=50,
            model="claude-sonnet",
            duration_ms=500,
            estimated_cost=0.001,
        )

        from app.services.digest_service import DigestService

        svc = DigestService(db, claude_client=mock_claude)

        with patch(
            "app.services.digest_service.generate_cover_image",
            new_callable=AsyncMock,
            return_value=None,
        ):
            digest = await svc.generate_daily_digest(digest_date)

            # 草稿正常生成
            assert digest is not None
            assert digest.status == "draft"
            assert digest.cover_image_path is None
