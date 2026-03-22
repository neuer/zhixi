"""US-013/014/015 — 每日自动抓取 + 容错 + 限流 测试。"""

import json
from datetime import UTC, date, datetime

import httpx
import respx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_fetch_window
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.fetch_log import FetchLog
from app.models.tweet import Tweet
from app.schemas.fetcher_types import FetchResult
from app.services.fetch_service import FetchService
from tests.factories import create_account

# ──────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────

DIGEST_DATE = date(2026, 3, 19)
SINCE, UNTIL = get_fetch_window(DIGEST_DATE)
BASE_URL = "https://api.x.com/2"


def _tweets_url(user_id: str) -> str:
    return f"{BASE_URL}/users/{user_id}/tweets"


async def _seed_accounts(
    db: AsyncSession,
    count: int = 2,
    *,
    with_user_id: bool = True,
) -> list[TwitterAccount]:
    """预置活跃账号（委托工厂函数）。"""
    accounts: list[TwitterAccount] = []
    for i in range(1, count + 1):
        acct = await create_account(
            db,
            twitter_handle=f"user{i}",
            twitter_user_id=f"uid_{i}" if with_user_id else None,
            display_name=f"User {i}",
        )
        accounts.append(acct)
    return accounts


def _make_tweet_data(
    tweet_id: str = "1001",
    author_id: str = "u1",
    text: str = "测试推文",
    created_at: str = "2026-03-18T10:00:00Z",
    like_count: int = 10,
    retweet_count: int = 2,
    reply_count: int = 1,
    referenced_tweets: list[dict] | None = None,
) -> dict:
    """构造一条 X API tweet data。"""
    data: dict = {
        "id": tweet_id,
        "author_id": author_id,
        "text": text,
        "created_at": created_at,
        "public_metrics": {
            "like_count": like_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
        },
    }
    if referenced_tweets is not None:
        data["referenced_tweets"] = referenced_tweets
    return data


def _make_api_response(
    tweets: list[dict],
    next_token: str | None = None,
    includes: dict | None = None,
) -> dict:
    """构造 X API 分页响应。"""
    resp: dict = {"data": tweets, "meta": {"result_count": len(tweets)}}
    if next_token:
        resp["meta"]["next_token"] = next_token
    if includes:
        resp["includes"] = includes
    return resp


# ──────────────────────────────────────────────────
# US-013: 正常抓取
# ──────────────────────────────────────────────────


@respx.mock
async def test_normal_fetch_two_accounts(db: AsyncSession):
    """2 个活跃账号各返回推文 → tweets 表有数据。"""
    await _seed_accounts(db, 2)

    # Mock 账号 1 返回 1 条推文
    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="t1", author_id="uid_1", text="推文A"),
                ]
            ),
        )
    )
    # Mock 账号 2 返回 1 条推文
    respx.get(_tweets_url("uid_2")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="t2", author_id="uid_2", text="推文B"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert isinstance(result, FetchResult)
    assert result.total_accounts == 2
    assert result.new_tweets_count == 2
    assert result.fail_count == 0

    # 验证 DB 中推文数
    rows = (await db.execute(select(Tweet))).scalars().all()
    assert len(rows) == 2


# ──────────────────────────────────────────────────
# US-013: 推文分类过滤
# ──────────────────────────────────────────────────


@respx.mock
async def test_classify_and_filter(db: AsyncSession):
    """混合 5 种类型推文 → 只保留 ORIGINAL/SELF_REPLY/QUOTE。"""
    await _seed_accounts(db, 1)

    # ORIGINAL（无 referenced_tweets）
    original = _make_tweet_data(tweet_id="t_orig", author_id="uid_1")
    # SELF_REPLY（replied_to 同作者）
    self_reply = _make_tweet_data(
        tweet_id="t_self",
        author_id="uid_1",
        referenced_tweets=[{"type": "replied_to", "id": "ref1"}],
    )
    # QUOTE
    quote = _make_tweet_data(
        tweet_id="t_quote",
        author_id="uid_1",
        referenced_tweets=[{"type": "quoted", "id": "ref2"}],
    )
    # RETWEET（应过滤，但 X API exclude=retweets 已排除，测试分类器兜底）
    retweet = _make_tweet_data(
        tweet_id="t_rt",
        author_id="uid_1",
        referenced_tweets=[{"type": "retweeted", "id": "ref3"}],
    )
    # REPLY（replied_to 不同作者）
    reply = _make_tweet_data(
        tweet_id="t_reply",
        author_id="uid_1",
        referenced_tweets=[{"type": "replied_to", "id": "ref4"}],
    )

    includes = {
        "tweets": [
            {"id": "ref1", "author_id": "uid_1"},  # SELF_REPLY
            {"id": "ref2", "author_id": "other"},  # QUOTE
            {"id": "ref3", "author_id": "other"},  # RETWEET
            {"id": "ref4", "author_id": "other"},  # REPLY
        ]
    }

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [original, self_reply, quote, retweet, reply],
                includes=includes,
            ),
        )
    )

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    # 只保留 ORIGINAL + SELF_REPLY + QUOTE = 3 条
    assert result.new_tweets_count == 3

    rows = (await db.execute(select(Tweet))).scalars().all()
    tweet_ids = {r.tweet_id for r in rows}
    assert tweet_ids == {"t_orig", "t_self", "t_quote"}


# ──────────────────────────────────────────────────
# US-013: tweet_id 去重（跨账号）
# ──────────────────────────────────────────────────


@respx.mock
async def test_dedup_across_accounts(db: AsyncSession):
    """两个账号返回相同 tweet_id → 只保存 1 条。"""
    await _seed_accounts(db, 2)

    same_tweet = _make_tweet_data(tweet_id="dup_1", author_id="uid_1")

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(200, json=_make_api_response([same_tweet]))
    )
    respx.get(_tweets_url("uid_2")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="dup_1", author_id="uid_2"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.new_tweets_count == 1
    rows = (await db.execute(select(Tweet))).scalars().all()
    assert len(rows) == 1


# ──────────────────────────────────────────────────
# US-013: DB 已有推文不重复插入
# ──────────────────────────────────────────────────


@respx.mock
async def test_dedup_against_existing_db(db: AsyncSession):
    """DB 中已有的 tweet_id → 不重复插入。"""
    accounts = await _seed_accounts(db, 1)

    # 预先插入一条推文
    existing = Tweet(
        tweet_id="existing_1",
        account_id=accounts[0].id,
        original_text="已存在",
        tweet_time=datetime(2026, 3, 18, 10, 0, 0, tzinfo=UTC),
        digest_date=DIGEST_DATE,
    )
    db.add(existing)
    await db.flush()

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="existing_1", author_id="uid_1"),
                    _make_tweet_data(tweet_id="new_1", author_id="uid_1"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.new_tweets_count == 1
    rows = (await db.execute(select(Tweet))).scalars().all()
    assert len(rows) == 2  # 1 existing + 1 new


# ──────────────────────────────────────────────────
# US-013: 无活跃账号
# ──────────────────────────────────────────────────


async def test_no_active_accounts(db: AsyncSession):
    """无活跃账号 → 空结果。"""
    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.total_accounts == 0
    assert result.new_tweets_count == 0
    assert result.fail_count == 0


# ──────────────────────────────────────────────────
# US-013: 账号返回空列表
# ──────────────────────────────────────────────────


@respx.mock
async def test_account_empty_response(db: AsyncSession):
    """账号无新推文 → new_tweets=0，不报错。"""
    await _seed_accounts(db, 1)

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(200, json={"data": [], "meta": {"result_count": 0}})
    )

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.new_tweets_count == 0
    assert result.fail_count == 0
    assert result.total_accounts == 1


# ──────────────────────────────────────────────────
# US-014: 单账号失败容错
# ──────────────────────────────────────────────────


@respx.mock
async def test_single_account_failure_continues(db: AsyncSession):
    """一个账号 500 错误 → 记录失败，继续抓取其他。"""
    await _seed_accounts(db, 2)

    # 账号 1 返回 500
    respx.get(_tweets_url("uid_1")).mock(return_value=httpx.Response(500))
    # 账号 2 正常
    respx.get(_tweets_url("uid_2")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="ok_1", author_id="uid_2"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.fail_count == 1
    assert result.new_tweets_count == 1
    assert result.total_accounts == 2


# ──────────────────────────────────────────────────
# US-014: 全部账号失败
# ──────────────────────────────────────────────────


@respx.mock
async def test_all_accounts_fail(db: AsyncSession):
    """全部账号失败 → fail_count == total_accounts。"""
    await _seed_accounts(db, 2)

    respx.get(_tweets_url("uid_1")).mock(return_value=httpx.Response(500))
    respx.get(_tweets_url("uid_2")).mock(return_value=httpx.Response(500))

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.fail_count == 2
    assert result.total_accounts == 2
    assert result.new_tweets_count == 0


# ──────────────────────────────────────────────────
# US-014: error_details JSON 格式
# ──────────────────────────────────────────────────


@respx.mock
async def test_error_details_json(db: AsyncSession):
    """失败账号的 error_details 是有效 JSON，包含账号信息。"""
    await _seed_accounts(db, 1)

    respx.get(_tweets_url("uid_1")).mock(return_value=httpx.Response(500))

    svc = FetchService(db)
    await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    log = (await db.execute(select(FetchLog))).scalar_one()
    assert log.error_details is not None
    errors = json.loads(log.error_details)
    assert isinstance(errors, list)
    assert len(errors) == 1
    assert "handle" in errors[0]
    assert errors[0]["handle"] == "user1"


# ──────────────────────────────────────────────────
# US-015: HTTP 429 退避重试成功
# ──────────────────────────────────────────────────


@respx.mock
async def test_rate_limit_429_retry_success(db: AsyncSession):
    """首次 429 → 退避重试 → 第二次成功。

    I-36 局限性说明：此测试仅验证重试最终成功，未验证退避时间间隔是否符合预期。
    验证退避需要 mock asyncio.sleep 并断言调用参数，暂不改造。
    """
    await _seed_accounts(db, 1)

    route = respx.get(_tweets_url("uid_1"))
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="retry_ok", author_id="uid_1"),
                ]
            ),
        ),
    ]

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.new_tweets_count == 1
    assert result.fail_count == 0


# ──────────────────────────────────────────────────
# US-015: 429 超过 3 次 → 失败
# ──────────────────────────────────────────────────


@respx.mock
async def test_rate_limit_429_exhausted(db: AsyncSession):
    """连续 4 次 429（初始 + 3 次重试）→ 账号标记失败。"""
    await _seed_accounts(db, 1)

    respx.get(_tweets_url("uid_1")).mock(return_value=httpx.Response(429))

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.fail_count == 1
    assert result.new_tweets_count == 0


# ──────────────────────────────────────────────────
# US-013: fetch_log 字段完整
# ──────────────────────────────────────────────────


@respx.mock
async def test_fetch_log_fields(db: AsyncSession):
    """fetch_log 记录字段完整且正确。"""
    await _seed_accounts(db, 2)

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="fl1", author_id="uid_1"),
                ]
            ),
        )
    )
    respx.get(_tweets_url("uid_2")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="fl2", author_id="uid_2"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    log = (await db.execute(select(FetchLog))).scalar_one()
    assert log.fetch_date == DIGEST_DATE
    assert log.total_accounts == 2
    assert log.success_count == 2
    assert log.fail_count == 0
    assert log.new_tweets == 2
    assert log.started_at is not None
    assert log.finished_at is not None
    assert log.finished_at >= log.started_at


# ──────────────────────────────────────────────────
# US-013: api_cost_log 记录
# ──────────────────────────────────────────────────


@respx.mock
async def test_api_cost_log(db: AsyncSession):
    """每个成功账号写入一条 api_cost_log。"""
    await _seed_accounts(db, 2)

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="cl1", author_id="uid_1"),
                ]
            ),
        )
    )
    respx.get(_tweets_url("uid_2")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="cl2", author_id="uid_2"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    logs = (await db.execute(select(ApiCostLog))).scalars().all()
    assert len(logs) == 2
    for log in logs:
        assert log.service == "x"
        assert log.call_type == "fetch_tweets"
        assert log.success is True


# ──────────────────────────────────────────────────
# US-013: last_fetch_at 更新
# ──────────────────────────────────────────────────


@respx.mock
async def test_last_fetch_at_updated(db: AsyncSession):
    """成功抓取后更新账号的 last_fetch_at。"""
    accounts = await _seed_accounts(db, 1)
    assert accounts[0].last_fetch_at is None

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="lf1", author_id="uid_1"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    await db.refresh(accounts[0])
    assert accounts[0].last_fetch_at is not None


# ──────────────────────────────────────────────────
# US-013: tweet_url 使用 twitter_handle
# ──────────────────────────────────────────────────


@respx.mock
async def test_tweet_url_uses_handle(db: AsyncSession):
    """tweet_url 使用 twitter_handle（而非 numeric user_id）构建。"""
    await _seed_accounts(db, 1)

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response(
                [
                    _make_tweet_data(tweet_id="url_1", author_id="uid_1"),
                ]
            ),
        )
    )

    svc = FetchService(db)
    await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    tweet = (await db.execute(select(Tweet))).scalar_one()
    assert tweet.tweet_url == "https://x.com/user1/status/url_1"


# ──────────────────────────────────────────────────
# US-013: is_quote_tweet / is_self_thread_reply
# ──────────────────────────────────────────────────


@respx.mock
async def test_tweet_type_flags(db: AsyncSession):
    """is_quote_tweet 和 is_self_thread_reply 标志正确设置。"""
    await _seed_accounts(db, 1)

    original = _make_tweet_data(tweet_id="f_orig", author_id="uid_1")
    self_reply = _make_tweet_data(
        tweet_id="f_self",
        author_id="uid_1",
        referenced_tweets=[{"type": "replied_to", "id": "ref1"}],
    )
    quote = _make_tweet_data(
        tweet_id="f_quote",
        author_id="uid_1",
        referenced_tweets=[{"type": "quoted", "id": "ref2"}],
    )
    includes = {
        "tweets": [
            {"id": "ref1", "author_id": "uid_1"},
            {"id": "ref2", "author_id": "other"},
        ]
    }

    respx.get(_tweets_url("uid_1")).mock(
        return_value=httpx.Response(
            200,
            json=_make_api_response([original, self_reply, quote], includes=includes),
        )
    )

    svc = FetchService(db)
    await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    rows = (await db.execute(select(Tweet).order_by(Tweet.tweet_id))).scalars().all()
    by_id = {r.tweet_id: r for r in rows}

    assert by_id["f_orig"].is_quote_tweet is False
    assert by_id["f_orig"].is_self_thread_reply is False
    assert by_id["f_self"].is_quote_tweet is False
    assert by_id["f_self"].is_self_thread_reply is True
    assert by_id["f_quote"].is_quote_tweet is True
    assert by_id["f_quote"].is_self_thread_reply is False


# ──────────────────────────────────────────────────
# 边界：无 twitter_user_id 的账号跳过
# ──────────────────────────────────────────────────


@respx.mock
async def test_skip_account_without_user_id(db: AsyncSession):
    """twitter_user_id 为空的账号跳过抓取。"""
    await _seed_accounts(db, 1, with_user_id=False)

    svc = FetchService(db)
    result = await svc.run_daily_fetch(digest_date=DIGEST_DATE)

    assert result.total_accounts == 1
    assert result.skipped_count == 1
    assert result.new_tweets_count == 0
