"""DigestService 集成测试（US-023 + US-024）。"""

import json
from datetime import UTC, date, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.clients.claude_client import ClaudeClient
from app.digest.summary_prompts import DEFAULT_SUMMARY
from app.models.account import TwitterAccount
from app.models.api_cost_log import ApiCostLog
from app.models.digest_item import DigestItem
from app.models.topic import Topic
from app.models.tweet import Tweet
from app.schemas.client_types import ClaudeResponse
from app.services.digest_service import DigestService

DIGEST_DATE = date(2026, 3, 20)


# ──────────────────────────────────────────────────
# 辅助函数
# ──────────────────────────────────────────────────


def _mock_claude_response(content: str) -> ClaudeResponse:
    """构造模拟 ClaudeResponse。"""
    return ClaudeResponse(
        content=content,
        input_tokens=200,
        output_tokens=80,
        model="claude-sonnet-4-20250514",
        duration_ms=1500,
        estimated_cost=0.0018,
    )


def _make_service(db: AsyncSession, summary_text: str = "今日AI摘要") -> DigestService:
    """构造带 mock ClaudeClient 的 DigestService。"""
    client = AsyncMock(spec=ClaudeClient)
    client.complete = AsyncMock(return_value=_mock_claude_response(summary_text))
    return DigestService(db, claude_client=client)


async def _seed_account(
    db: AsyncSession,
    handle: str = "testuser",
    display_name: str = "Test User",
    **overrides: object,
) -> TwitterAccount:
    """创建测试账号。"""
    defaults: dict[str, object] = {
        "twitter_handle": handle,
        "display_name": display_name,
        "bio": "AI researcher",
        "weight": 1.0,
        "is_active": True,
    }
    defaults.update(overrides)
    account = TwitterAccount(**defaults)
    db.add(account)
    await db.flush()
    return account


async def _seed_tweet(
    db: AsyncSession,
    account: TwitterAccount,
    tweet_id: str = "t1",
    *,
    heat_score: float = 50.0,
    title: str = "推文标题",
    translated_text: str = "推文翻译",
    ai_comment: str = "推文点评",
    topic_id: int | None = None,
    is_ai_relevant: bool = True,
    is_processed: bool = True,
) -> Tweet:
    """创建测试推文。"""
    tweet = Tweet(
        tweet_id=tweet_id,
        account_id=account.id,
        digest_date=DIGEST_DATE,
        original_text=f"Original text for {tweet_id}",
        tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        likes=100,
        retweets=20,
        replies=10,
        tweet_url=f"https://x.com/{account.twitter_handle}/status/{tweet_id}",
        source="auto",
        title=title,
        translated_text=translated_text,
        ai_comment=ai_comment,
        heat_score=heat_score,
        ai_importance_score=70.0,
        base_heat_score=60.0,
        is_ai_relevant=is_ai_relevant,
        is_processed=is_processed,
        topic_id=topic_id,
    )
    db.add(tweet)
    await db.flush()
    return tweet


async def _seed_topic(
    db: AsyncSession,
    topic_type: str = "aggregated",
    *,
    title: str = "话题标题",
    summary: str = "话题摘要",
    perspectives: str | None = None,
    ai_comment: str = "话题点评",
    heat_score: float = 60.0,
) -> Topic:
    """创建测试话题。"""
    topic = Topic(
        digest_date=DIGEST_DATE,
        type=topic_type,
        title=title,
        summary=summary,
        perspectives=perspectives,
        ai_comment=ai_comment,
        heat_score=heat_score,
        ai_importance_score=80.0,
        tweet_count=2,
    )
    db.add(topic)
    await db.flush()
    return topic


# ──────────────────────────────────────────────────
# 测试
# ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_generate_daily_digest_mixed(db: AsyncSession) -> None:
    """标准场景：混合推文和话题。"""
    svc = _make_service(db)

    # 种子数据
    acct1 = await _seed_account(db, handle="alice", display_name="Alice")
    acct2 = await _seed_account(db, handle="bob", display_name="Bob")
    acct3 = await _seed_account(db, handle="carol", display_name="Carol")

    # 3 条独立推文（topic_id=null）
    await _seed_tweet(db, acct1, "tw1", heat_score=90.0, title="GPT-5 发布")
    await _seed_tweet(db, acct2, "tw2", heat_score=70.0, title="Gemini 2 更新")
    await _seed_tweet(db, acct3, "tw3", heat_score=50.0, title="LLM 小技巧")

    # 1 个 aggregated 话题（2 条成员推文）
    perspectives_json = json.dumps(
        [
            {"author": "Alice", "handle": "alice", "viewpoint": "观点A"},
            {"author": "Bob", "handle": "bob", "viewpoint": "观点B"},
        ],
        ensure_ascii=False,
    )
    topic_agg = await _seed_topic(
        db,
        "aggregated",
        title="AI安全热议",
        summary="各方激烈讨论",
        perspectives=perspectives_json,
        heat_score=85.0,
    )
    tw_agg1 = await _seed_tweet(
        db, acct1, "tw_a1", heat_score=80.0, title="AI安全1", topic_id=topic_agg.id
    )
    tw_agg2 = await _seed_tweet(
        db, acct2, "tw_a2", heat_score=75.0, title="AI安全2", topic_id=topic_agg.id
    )

    # 1 个 thread 话题（2 条成员推文）
    topic_thread = await _seed_topic(
        db,
        "thread",
        title="Transformer 深度分析",
        summary="Thread 中文翻译全文",
        heat_score=80.0,
    )
    tw_th1 = await _seed_tweet(
        db, acct3, "tw_t1", heat_score=78.0, title="Thread 1", topic_id=topic_thread.id
    )
    tw_th2 = await _seed_tweet(
        db, acct3, "tw_t2", heat_score=76.0, title="Thread 2", topic_id=topic_thread.id
    )

    await db.commit()

    # 执行
    digest = await svc.generate_daily_digest(DIGEST_DATE)

    # 验证 DailyDigest
    assert digest.digest_date == DIGEST_DATE
    assert digest.version == 1
    assert digest.status == "draft"
    assert digest.is_current is True
    assert digest.summary is not None

    # 验证 digest_items 数量：3 独立推文 + 2 话题 = 5
    items_result = await db.execute(
        select(DigestItem)
        .where(DigestItem.digest_id == digest.id)
        .order_by(DigestItem.display_order)
    )
    items = list(items_result.scalars().all())
    assert len(items) == 5
    assert digest.item_count == 5

    # 验证按 heat_score 降序：tw1(90) > agg(85) > thread(80) > tw2(70) > tw3(50)
    assert items[0].snapshot_heat_score == 90.0
    assert items[1].snapshot_heat_score == 85.0
    assert items[2].snapshot_heat_score == 80.0
    assert items[3].snapshot_heat_score == 70.0
    assert items[4].snapshot_heat_score == 50.0

    # 验证 display_order 从 1 开始连续
    for i, item in enumerate(items):
        assert item.display_order == i + 1

    # 验证成员推文不单独创建 item
    item_types_refs = [(it.item_type, it.item_ref_id) for it in items]
    assert ("tweet", tw_agg1.id) not in item_types_refs
    assert ("tweet", tw_agg2.id) not in item_types_refs
    assert ("tweet", tw_th1.id) not in item_types_refs
    assert ("tweet", tw_th2.id) not in item_types_refs


@pytest.mark.asyncio
async def test_tweet_snapshot_mapping(db: AsyncSession) -> None:
    """验证 tweet 类型的 snapshot 字段映射。"""
    svc = _make_service(db)

    acct = await _seed_account(db, handle="alice", display_name="Alice Wang")
    tweet = await _seed_tweet(
        db,
        acct,
        "tw_snap",
        heat_score=80.0,
        title="测试标题",
        translated_text="测试翻译",
        ai_comment="测试点评",
    )
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
    item = items_result.scalars().first()
    assert item is not None

    assert item.item_type == "tweet"
    assert item.item_ref_id == tweet.id
    assert item.snapshot_title == "测试标题"
    assert item.snapshot_translation == "测试翻译"
    assert item.snapshot_comment == "测试点评"
    assert item.snapshot_heat_score == 80.0
    assert item.snapshot_author_name == "Alice Wang"
    assert item.snapshot_author_handle == "alice"
    assert item.snapshot_tweet_url == tweet.tweet_url
    # SQLite 读回 datetime 丢失 tzinfo，比较时去除时区
    assert item.snapshot_tweet_time is not None
    assert item.snapshot_tweet_time.replace(tzinfo=None) == tweet.tweet_time.replace(tzinfo=None)
    assert item.snapshot_summary is None
    assert item.snapshot_perspectives is None
    assert item.snapshot_topic_type is None
    assert item.snapshot_source_tweets is None


@pytest.mark.asyncio
async def test_aggregated_topic_snapshot_mapping(db: AsyncSession) -> None:
    """验证 aggregated topic 的 snapshot 字段映射。"""
    svc = _make_service(db)

    acct1 = await _seed_account(db, handle="alice", display_name="Alice")
    acct2 = await _seed_account(db, handle="bob", display_name="Bob")

    perspectives_json = json.dumps(
        [{"author": "Alice", "handle": "alice", "viewpoint": "观点"}],
        ensure_ascii=False,
    )
    topic = await _seed_topic(
        db,
        "aggregated",
        title="聚合标题",
        summary="聚合摘要",
        perspectives=perspectives_json,
        ai_comment="聚合点评",
        heat_score=75.0,
    )
    await _seed_tweet(db, acct1, "agg1", heat_score=70.0, topic_id=topic.id)
    await _seed_tweet(db, acct2, "agg2", heat_score=65.0, topic_id=topic.id)
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
    item = items_result.scalars().first()
    assert item is not None

    assert item.item_type == "topic"
    assert item.item_ref_id == topic.id
    assert item.snapshot_title == "聚合标题"
    assert item.snapshot_summary == "聚合摘要"
    assert item.snapshot_comment == "聚合点评"
    assert item.snapshot_perspectives == perspectives_json
    assert item.snapshot_heat_score == 75.0
    assert item.snapshot_topic_type == "aggregated"
    assert item.snapshot_translation is None
    assert item.snapshot_author_name is None
    assert item.snapshot_author_handle is None
    assert item.snapshot_tweet_url is None
    assert item.snapshot_tweet_time is None

    # 验证 source_tweets JSON
    assert item.snapshot_source_tweets is not None
    source_tweets = json.loads(item.snapshot_source_tweets)
    handles = {s["handle"] for s in source_tweets}
    assert handles == {"alice", "bob"}
    assert all("tweet_url" in s for s in source_tweets)


@pytest.mark.asyncio
async def test_thread_topic_snapshot_mapping(db: AsyncSession) -> None:
    """验证 thread topic 的 snapshot 字段映射。"""
    svc = _make_service(db)

    acct = await _seed_account(db, handle="carol", display_name="Carol Lee")
    topic = await _seed_topic(
        db,
        "thread",
        title="Thread 标题",
        summary="Thread 中文翻译全文",
        ai_comment="Thread 点评",
        heat_score=82.0,
    )
    # Thread 第一条推文（tweet_time 最早）
    tw1 = await _seed_tweet(db, acct, "th1", heat_score=80.0, topic_id=topic.id)
    await _seed_tweet(db, acct, "th2", heat_score=78.0, topic_id=topic.id)
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
    item = items_result.scalars().first()
    assert item is not None

    assert item.item_type == "topic"
    assert item.item_ref_id == topic.id
    assert item.snapshot_title == "Thread 标题"
    assert item.snapshot_translation == "Thread 中文翻译全文"
    assert item.snapshot_comment == "Thread 点评"
    assert item.snapshot_heat_score == 82.0
    assert item.snapshot_topic_type == "thread"
    # Thread 作者 = 第一条推文作者
    assert item.snapshot_author_name == "Carol Lee"
    assert item.snapshot_author_handle == "carol"
    assert item.snapshot_tweet_url == tw1.tweet_url
    assert item.snapshot_summary is None
    assert item.snapshot_perspectives is None
    assert item.snapshot_source_tweets is None


@pytest.mark.asyncio
async def test_summary_generation_and_cost_log(db: AsyncSession) -> None:
    """验证导读摘要生成和 api_cost_log 记录。"""
    svc = _make_service(db, summary_text="今日 AI 焦点：GPT-5 正式发布")

    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=90.0, title="GPT-5")
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    assert digest.summary == "今日 AI 焦点：GPT-5 正式发布"

    # 验证 api_cost_log
    cost_result = await db.execute(select(ApiCostLog).where(ApiCostLog.call_type == "summary"))
    cost_log = cost_result.scalars().first()
    assert cost_log is not None
    assert cost_log.service == "claude"
    assert cost_log.call_date == DIGEST_DATE
    assert cost_log.input_tokens == 200
    assert cost_log.estimated_cost == 0.0018


@pytest.mark.asyncio
async def test_empty_digest_no_processed_tweets(db: AsyncSession) -> None:
    """边界条件：所有推文 is_ai_relevant=false → 空草稿。"""
    svc = _make_service(db)

    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "tw1", heat_score=80.0, is_ai_relevant=False)
    await _seed_tweet(db, acct, "tw2", heat_score=70.0, is_ai_relevant=False)
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    assert digest.item_count == 0
    assert digest.summary == DEFAULT_SUMMARY

    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
    assert list(items_result.scalars().all()) == []


@pytest.mark.asyncio
async def test_all_tweets_aggregated(db: AsyncSession) -> None:
    """边界条件：所有推文都有 topic_id → 只创建 topic 类型 items。"""
    svc = _make_service(db)

    acct = await _seed_account(db)
    topic = await _seed_topic(db, "aggregated", heat_score=80.0)
    await _seed_tweet(db, acct, "tw1", heat_score=75.0, topic_id=topic.id)
    await _seed_tweet(db, acct, "tw2", heat_score=70.0, topic_id=topic.id)
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
    items = list(items_result.scalars().all())
    assert len(items) == 1
    assert items[0].item_type == "topic"
    assert items[0].item_ref_id == topic.id
    assert digest.item_count == 1


@pytest.mark.asyncio
async def test_unprocessed_tweets_excluded(db: AsyncSession) -> None:
    """未处理完的推文不进入 digest_items。"""
    svc = _make_service(db)

    acct = await _seed_account(db)
    await _seed_tweet(db, acct, "processed", heat_score=80.0, is_processed=True)
    await _seed_tweet(db, acct, "unprocessed", heat_score=90.0, is_processed=False)
    await db.commit()

    digest = await svc.generate_daily_digest(DIGEST_DATE)
    items_result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
    items = list(items_result.scalars().all())
    assert len(items) == 1
    assert items[0].snapshot_heat_score == 80.0
