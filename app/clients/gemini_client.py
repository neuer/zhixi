"""Gemini Imagen API 客户端封装（US-026）。

使用 google.genai.Client 调用 Imagen 3 生成封面图。
generate_images 是同步 API，通过 asyncio.to_thread 包装为异步调用。
Service 层负责写 api_cost_log，GeminiClient 不持有 db session。
"""

import asyncio
import logging
import time

from google import genai
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_secret_config
from app.schemas.client_types import GeminiImageResponse

logger = logging.getLogger(__name__)

# Imagen 3 标准模式定价：$0.04/image
_IMAGEN_COST_PER_IMAGE = 0.04
_IMAGEN_MODEL = "imagen-3.0-generate-002"


class GeminiAPIError(Exception):
    """Gemini API 调用失败。"""


class GeminiClient:
    """Gemini Imagen API 异步客户端。"""

    def __init__(
        self,
        api_key: str,
        *,
        _genai_client: genai.Client | None = None,
    ) -> None:
        self._client = _genai_client or genai.Client(api_key=api_key)

    async def generate_image(
        self,
        prompt: str,
        timeout: float = 30.0,
    ) -> GeminiImageResponse:
        """调用 Imagen 3 生成图片。

        Args:
            prompt: 图片生成 prompt
            timeout: 超时时间（秒）

        Returns:
            GeminiImageResponse（含 image_bytes, duration_ms, estimated_cost）

        Raises:
            GeminiAPIError: API 调用失败或超时
        """
        start = time.monotonic()

        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_images,
                    model=_IMAGEN_MODEL,
                    prompt=prompt,
                    config={"number_of_images": 1, "aspect_ratio": "16:9"},
                ),
                timeout=timeout,
            )
        except TimeoutError:
            raise GeminiAPIError(f"Gemini API 超时（{timeout}s）") from None
        except Exception as e:
            logger.error("Gemini API 调用异常", exc_info=True)
            raise GeminiAPIError(str(e)) from e

        duration_ms = int((time.monotonic() - start) * 1000)

        if not response.generated_images:
            raise GeminiAPIError("Gemini API 未返回图片")

        first_image = response.generated_images[0]
        raw_bytes: bytes | None = first_image.image.image_bytes  # type: ignore[union-attr]
        if raw_bytes is None:
            raise GeminiAPIError("Gemini API 返回的图片数据为空")

        return GeminiImageResponse(
            image_bytes=raw_bytes,
            duration_ms=duration_ms,
            estimated_cost=_IMAGEN_COST_PER_IMAGE,
        )


async def get_gemini_client(db: AsyncSession) -> GeminiClient | None:
    """从 DB / .env 读取 API Key，构建 GeminiClient。Key 为空时返回 None。"""
    api_key = await get_secret_config(db, "gemini_api_key")
    if not api_key:
        return None
    return GeminiClient(api_key=api_key)
