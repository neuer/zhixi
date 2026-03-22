"""POST /api/manual/generate-cover 路由测试。"""

from datetime import date
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.factories import create_digest, seed_config_keys


class TestManualGenerateCover:
    """POST /api/manual/generate-cover 测试。"""

    async def test_401_without_auth(self, client: AsyncClient) -> None:
        """未认证 → 401。"""
        resp = await client.post("/api/manual/generate-cover")
        assert resp.status_code == 401

    async def test_400_cover_disabled(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """封面图功能未开启 → 400。"""
        await seed_config_keys(
            db,
            enable_cover_generation="false",
            cover_generation_timeout="30",
            admin_password_hash="dummy",
        )

        resp = await authed_client.post("/api/manual/generate-cover")
        assert resp.status_code == 400
        assert "封面图功能未开启" in resp.json()["detail"]

    async def test_400_no_gemini_key(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """Gemini API Key 未配置 → 400。"""
        await seed_config_keys(
            db,
            enable_cover_generation="true",
            cover_generation_timeout="30",
            admin_password_hash="dummy",
        )

        with patch("app.api.manual.get_gemini_client", AsyncMock(return_value=None)):
            resp = await authed_client.post("/api/manual/generate-cover")
        assert resp.status_code == 400
        assert "Gemini API Key" in resp.json()["detail"]

    async def test_404_no_digest(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """无当日草稿 → 404。"""
        await seed_config_keys(
            db,
            enable_cover_generation="true",
            cover_generation_timeout="30",
            admin_password_hash="dummy",
        )
        mock_client = AsyncMock()

        with (
            patch("app.api.manual.get_gemini_client", AsyncMock(return_value=mock_client)),
            patch("app.api.manual.get_today_digest_date", return_value=date(2026, 3, 19)),
        ):
            resp = await authed_client.post("/api/manual/generate-cover")
        assert resp.status_code == 404

    async def test_200_success(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """正常生成 → 200 + cover_path。"""
        await seed_config_keys(
            db,
            enable_cover_generation="true",
            cover_generation_timeout="30",
            admin_password_hash="dummy",
        )
        digest_date = date(2026, 3, 19)
        await create_digest(db, digest_date=digest_date, item_count=5)
        mock_client = AsyncMock()

        with (
            patch("app.api.manual.get_gemini_client", AsyncMock(return_value=mock_client)),
            patch("app.api.manual.get_today_digest_date", return_value=digest_date),
            patch(
                "app.services.digest_service.generate_cover_image",
                new_callable=AsyncMock,
                return_value="data/covers/cover_20260319.png",
            ),
            patch(
                "app.services.digest_service.get_gemini_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            resp = await authed_client.post("/api/manual/generate-cover")

        assert resp.status_code == 200
        data = resp.json()
        assert "封面图生成成功" in data["message"]
        assert "cover_20260319.png" in data["cover_path"]

    async def test_500_generation_failed(
        self, authed_client: AsyncClient, db: AsyncSession
    ) -> None:
        """生成失败 → 500。"""
        await seed_config_keys(
            db,
            enable_cover_generation="true",
            cover_generation_timeout="30",
            admin_password_hash="dummy",
        )
        digest_date = date(2026, 3, 19)
        await create_digest(db, digest_date=digest_date, item_count=5)
        mock_client = AsyncMock()

        with (
            patch("app.api.manual.get_gemini_client", AsyncMock(return_value=mock_client)),
            patch("app.api.manual.get_today_digest_date", return_value=digest_date),
            patch(
                "app.services.digest_service.generate_cover_image",
                new_callable=AsyncMock,
                return_value=None,
            ),
            patch(
                "app.services.digest_service.get_gemini_client",
                new_callable=AsyncMock,
                return_value=mock_client,
            ),
        ):
            resp = await authed_client.post("/api/manual/generate-cover")

        assert resp.status_code == 500
        assert "封面图生成失败" in resp.json()["detail"]
