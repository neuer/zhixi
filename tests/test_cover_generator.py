"""封面图生成器测试。"""

import io
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

from PIL import Image
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gemini_client import GeminiAPIError, GeminiClient
from app.digest.cover_generator import (
    _resize_image,
    generate_cover_image,
)
from app.models.api_cost_log import ApiCostLog
from app.models.digest_item import DigestItem
from app.schemas.client_types import GeminiImageResponse


def _make_png_bytes(width: int = 1024, height: int = 576) -> bytes:
    """创建指定尺寸的测试 PNG 图片字节。"""
    img = Image.new("RGB", (width, height), color=(100, 150, 200))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_items(titles: list[str]) -> list[DigestItem]:
    """创建测试用 DigestItem 列表。"""
    items = []
    for i, title in enumerate(titles):
        item = DigestItem(
            digest_id=1,
            item_type="tweet",
            item_ref_id=i + 1,
            display_order=i + 1,
            snapshot_title=title,
            snapshot_heat_score=90.0 - i,
        )
        items.append(item)
    return items


class TestResizeImage:
    """_resize_image 缩放逻辑测试。"""

    def test_resize_to_target(self) -> None:
        """缩放到 900x383。"""
        png_bytes = _make_png_bytes(1920, 1080)
        result = _resize_image(png_bytes)

        img = Image.open(io.BytesIO(result))
        assert img.size == (900, 383)

    def test_resize_small_image(self) -> None:
        """小图放大到 900x383。"""
        png_bytes = _make_png_bytes(200, 100)
        result = _resize_image(png_bytes)

        img = Image.open(io.BytesIO(result))
        assert img.size == (900, 383)

    def test_resize_exact_size(self) -> None:
        """已是目标尺寸不变。"""
        png_bytes = _make_png_bytes(900, 383)
        result = _resize_image(png_bytes)

        img = Image.open(io.BytesIO(result))
        assert img.size == (900, 383)


class TestGenerateCoverImage:
    """generate_cover_image 集成测试。"""

    async def test_success(self, db: AsyncSession, tmp_path: Path) -> None:
        """正常生成封面图 → 文件保存 + cost_log 写入。"""
        png_bytes = _make_png_bytes()
        items = _make_items(["AI 突破", "新模型发布", "政策解读"])

        mock_client = AsyncMock(spec=GeminiClient)
        mock_client.generate_image.return_value = GeminiImageResponse(
            image_bytes=png_bytes,
            duration_ms=2500,
            estimated_cost=0.04,
        )

        covers_dir = tmp_path / "covers"
        with patch("app.digest.cover_generator._COVERS_DIR", covers_dir):
            result = await generate_cover_image(
                gemini_client=mock_client,
                top_items=items,
                digest_date=date(2026, 3, 19),
                timeout=30.0,
                db=db,
            )

        assert result is not None
        assert "cover_20260319.png" in result

        cover_file = covers_dir / "cover_20260319.png"
        assert cover_file.exists()
        img = Image.open(cover_file)
        assert img.size == (900, 383)

        cost_result = await db.execute(select(ApiCostLog).where(ApiCostLog.service == "gemini"))
        cost_log = cost_result.scalar_one()
        assert cost_log.call_type == "cover"
        assert cost_log.estimated_cost == 0.04
        assert cost_log.duration_ms == 2500
        assert cost_log.success is True

    async def test_api_error_returns_none(self, db: AsyncSession, tmp_path: Path) -> None:
        """API 错误 → 返回 None + 记录失败 cost_log。"""
        items = _make_items(["标题1"])

        mock_client = AsyncMock(spec=GeminiClient)
        mock_client.generate_image.side_effect = GeminiAPIError("API 失败")

        covers_dir = tmp_path / "covers"
        with patch("app.digest.cover_generator._COVERS_DIR", covers_dir):
            result = await generate_cover_image(
                gemini_client=mock_client,
                top_items=items,
                digest_date=date(2026, 3, 19),
                timeout=30.0,
                db=db,
            )

        assert result is None

        cost_result = await db.execute(select(ApiCostLog).where(ApiCostLog.service == "gemini"))
        cost_log = cost_result.scalar_one()
        assert cost_log.success is False

    async def test_empty_items_returns_none(self, db: AsyncSession, tmp_path: Path) -> None:
        """空 items → 返回 None，不调用 API。"""
        mock_client = AsyncMock(spec=GeminiClient)

        covers_dir = tmp_path / "covers"
        with patch("app.digest.cover_generator._COVERS_DIR", covers_dir):
            result = await generate_cover_image(
                gemini_client=mock_client,
                top_items=[],
                digest_date=date(2026, 3, 19),
                timeout=30.0,
                db=db,
            )

        assert result is None
        mock_client.generate_image.assert_not_called()
