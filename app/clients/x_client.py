"""X API 用户查询客户端 — 与 XApiFetcher（推文抓取）职责分离。"""

import logging

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class XApiError(Exception):
    """X API 调用失败。"""


class XUserProfile(BaseModel):
    """X API 返回的用户资料。"""

    twitter_user_id: str
    display_name: str
    bio: str | None = None
    avatar_url: str | None = None
    followers_count: int = 0


async def lookup_user(bearer_token: str, handle: str) -> XUserProfile:
    """查询 X API 用户信息。

    调用 GET /2/users/by/username/{handle}，返回 XUserProfile。
    失败抛 XApiError。

    Args:
        bearer_token: X API Bearer Token
        handle: 推特用户名（不含 @）
    """
    url = f"https://api.x.com/2/users/by/username/{handle}"
    params = {"user.fields": "profile_image_url,description,public_metrics"}
    headers = {"Authorization": f"Bearer {bearer_token}"}

    async with httpx.AsyncClient(timeout=10.0) as client:
        try:
            response = await client.get(url, params=params, headers=headers)
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("X API 用户查询失败: handle=%s, error=%s", handle, exc)
            raise XApiError(f"X API 查询失败: {exc}") from exc

    payload = response.json()
    data = payload.get("data")
    if not data:
        logger.warning("X API 返回空数据: handle=%s, payload=%s", handle, payload)
        raise XApiError(f"X API 未找到用户: {handle}")

    metrics = data.get("public_metrics", {})
    return XUserProfile(
        twitter_user_id=data["id"],
        display_name=data["name"],
        bio=data.get("description"),
        avatar_url=data.get("profile_image_url"),
        followers_count=metrics.get("followers_count", 0),
    )
