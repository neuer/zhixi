"""POST /api/manual/generate-cover 路由测试。"""

from datetime import date
from unittest.mock import AsyncMock, patch

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig
from app.models.digest import DailyDigest


async def _seed_config(db: AsyncSession, *, cover_enabled: bool = True) -> None:
    """写入测试配置。"""
    configs = [
        SystemConfig(key="enable_cover_generation", value=str(cover_enabled).lower()),
        SystemConfig(key="cover_generation_timeout", value="30"),
        SystemConfig(key="admin_password_hash", value="dummy"),
    ]
    db.add_all(configs)
    await db.flush()


async def _seed_digest(db: AsyncSession, digest_date: date) -> DailyDigest:
    """创建测试 digest。"""
    digest = DailyDigest(
        digest_date=digest_date,
        version=1,
        is_current=True,
        status="draft",
        item_count=5,
    )
    db.add(digest)
    await db.flush()
    return digest


class TestManualGenerateCover:
    """POST /api/manual/generate-cover 测试。"""

    async def test_401_without_auth(self, client: AsyncClient) -> None:
        """未认证 → 401。"""
        resp = await client.post("/api/manual/generate-cover")
        assert resp.status_code == 401

    async def test_400_cover_disabled(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """封面图功能未开启 → 400。"""
        await _seed_config(db, cover_enabled=False)

        resp = await authed_client.post("/api/manual/generate-cover")
        assert resp.status_code == 400
        assert "封面图功能未开启" in resp.json()["detail"]

    async def test_400_no_gemini_key(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """Gemini API Key 未配置 → 400。"""
        await _seed_config(db, cover_enabled=True)

        with patch("app.api.manual.get_gemini_client", AsyncMock(return_value=None)):
            resp = await authed_client.post("/api/manual/generate-cover")
        assert resp.status_code == 400
        assert "Gemini API Key" in resp.json()["detail"]

    async def test_404_no_digest(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """无当日草稿 → 404。"""
        await _seed_config(db, cover_enabled=True)
        mock_client = AsyncMock()

        with (
            patch("app.api.manual.get_gemini_client", AsyncMock(return_value=mock_client)),
            patch("app.api.manual.get_today_digest_date", return_value=date(2026, 3, 19)),
        ):
            resp = await authed_client.post("/api/manual/generate-cover")
        assert resp.status_code == 404

    async def test_200_success(self, authed_client: AsyncClient, db: AsyncSession) -> None:
        """正常生成 → 200 + cover_path。"""
        await _seed_config(db, cover_enabled=True)
        digest_date = date(2026, 3, 19)
        await _seed_digest(db, digest_date)
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
        await _seed_config(db, cover_enabled=True)
        digest_date = date(2026, 3, 19)
        await _seed_digest(db, digest_date)
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
