"""封面图生成器（US-026）。

调用 Gemini Imagen API 生成封面图，用 Pillow 裁切/缩放至 900x383px。
超时/异常不阻塞主流程，仅 log warning。
"""

import asyncio
import io
import logging
from datetime import date
from pathlib import Path

from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.gemini_client import GeminiAPIError, GeminiClient
from app.digest.cover_prompts import build_cover_prompt
from app.models.api_cost_log import ApiCostLog
from app.models.digest_item import DigestItem
from app.schemas.enums import CallType, ServiceType

logger = logging.getLogger(__name__)

# 目标尺寸
_TARGET_WIDTH = 900
_TARGET_HEIGHT = 383

# 封面图存储目录
_COVERS_DIR = Path("data/covers")

# 默认封面图路径
_DEFAULT_COVER_PATH = Path("data/default_cover.png")


def _resize_image(image_bytes: bytes) -> bytes:
    """将图片裁切/缩放至 900x383px。

    先按目标宽高比裁切中心区域，再缩放到目标尺寸。
    """
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")

    # 计算目标宽高比
    target_ratio = _TARGET_WIDTH / _TARGET_HEIGHT
    img_ratio = img.width / img.height

    if img_ratio > target_ratio:
        # 图片更宽，裁切左右
        new_width = int(img.height * target_ratio)
        left = (img.width - new_width) // 2
        img = img.crop((left, 0, left + new_width, img.height))
    elif img_ratio < target_ratio:
        # 图片更高，裁切上下
        new_height = int(img.width / target_ratio)
        top = (img.height - new_height) // 2
        img = img.crop((0, top, img.width, top + new_height))

    # 缩放到目标尺寸
    img = img.resize((_TARGET_WIDTH, _TARGET_HEIGHT), Image.Resampling.LANCZOS)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _record_cover_cost(
    db: AsyncSession,
    digest_date: date,
    *,
    estimated_cost: float = 0.0,
    duration_ms: int = 0,
    success: bool = False,
) -> None:
    """记录封面图生成 API 成本日志。"""
    cost_log = ApiCostLog(
        call_date=digest_date,
        service=ServiceType.GEMINI,
        call_type=CallType.COVER,
        endpoint="imagen-3.0-generate-002",
        model="imagen-3.0-generate-002",
        estimated_cost=estimated_cost,
        duration_ms=duration_ms,
        success=success,
    )
    db.add(cost_log)


async def generate_cover_image(
    gemini_client: GeminiClient,
    top_items: list[DigestItem],
    digest_date: date,
    timeout: float,
    db: AsyncSession,
) -> str | None:
    """生成封面图。

    Args:
        gemini_client: Gemini API 客户端
        top_items: DigestItem 列表（已按 heat_score 降序）
        digest_date: 日报日期
        timeout: 超时时间（秒）
        db: 数据库 session

    Returns:
        封面图路径字符串，失败返回 None
    """
    if not top_items:
        logger.info("无可用条目，跳过封面图生成")
        return None

    # 构建 prompt
    titles = [item.snapshot_title or "" for item in top_items]
    prompt = build_cover_prompt(titles, digest_date)

    try:
        response = await gemini_client.generate_image(prompt, timeout=timeout)

        # 裁切/缩放（通过 asyncio.to_thread 避免 Pillow CPU 阻塞事件循环）
        resized_bytes = await asyncio.to_thread(_resize_image, response.image_bytes)

        # 保存文件（mkdir 走线程池避免阻塞事件循环）
        await asyncio.to_thread(_COVERS_DIR.mkdir, parents=True, exist_ok=True)
        filename = f"cover_{digest_date.strftime('%Y%m%d')}.png"
        cover_path = _COVERS_DIR / filename
        await asyncio.to_thread(cover_path.write_bytes, resized_bytes)

        # 记录成本
        _record_cover_cost(
            db,
            digest_date,
            estimated_cost=response.estimated_cost,
            duration_ms=response.duration_ms,
            success=True,
        )

        logger.info("封面图生成成功: %s", cover_path)
        return str(cover_path)

    except GeminiAPIError as e:
        logger.warning("封面图生成失败（API 错误）: %s", e)
        _record_cover_cost(db, digest_date)
        return None

    except (TimeoutError, OSError) as e:
        logger.warning("封面图生成失败（网络/IO 错误）: %s", e, exc_info=True)
        _record_cover_cost(db, digest_date)
        return None
