"""手动发布模式 API 测试（US-036）。"""

from datetime import date

from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.digest import DailyDigest

DIGEST_DATE = date(2026, 3, 20)


async def _seed_draft(
    db: AsyncSession,
    status: str = "draft",
    content_markdown: str = "# 智曦AI日报\n\n今日AI热点",
) -> DailyDigest:
    """创建测试 digest。"""
    digest = DailyDigest(
        digest_date=DIGEST_DATE,
        version=1,
        is_current=True,
        status=status,
        summary="摘要",
        item_count=2,
        content_markdown=content_markdown,
    )
    db.add(digest)
    await db.flush()
    return digest


# ── GET /api/digest/markdown ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestGetMarkdown:
    """获取 Markdown 内容。"""

    async def test_get_markdown_200(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """正常返回 content_markdown。"""
        await _seed_draft(db, content_markdown="# 测试标题\n\n正文内容")
        await db.commit()

        resp = await authed_client.get("/api/digest/markdown")
        assert resp.status_code == 200
        data = resp.json()
        assert data["content_markdown"] == "# 测试标题\n\n正文内容"

    async def test_get_markdown_404_no_digest(
        self,
        authed_client: AsyncClient,
    ) -> None:
        """无草稿 → 404。"""
        resp = await authed_client.get("/api/digest/markdown")
        assert resp.status_code == 404
        assert "草稿不存在" in resp.json()["detail"]

    async def test_get_markdown_401_no_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """未认证 → 401。"""
        resp = await client.get("/api/digest/markdown")
        assert resp.status_code == 401


# ── POST /api/digest/mark-published ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestMarkPublished:
    """标记发布。"""

    async def test_mark_published_200(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """draft → published, published_at 有值。"""
        await _seed_draft(db, status="draft")
        await db.commit()

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200
        assert resp.json()["message"] == "发布成功"

        # 通过 select 查询（触发 autoflush）验证 DB 状态
        result = await db.execute(
            select(DailyDigest).where(
                DailyDigest.digest_date == DIGEST_DATE,
                DailyDigest.is_current.is_(True),
            )
        )
        digest = result.scalar_one()
        assert digest.status == "published"
        assert digest.published_at is not None

    async def test_mark_published_409_already_published(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """已发布 → 409。"""
        await _seed_draft(db, status="published")
        await db.commit()

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 409
        assert "已发布" in resp.json()["detail"]

    async def test_mark_published_404_no_digest(
        self,
        authed_client: AsyncClient,
    ) -> None:
        """无草稿 → 404。"""
        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 404
        assert "草稿不存在" in resp.json()["detail"]

    async def test_mark_published_from_failed(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """failed → published（US-051 铺垫）。"""
        await _seed_draft(db, status="failed")
        await db.commit()

        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 200

        result = await db.execute(
            select(DailyDigest).where(
                DailyDigest.digest_date == DIGEST_DATE,
                DailyDigest.is_current.is_(True),
            )
        )
        digest = result.scalar_one()
        assert digest.status == "published"

    async def test_mark_published_401_no_auth(
        self,
        client: AsyncClient,
    ) -> None:
        """未认证 → 401。"""
        resp = await client.post("/api/digest/mark-published")
        assert resp.status_code == 401
