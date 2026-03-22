"""调试路由 — X API 连通性检测、用户查询、推文抓取。"""

import logging
import time

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_admin
from app.config import get_secret_config
from app.database import get_db
from app.fetcher.x_api import enrich_tweet_text
from app.lib.timing import elapsed_ms
from app.schemas.debug_types import (
    DebugXPingResponse,
    DebugXTweetResponse,
    DebugXTweetsRequest,
    DebugXTweetsResponse,
    DebugXUserResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()


async def _get_bearer_token(db: AsyncSession) -> str:
    """获取 X API Bearer Token，未配置时抛 400。"""
    token = await get_secret_config(db, "x_api_bearer_token")
    if not token:
        raise HTTPException(status_code=400, detail="X API Bearer Token 未配置")
    return token


@router.get("/x/ping", response_model=DebugXPingResponse)
async def debug_x_ping(
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> DebugXPingResponse:
    """检测 X API 连通性 — GET /2/users/by/username/x。

    /2/users/me 需要 OAuth User Context，Bearer Token 不支持。
    改用查询公开用户信息的端点来验证 Token 有效性。
    """
    token = await get_secret_config(db, "x_api_bearer_token")
    if not token:
        return DebugXPingResponse(status="unconfigured")

    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://api.x.com/2/users/by/username/x",
                headers={"Authorization": f"Bearer {token}"},
            )
            resp.raise_for_status()
            raw = resp.json()
    except httpx.HTTPStatusError as exc:
        return DebugXPingResponse(
            status="error",
            latency_ms=elapsed_ms(start),
            raw_response=exc.response.json(),
        )
    except httpx.HTTPError as exc:
        return DebugXPingResponse(
            status="error",
            latency_ms=elapsed_ms(start),
            raw_response={"error": str(exc)},
        )

    return DebugXPingResponse(
        status="ok",
        latency_ms=elapsed_ms(start),
        raw_response=raw,
    )


@router.get("/x/user/{handle}", response_model=DebugXUserResponse)
async def debug_x_user(
    handle: str,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> DebugXUserResponse:
    """查询 X API 用户信息，返回解析结果 + 原始 JSON。"""
    token = await _get_bearer_token(db)

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.x.com/2/users/by/username/{handle}",
            headers={"Authorization": f"Bearer {token}"},
            params={"user.fields": "profile_image_url,description,public_metrics"},
        )
        raw = resp.json()
        latency = elapsed_ms(start)

    data = raw.get("data")
    if not data:
        return DebugXUserResponse(user=None, raw_response=raw, latency_ms=latency)

    from app.clients.x_client import XUserProfile

    metrics = data.get("public_metrics", {})
    user = XUserProfile(
        twitter_user_id=data["id"],
        display_name=data["name"],
        bio=data.get("description"),
        avatar_url=data.get("profile_image_url"),
        followers_count=metrics.get("followers_count", 0),
    )
    return DebugXUserResponse(user=user, raw_response=raw, latency_ms=latency)


@router.post("/x/tweets", response_model=DebugXTweetsResponse)
async def debug_x_tweets(
    body: DebugXTweetsRequest,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> DebugXTweetsResponse:
    """抓取指定用户近 N 小时的推文。

    流程：先查用户 ID，再调推文列表接口。不写数据库。
    """
    token = await _get_bearer_token(db)
    start = time.monotonic()

    # 1. 查询用户 ID
    async with httpx.AsyncClient(timeout=10.0) as client:
        user_resp = await client.get(
            f"https://api.x.com/2/users/by/username/{body.handle}",
            headers={"Authorization": f"Bearer {token}"},
            params={"user.fields": "id"},
        )
        user_payload = user_resp.json()

    user_data = user_payload.get("data")
    if not user_data:
        return DebugXTweetsResponse(
            tweets=[],
            count=0,
            raw_response=user_payload,
            latency_ms=elapsed_ms(start),
        )

    user_id = user_data["id"]

    # 2. 抓取推文
    from datetime import UTC, datetime, timedelta

    from app.fetcher.x_api import XApiFetcher

    now = datetime.now(UTC)
    since = now - timedelta(hours=body.hours_back)

    # 先直接调 X API 拿原始响应，再解析
    raw_payload: dict[str, object] = {}
    async with httpx.AsyncClient(
        base_url="https://api.x.com/2",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30.0,
    ) as client:
        try:
            resp = await client.get(
                f"/users/{user_id}/tweets",
                params={
                    "exclude": "retweets,replies",
                    "max_results": "100",
                    "start_time": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "end_time": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "tweet.fields": "author_id,created_at,public_metrics,attachments,referenced_tweets,entities,note_tweet,article",
                    "expansions": "attachments.media_keys,referenced_tweets.id",
                    "media.fields": "url,type",
                },
            )
            raw_payload = resp.json()
        except Exception as exc:
            return DebugXTweetsResponse(
                tweets=[],
                count=0,
                raw_response={"error": str(exc)},
                latency_ms=elapsed_ms(start),
            )

    latency = elapsed_ms(start)

    # API 返回错误（如 403 Free 层级不支持）时直接返回原始响应
    if "data" not in raw_payload:
        return DebugXTweetsResponse(
            tweets=[],
            count=0,
            raw_response=raw_payload,
            latency_ms=latency,
        )

    # 解析推文
    async with XApiFetcher(bearer_token=token) as fetcher:
        included_tweets, media_url_map = fetcher._build_includes_index(raw_payload)
        tweets = []
        data_list = raw_payload.get("data", [])
        if not isinstance(data_list, list):
            data_list = []
        for raw_tweet in data_list:
            if not isinstance(raw_tweet, dict):
                continue
            enrich_tweet_text(raw_tweet)
            parsed = fetcher._parse_tweet(raw_tweet, included_tweets, media_url_map)
            if parsed is not None:
                tweets.append(parsed)

    return DebugXTweetsResponse(
        tweets=tweets,
        count=len(tweets),
        raw_response=raw_payload,
        latency_ms=latency,
    )


@router.get("/x/tweet/{tweet_id}", response_model=DebugXTweetResponse)
async def debug_x_tweet(
    tweet_id: str,
    db: AsyncSession = Depends(get_db),
    _admin: str = Depends(get_current_admin),
) -> DebugXTweetResponse:
    """查询单条推文，返回解析结果 + 原始 JSON。"""
    token = await _get_bearer_token(db)

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            f"https://api.x.com/2/tweets/{tweet_id}",
            headers={"Authorization": f"Bearer {token}"},
            params={
                "tweet.fields": "author_id,created_at,public_metrics,attachments,referenced_tweets,entities,note_tweet,article",
                "expansions": "attachments.media_keys,referenced_tweets.id",
                "media.fields": "url,type",
            },
        )
        raw = resp.json()
        latency = elapsed_ms(start)

    data = raw.get("data")
    if not data:
        return DebugXTweetResponse(tweet=None, raw_response=raw, latency_ms=latency)

    # 复用 XApiFetcher 的解析逻辑
    from app.fetcher.x_api import XApiFetcher

    async with XApiFetcher(bearer_token=token) as fetcher:
        included_tweets, media_url_map = fetcher._build_includes_index(raw)
        if isinstance(data, dict):
            enrich_tweet_text(data)
        tweet = fetcher._parse_tweet(data, included_tweets, media_url_map)

    return DebugXTweetResponse(tweet=tweet, raw_response=raw, latency_ms=latency)
