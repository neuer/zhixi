"""US-011 — BaseFetcher 抽象基类 + XApiFetcher 测试。"""

from datetime import UTC, datetime

import httpx
import pytest
import respx

from app.fetcher import get_fetcher
from app.fetcher.base import BaseFetcher
from app.fetcher.x_api import XApiFetcher
from app.schemas.fetcher_types import RawTweet

# ──────────────────────────────────────────────────
# 工具函数
# ──────────────────────────────────────────────────


def make_tweet_data(
    tweet_id: str = "1001",
    author_id: str = "u1",
    text: str = "测试推文",
    created_at: str = "2026-03-18T10:00:00Z",
    like_count: int = 10,
    retweet_count: int = 2,
    reply_count: int = 1,
    referenced_tweets: list[dict] | None = None,
    attachments: dict | None = None,
) -> dict:
    """构造一条 X API tweet data 对象。"""
    data: dict = {
        "id": tweet_id,
        "author_id": author_id,
        "text": text,
        "created_at": created_at,
        "public_metrics": {
            "like_count": like_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
            "quote_count": 0,  # X API 返回但模型中不存在的字段
        },
    }
    if referenced_tweets is not None:
        data["referenced_tweets"] = referenced_tweets
    if attachments is not None:
        data["attachments"] = attachments
    return data


def make_api_response(
    tweets: list[dict],
    next_token: str | None = None,
    includes: dict | None = None,
) -> dict:
    """构造 X API 分页响应。"""
    resp: dict = {"data": tweets}
    meta: dict = {"result_count": len(tweets)}
    if next_token:
        meta["next_token"] = next_token
    resp["meta"] = meta
    if includes:
        resp["includes"] = includes
    return resp


SINCE = datetime(2026, 3, 18, 0, 0, 0, tzinfo=UTC)
UNTIL = datetime(2026, 3, 18, 23, 59, 59, tzinfo=UTC)
BASE_URL = "https://api.x.com/2"
USER_ID = "123456"
TWEETS_URL = f"{BASE_URL}/users/{USER_ID}/tweets"


# ──────────────────────────────────────────────────
# 1. BaseFetcher 不可直接实例化
# ──────────────────────────────────────────────────


def test_base_fetcher_cannot_be_instantiated():
    """BaseFetcher 是抽象类，无法直接实例化。"""
    with pytest.raises(TypeError):
        BaseFetcher()  # type: ignore[abstract]


# ──────────────────────────────────────────────────
# 2. 正常单页响应解析
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_single_page():
    """单页响应正常解析为 RawTweet 列表。"""
    tweet_data = make_tweet_data(tweet_id="1001", author_id="u1", text="单页推文")
    api_resp = make_api_response([tweet_data])

    respx.get(TWEETS_URL).mock(return_value=httpx.Response(200, json=api_resp))

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert len(tweets) == 1
    tweet = tweets[0]
    assert isinstance(tweet, RawTweet)
    assert tweet.tweet_id == "1001"
    assert tweet.author_id == "u1"
    assert tweet.text == "单页推文"
    assert tweet.public_metrics.like_count == 10
    assert tweet.public_metrics.retweet_count == 2
    assert tweet.public_metrics.reply_count == 1
    assert tweet.referenced_tweets == []
    assert tweet.media_urls == []
    assert tweet.tweet_url == "https://x.com/u1/status/1001"


# ──────────────────────────────────────────────────
# 3. 带 referenced_tweets 的响应（author_id 从 includes.tweets 提取）
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_with_referenced_tweets():
    """referenced_tweets 的 author_id 从 includes.tweets 补全。"""
    tweet_data = make_tweet_data(
        tweet_id="2001",
        author_id="u2",
        text="引用推文",
        referenced_tweets=[{"type": "quoted", "id": "9001"}],
    )
    includes = {
        "tweets": [
            {"id": "9001", "author_id": "orig_author", "text": "原始推文"},
        ]
    }
    api_resp = make_api_response([tweet_data], includes=includes)

    respx.get(TWEETS_URL).mock(return_value=httpx.Response(200, json=api_resp))

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert len(tweets) == 1
    ref = tweets[0].referenced_tweets[0]
    assert ref.type == "quoted"
    assert ref.id == "9001"
    assert ref.author_id == "orig_author"


# ──────────────────────────────────────────────────
# 4. 带 media 的响应（从 includes.media 提取 URL）
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_with_media():
    """includes.media 中的图片 URL 应附加到 RawTweet.media_urls。"""
    tweet_data = make_tweet_data(
        tweet_id="3001",
        author_id="u3",
        attachments={"media_keys": ["mk_1", "mk_2"]},
    )
    includes = {
        "media": [
            {"media_key": "mk_1", "type": "photo", "url": "https://pbs.twimg.com/img1.jpg"},
            {"media_key": "mk_2", "type": "photo", "url": "https://pbs.twimg.com/img2.jpg"},
        ]
    }
    api_resp = make_api_response([tweet_data], includes=includes)

    respx.get(TWEETS_URL).mock(return_value=httpx.Response(200, json=api_resp))

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert len(tweets) == 1
    assert tweets[0].media_urls == [
        "https://pbs.twimg.com/img1.jpg",
        "https://pbs.twimg.com/img2.jpg",
    ]


# ──────────────────────────────────────────────────
# 5. 2 页分页
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_two_pages():
    """meta.next_token 存在时继续请求下一页，汇总所有推文。"""
    page1 = make_api_response(
        [make_tweet_data(tweet_id="4001", author_id="u4")],
        next_token="TOKEN_PAGE2",
    )
    page2 = make_api_response(
        [make_tweet_data(tweet_id="4002", author_id="u4")],
    )

    route = respx.get(TWEETS_URL)
    route.side_effect = [
        httpx.Response(200, json=page1),
        httpx.Response(200, json=page2),
    ]

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert len(tweets) == 2
    assert tweets[0].tweet_id == "4001"
    assert tweets[1].tweet_id == "4002"


# ──────────────────────────────────────────────────
# 6. 空响应
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_empty_response():
    """API 返回空 data 时返回空列表。"""
    api_resp = {"data": [], "meta": {"result_count": 0}}

    respx.get(TWEETS_URL).mock(return_value=httpx.Response(200, json=api_resp))

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert tweets == []


# ──────────────────────────────────────────────────
# 7. 5 页分页上限
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_max_pages_limit():
    """分页不超过 MAX_PAGES=5，即使第 5 页仍有 next_token。"""

    def make_page(tweet_id: str, next_token: str | None) -> httpx.Response:
        return httpx.Response(
            200,
            json=make_api_response(
                [make_tweet_data(tweet_id=tweet_id, author_id="u5")],
                next_token=next_token,
            ),
        )

    responses = [
        make_page("5001", "T2"),
        make_page("5002", "T3"),
        make_page("5003", "T4"),
        make_page("5004", "T5"),
        make_page("5005", "T6"),  # 第 5 页仍有 next_token，但应停止
    ]

    route = respx.get(TWEETS_URL)
    route.side_effect = responses

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    # 只请求了 5 页
    assert len(tweets) == 5
    assert route.call_count == 5


# ──────────────────────────────────────────────────
# 8. get_fetcher 返回 BaseFetcher 实例
# ──────────────────────────────────────────────────


def test_get_fetcher_returns_base_fetcher_instance():
    """get_fetcher 工厂函数返回 BaseFetcher 的实例。"""
    fetcher = get_fetcher(bearer_token="test_token")
    assert isinstance(fetcher, BaseFetcher)


# ──────────────────────────────────────────────────
# 9. _parse_tweet 解析失败边界
# ──────────────────────────────────────────────────


class TestParseTweetEdgeCases:
    """_parse_tweet 字段缺失和格式异常测试。"""

    def _make_fetcher(self) -> XApiFetcher:
        return XApiFetcher(bearer_token="test_token")

    def test_missing_author_id_returns_none(self):
        """缺少 author_id → 返回 None。"""
        fetcher = self._make_fetcher()
        raw: dict[str, object] = {
            "id": "1001",
            "text": "hello",
            "created_at": "2026-03-18T10:00:00Z",
        }
        result = fetcher._parse_tweet(raw, {}, {})
        assert result is None

    def test_missing_text_returns_none(self):
        """缺少 text → 返回 None。"""
        fetcher = self._make_fetcher()
        raw: dict[str, object] = {
            "id": "1001",
            "author_id": "u1",
            "created_at": "2026-03-18T10:00:00Z",
        }
        result = fetcher._parse_tweet(raw, {}, {})
        assert result is None

    def test_missing_created_at_returns_none(self):
        """缺少 created_at → 返回 None。"""
        fetcher = self._make_fetcher()
        raw: dict[str, object] = {"id": "1001", "author_id": "u1", "text": "hello"}
        result = fetcher._parse_tweet(raw, {}, {})
        assert result is None

    def test_invalid_created_at_format_returns_none(self):
        """created_at 格式异常 → 返回 None。"""
        fetcher = self._make_fetcher()
        raw: dict[str, object] = {
            "id": "1001",
            "author_id": "u1",
            "text": "hello",
            "created_at": "not-a-date",
        }
        result = fetcher._parse_tweet(raw, {}, {})
        assert result is None

    def test_complete_data_returns_raw_tweet(self):
        """完整数据 → 返回 RawTweet。"""
        fetcher = self._make_fetcher()
        raw = make_tweet_data()
        result = fetcher._parse_tweet(raw, {}, {})
        assert result is not None
        assert isinstance(result, RawTweet)
        assert result.tweet_id == "1001"


# ──────────────────────────────────────────────────
# 10. 5xx HTTP 错误重试
# ──────────────────────────────────────────────────


@respx.mock
async def test_retry_on_5xx_then_success():
    """5xx 服务端错误应纳入重试，后续成功则正常返回。"""
    tweet_data = make_tweet_data(tweet_id="6001", author_id="u6")
    api_resp = make_api_response([tweet_data])

    route = respx.get(TWEETS_URL)
    route.side_effect = [
        httpx.Response(502, text="Bad Gateway"),
        httpx.Response(200, json=api_resp),
    ]

    fetcher = XApiFetcher(bearer_token="test_token")
    tweets = await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert len(tweets) == 1
    assert tweets[0].tweet_id == "6001"
    assert route.call_count == 2


@respx.mock
async def test_retry_on_5xx_exhausted():
    """5xx 持续失败耗尽重试 → 抛出 HTTPStatusError。"""
    route = respx.get(TWEETS_URL)
    route.side_effect = [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(503, text="Service Unavailable"),
    ]

    fetcher = XApiFetcher(bearer_token="test_token")
    with pytest.raises(httpx.HTTPStatusError):
        await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()


@respx.mock
async def test_4xx_not_retried():
    """4xx 客户端错误（非 429）不重试，立即抛出。"""
    respx.get(TWEETS_URL).mock(return_value=httpx.Response(403, text="Forbidden"))

    fetcher = XApiFetcher(bearer_token="test_token")
    with pytest.raises(httpx.HTTPStatusError) as exc_info:
        await fetcher.fetch_user_tweets(USER_ID, SINCE, UNTIL)
    await fetcher.close()

    assert exc_info.value.response.status_code == 403
