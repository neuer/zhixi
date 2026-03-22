"""Digest 状态流转测试（US-051）。

覆盖：draft→published、draft→regenerate→v2、published后regenerate→new draft、
failed→regenerate→new draft、failed→重试发布→published、
已published不可修改、is_current 切换、regenerate 失败回滚。
"""

from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_digest_service
from app.main import app
from app.models.digest import DailyDigest
from app.models.digest_item import DigestItem
from app.models.job_run import JobRun
from tests.factories import (
    create_account,
    create_digest,
    create_digest_item,
    create_tweet,
    seed_config_keys,
)

DIGEST_DATE = date(2026, 3, 20)

TWEET_TIME = datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC)


# ── 辅助函数 ──


async def _setup_digest_with_item(
    db: AsyncSession,
    *,
    version: int = 1,
    status: str = "draft",
) -> tuple[DailyDigest, DigestItem]:
    """创建 config + account + tweet + digest + item 的完整组合。"""
    await seed_config_keys(db, top_n="10", min_articles="1")

    acct = await create_account(db, twitter_handle="stuser", display_name="ST User")
    tweet = await create_tweet(
        db,
        acct,
        tweet_id=f"st_tweet_v{version}",
        digest_date=DIGEST_DATE,
        tweet_time=TWEET_TIME,
        title="标题",
        translated_text="翻译",
        ai_comment="点评",
        is_processed=True,
    )

    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        version=version,
        status=status,
        summary="测试摘要",
        item_count=2,
        content_markdown="# 版本内容",
    )

    item = await create_digest_item(
        db,
        digest,
        item_ref_id=tweet.id,
        snapshot_title="标题",
        snapshot_translation="翻译",
        snapshot_comment="点评",
        snapshot_heat_score=85.0,
        snapshot_author_name="ST User",
        snapshot_author_handle="stuser",
        snapshot_tweet_url="https://x.com/stuser/status/1",
        snapshot_tweet_time=TWEET_TIME,
    )
    return digest, item


async def _query_digest(
    db: AsyncSession,
    version: int,
) -> DailyDigest:
    """通过 select 查询 digest（触发 autoflush）。"""
    result = await db.execute(
        select(DailyDigest).where(
            DailyDigest.digest_date == DIGEST_DATE,
            DailyDigest.version == version,
        )
    )
    return result.scalar_one()


@contextmanager
def _override_digest_service(mock_svc: Any):  # noqa: ANN204
    """临时覆盖 get_digest_service 依赖。"""
    app.dependency_overrides[get_digest_service] = lambda: mock_svc
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_digest_service, None)


def _make_regenerate_patches(
    db: AsyncSession,
    new_version: int,
    new_item_count: int = 3,
) -> tuple[Any, Any]:
    """创建 regenerate mock patches。

    side_effect 模拟 regenerate_digest 的 DB 变更：
    旧 digest is_current=false → 创建新 digest。
    """

    async def mock_regenerate(digest_date: date) -> DailyDigest:
        old_stmt = select(DailyDigest).where(
            DailyDigest.digest_date == digest_date,
            DailyDigest.is_current.is_(True),
        )
        old_result = await db.execute(old_stmt)
        old_digest = old_result.scalar_one_or_none()
        if old_digest:
            old_digest.is_current = False

        new_digest = DailyDigest(
            digest_date=digest_date,
            version=new_version,
            is_current=True,
            status="draft",
            summary="新版摘要",
            item_count=new_item_count,
            content_markdown="# 新版本",
        )
        db.add(new_digest)
        await db.flush()
        return new_digest

    mock_svc = AsyncMock()
    mock_svc.regenerate_digest = mock_regenerate

    return (
        _override_digest_service(mock_svc),
        patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
    )


def _make_regenerate_failure_patches() -> tuple[Any, Any, Any]:
    """创建 regenerate 失败的 mock patches。"""
    mock_svc = AsyncMock()
    mock_svc.regenerate_digest = AsyncMock(side_effect=RuntimeError("AI 超时"))

    return (
        _override_digest_service(mock_svc),
        patch("app.api.digest.get_today_digest_date", return_value=DIGEST_DATE),
        patch("app.api.digest.send_alert", AsyncMock()),
    )


# ── draft → published ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestDraftToPublished:
    """draft → published 流转。"""

    async def test_draft_to_published(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """draft → mark-published → published + published_at 有值。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200

        digest = await _query_digest(db, version=1)
        assert digest.status == "published"
        assert digest.published_at is not None

    async def test_published_preserves_is_current(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """发布后 is_current 保持 true。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        await authed_client.post("/api/digest/mark-published")

        digest = await _query_digest(db, version=1)
        assert digest.is_current is True


# ── draft → regenerate → v2 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestDraftRegenerateV2:
    """draft → regenerate → v2 draft。"""

    async def test_creates_v2(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """draft v1 → regenerate → v2 draft, v1.is_current=false。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            resp = await authed_client.post("/api/digest/regenerate")

        assert resp.status_code == 200
        assert resp.json()["version"] == 2

        v1 = await _query_digest(db, version=1)
        assert v1.is_current is False

        v2 = await _query_digest(db, version=2)
        assert v2.is_current is True
        assert v2.status == "draft"

    async def test_v2_is_editable(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """regenerate 后新版本可编辑（不返回 409）。"""
        await seed_config_keys(db, top_n="10", min_articles="1")
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        # 尝试编辑摘要 — 不应 409
        resp = await authed_client.put(
            "/api/digest/summary",
            json={"summary": "v2 新摘要"},
        )
        assert resp.status_code != 409

    async def test_v2_to_published(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """v2 draft → mark-published → v2 published。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200

        v2 = await _query_digest(db, version=2)
        assert v2.status == "published"
        assert v2.published_at is not None


# ── published → regenerate → new draft ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPublishedRegenerateNewDraft:
    """published → regenerate → new draft。"""

    async def test_creates_new_draft(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """published v1 → regenerate → draft v2。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            status="published",
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            resp = await authed_client.post("/api/digest/regenerate")

        assert resp.status_code == 200

        v1 = await _query_digest(db, version=1)
        assert v1.status == "published"  # 旧版本状态不变
        assert v1.is_current is False

        v2 = await _query_digest(db, version=2)
        assert v2.status == "draft"
        assert v2.is_current is True

    async def test_old_published_items_intact(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """regenerate 后旧版本 items 快照不受影响。"""
        digest, item = await _setup_digest_with_item(db, version=1, status="published")
        original_title = item.snapshot_title
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        # 旧版本 item 快照不变
        result = await db.execute(select(DigestItem).where(DigestItem.digest_id == digest.id))
        old_item = result.scalar_one()
        assert old_item.snapshot_title == original_title


# ── failed → regenerate → new draft ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestFailedRegenerateNewDraft:
    """failed → regenerate → new draft。"""

    async def test_creates_new_draft(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """failed v1 → regenerate → draft v2。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            status="failed",
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            resp = await authed_client.post("/api/digest/regenerate")

        assert resp.status_code == 200

        v1 = await _query_digest(db, version=1)
        assert v1.status == "failed"  # 旧版本状态不变
        assert v1.is_current is False

    async def test_v2_then_published(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """failed v1 → regenerate → v2 draft → mark-published → v2 published。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            status="failed",
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200

        v2 = await _query_digest(db, version=2)
        assert v2.status == "published"


# ── failed → 重试发布 → published ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestFailedRetryPublish:
    """failed → mark-published → published。"""

    async def test_failed_to_published(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """failed → mark-published → published。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            status="failed",
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200

        digest = await _query_digest(db, version=1)
        assert digest.status == "published"

    async def test_published_at_set(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """failed → published 后 published_at 有值。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            status="failed",
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        await authed_client.post("/api/digest/mark-published")

        digest = await _query_digest(db, version=1)
        assert digest.published_at is not None


# ── published 不可编辑 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPublishedNoEdit:
    """published 状态下所有编辑操作 → 409。"""

    @pytest.mark.parametrize(
        "method,url,body",
        [
            ("put", "/api/digest/item/tweet/9999", {"title": "x"}),
            ("put", "/api/digest/summary", {"summary": "x"}),
            ("put", "/api/digest/reorder", {"items": []}),
            ("post", "/api/digest/exclude/tweet/9999", None),
            ("post", "/api/digest/restore/tweet/9999", None),
        ],
        ids=["edit_item", "edit_summary", "reorder", "exclude", "restore"],
    )
    async def test_all_edits_blocked(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
        method: str,
        url: str,
        body: dict[str, object] | None,
    ) -> None:
        """published → 编辑 → 409。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            status="published",
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        kwargs: dict[str, object] = {}
        if body is not None:
            kwargs["json"] = body
        resp = await getattr(authed_client, method)(url, **kwargs)
        assert resp.status_code == 409


# ── is_current 切换 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestIsCurrentSwitch:
    """is_current 在各流转中的正确性。"""

    async def test_regenerate_switches(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """regenerate: 旧 false, 新 true。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        v1 = await _query_digest(db, version=1)
        v2 = await _query_digest(db, version=2)
        assert v1.is_current is False
        assert v2.is_current is True

    async def test_multi_version_only_one_current(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """v1 → regen → v2 → regen → v3，仅 v3 is_current=true。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        # v1 → v2
        p1, p2 = _make_regenerate_patches(db, new_version=2)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        # v2 → v3
        p1, p2 = _make_regenerate_patches(db, new_version=3)
        with p1, p2:
            await authed_client.post("/api/digest/regenerate")

        v1 = await _query_digest(db, version=1)
        v2 = await _query_digest(db, version=2)
        v3 = await _query_digest(db, version=3)
        assert v1.is_current is False
        assert v2.is_current is False
        assert v3.is_current is True

    async def test_get_today_returns_current(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """GET /today 只返回 is_current=true 的版本。"""
        await seed_config_keys(db, top_n="10", min_articles="1")
        # v1: 旧版本
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=1,
            is_current=False,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        # v2: 当前版本
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            version=2,
            is_current=True,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        resp = await authed_client.get("/api/digest/today")
        assert resp.status_code == 200
        data = resp.json()
        assert data["digest"]["version"] == 2


# ── regenerate 失败回滚 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestRegenerateFailureRollback:
    """regenerate 失败 → 500 + job_run failed。

    注：is_current 的恢复由 DigestService.regenerate_digest 内部 finally 块负责，
    已在 test_regenerate_service.py::test_regenerate_rollback_on_failure 中覆盖。
    API 层验证 500 响应 + job_run 持久化。
    """

    async def test_returns_500(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """regenerate 失败 → 500。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2, p3 = _make_regenerate_failure_patches()
        with p1, p2, p3:
            resp = await authed_client.post("/api/digest/regenerate")

        assert resp.status_code == 500
        assert "重新生成失败" in resp.json()["detail"]

    async def test_job_run_marked_failed(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """regenerate 失败 → job_run.status=failed + error_message。"""
        await create_digest(
            db,
            digest_date=DIGEST_DATE,
            summary="测试摘要",
            item_count=2,
            content_markdown="# 版本内容",
        )
        await db.commit()

        p1, p2, p3 = _make_regenerate_failure_patches()
        with p1, p2, p3:
            await authed_client.post("/api/digest/regenerate")

        result = await db.execute(select(JobRun).where(JobRun.trigger_source == "regenerate"))
        job_run = result.scalar_one()
        assert job_run.status == "failed"
        assert "AI 超时" in (job_run.error_message or "")
