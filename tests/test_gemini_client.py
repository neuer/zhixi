"""GeminiClient 单元测试。"""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from app.clients.gemini_client import GeminiAPIError, GeminiClient
from app.schemas.client_types import GeminiImageResponse


class TestGeminiClient:
    """GeminiClient 测试。"""

    def _make_client(self) -> GeminiClient:
        """创建测试用 GeminiClient。"""
        return GeminiClient(api_key="test-key")

    def _make_mock_response(self, image_bytes: bytes = b"fake-png-data") -> MagicMock:
        """构造 mock generate_images 响应。"""
        mock_image = MagicMock()
        mock_image.image.image_bytes = image_bytes
        mock_response = MagicMock()
        mock_response.generated_images = [mock_image]
        return mock_response

    async def test_generate_image_success(self) -> None:
        """正常生成图片返回 GeminiImageResponse。"""
        client = self._make_client()
        mock_response = self._make_mock_response(b"test-image-bytes")

        with patch.object(client._client.models, "generate_images", return_value=mock_response):
            result = await client.generate_image("test prompt", timeout=30.0)

        assert isinstance(result, GeminiImageResponse)
        assert result.image_bytes == b"test-image-bytes"
        assert result.duration_ms >= 0
        assert result.estimated_cost == 0.04  # Imagen 3 标准定价

    async def test_generate_image_api_error(self) -> None:
        """API 错误抛出 GeminiAPIError。"""
        client = self._make_client()

        with (
            patch.object(
                client._client.models,
                "generate_images",
                side_effect=Exception("API connection failed"),
            ),
            pytest.raises(GeminiAPIError, match="API connection failed"),
        ):
            await client.generate_image("test prompt", timeout=30.0)

    async def test_generate_image_empty_response(self) -> None:
        """空响应抛出 GeminiAPIError。"""
        client = self._make_client()
        mock_response = MagicMock()
        mock_response.generated_images = []

        with (
            patch.object(client._client.models, "generate_images", return_value=mock_response),
            pytest.raises(GeminiAPIError, match="未返回图片"),
        ):
            await client.generate_image("test prompt", timeout=30.0)

    async def test_generate_image_timeout(self) -> None:
        """超时抛出 GeminiAPIError。"""
        client = self._make_client()

        async def slow_generate(*_args: object, **_kwargs: object) -> None:
            await asyncio.sleep(10)

        with (
            patch(
                "app.clients.gemini_client.asyncio.to_thread",
                side_effect=asyncio.TimeoutError,
            ),
            pytest.raises(GeminiAPIError, match="超时"),
        ):
            await client.generate_image("test prompt", timeout=0.01)


class TestGetGeminiClient:
    """get_gemini_client 异步工厂函数测试。"""

    async def test_returns_none_without_key(self) -> None:
        """DB 和 .env 都无 key 时返回 None。"""
        from app.clients.gemini_client import get_gemini_client

        with patch("app.clients.gemini_client.get_secret_config", return_value=""):
            result = await get_gemini_client(MagicMock())
            assert result is None

    async def test_returns_client_with_key(self) -> None:
        """有 key 时返回 GeminiClient。"""
        from app.clients.gemini_client import get_gemini_client

        with patch("app.clients.gemini_client.get_secret_config", return_value="test-gemini-key"):
            result = await get_gemini_client(MagicMock())
            assert isinstance(result, GeminiClient)
