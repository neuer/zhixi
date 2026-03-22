"""综合 API 接口测试（US-050）。

覆盖：认证流程、setup、digest CRUD、权限 409、锁 409。
"""

from datetime import UTC, date, datetime

import pytest
from freezegun import freeze_time
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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

# ── 受保护端点清单（method, url, body） ──

PROTECTED_ENDPOINTS: list[tuple[str, str, dict[str, object] | None]] = [
    ("get", "/api/accounts", None),
    ("post", "/api/accounts", {"twitter_handle": "test"}),
    ("put", "/api/accounts/1", {"is_active": True}),
    ("delete", "/api/accounts/1", None),
    ("get", "/api/digest/today", None),
    ("put", "/api/digest/item/tweet/1", {"title": "x"}),
    ("put", "/api/digest/summary", {"summary": "x"}),
    ("put", "/api/digest/reorder", {"items": []}),
    ("post", "/api/digest/exclude/tweet/1", None),
    ("post", "/api/digest/restore/tweet/1", None),
    ("post", "/api/digest/regenerate", None),
    ("get", "/api/digest/markdown", None),
    ("post", "/api/digest/mark-published", None),
    ("post", "/api/manual/fetch", None),
    ("get", "/api/settings", None),
    ("put", "/api/settings", {"push_time": "09:00"}),
    ("get", "/api/settings/api-status", None),
    ("get", "/api/dashboard/overview", None),
]


# ── 辅助函数 ──


async def _seed_draft_with_items(
    db: AsyncSession,
    *,
    status: str = "draft",
    item_count: int = 2,
) -> tuple[DailyDigest, list[DigestItem]]:
    """创建 config + digest + tweet items 用于综合测试。"""
    await seed_config_keys(db, top_n="10", min_articles="1")

    acct = await create_account(db, twitter_handle="testuser", display_name="Test User")

    digest = await create_digest(
        db,
        digest_date=DIGEST_DATE,
        status=status,
        item_count=item_count,
        summary="今日导读",
        content_markdown="# 测试 Markdown\n\n> 今日导读",
    )

    items: list[DigestItem] = []
    for i in range(1, item_count + 1):
        tweet = await create_tweet(
            db,
            acct,
            tweet_id=f"api_test_{i}",
            text=f"Text {i}",
            digest_date=DIGEST_DATE,
            tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
            title=f"标题{i}",
            translated_text=f"翻译{i}",
            ai_comment=f"点评{i}",
            is_ai_relevant=True,
            is_processed=True,
        )
        item = await create_digest_item(
            db,
            digest,
            item_ref_id=tweet.id,
            display_order=i,
            snapshot_title=f"标题{i}",
            snapshot_translation=f"翻译{i}",
            snapshot_comment=f"点评{i}",
            snapshot_heat_score=100.0 - i * 10,
            snapshot_author_name="Test User",
            snapshot_author_handle="testuser",
            snapshot_tweet_url=f"https://x.com/testuser/status/{i}",
            snapshot_tweet_time=datetime(2026, 3, 19, 10, 0, 0, tzinfo=UTC),
        )
        items.append(item)

    return digest, items


# ── 401 统一检查 ──


class TestUnauthedEndpoints:
    """所有受保护端点无 JWT → 401。"""

    @pytest.mark.parametrize(
        "method,url,body",
        PROTECTED_ENDPOINTS,
        ids=[f"{m.upper()} {u}" for m, u, _ in PROTECTED_ENDPOINTS],
    )
    async def test_returns_401(
        self,
        client: AsyncClient,
        method: str,
        url: str,
        body: dict[str, object] | None,
    ) -> None:
        """无 JWT → 401。"""
        kwargs: dict[str, object] = {}
        if body is not None:
            kwargs["json"] = body
        resp = await getattr(client, method)(url, **kwargs)
        assert resp.status_code == 401


# ── 公共端点 ──


class TestPublicEndpoints:
    """setup/login/logout 不需要 JWT。"""

    async def test_setup_status_accessible(
        self,
        client: AsyncClient,
        seeded_db: AsyncSession,
    ) -> None:
        """GET /api/setup/status 不需要 JWT。"""
        resp = await client.get("/api/setup/status")
        assert resp.status_code == 200
        assert "need_setup" in resp.json()

    async def test_logout_accessible(
        self,
        client: AsyncClient,
    ) -> None:
        """POST /api/auth/logout 不需要 JWT。"""
        resp = await client.post("/api/auth/logout")
        assert resp.status_code == 200

    async def test_login_returns_auth_error_not_401_missing_token(
        self,
        client: AsyncClient,
        seeded_db: AsyncSession,
    ) -> None:
        """POST /api/auth/login 无 JWT 也能访问（返回认证错误而非缺 token）。"""
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPwd1"},
        )
        # 401 是密码错误，不是缺 JWT
        assert resp.status_code == 401
        assert "密码错误" in resp.json()["detail"]


# ── setup → login 端到端 ──


class TestSetupLoginFlow:
    """setup → login → 获取 token → 用 token 操作。"""

    async def test_full_flow(
        self,
        client: AsyncClient,
        seeded_db: AsyncSession,
    ) -> None:
        """setup → login → 用 token 访问受保护端点。"""
        # 1. need_setup = true
        resp = await client.get("/api/setup/status")
        assert resp.json()["need_setup"] is True

        # 2. init
        resp = await client.post(
            "/api/setup/init",
            json={"password": "Admin123"},
        )
        assert resp.status_code == 200

        # 3. need_setup = false
        resp = await client.get("/api/setup/status")
        assert resp.json()["need_setup"] is False

        # 4. login
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "Admin123"},
        )
        assert resp.status_code == 200
        token = resp.json()["token"]

        # 5. 用 token 访问受保护端点
        headers = {"Authorization": f"Bearer {token}"}
        resp = await client.get("/api/accounts", headers=headers)
        assert resp.status_code == 200

    async def test_repeat_setup_403(
        self,
        client: AsyncClient,
        seeded_db: AsyncSession,
    ) -> None:
        """setup 完成后再次 init → 403。"""
        await client.post("/api/setup/init", json={"password": "Admin123"})
        resp = await client.post("/api/setup/init", json={"password": "Admin456"})
        assert resp.status_code == 403
        assert "已完成初始化" in resp.json()["detail"]


# ── Digest CRUD 综合 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestDigestCRUD:
    """查看 + 编辑 → markdown 反映变更。"""

    async def test_edit_reflected_in_markdown(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """编辑标题 → GET markdown 包含编辑内容。"""
        _, items = await _seed_draft_with_items(db, item_count=1)
        await db.commit()

        ref_id = items[0].item_ref_id
        resp = await authed_client.put(
            f"/api/digest/item/tweet/{ref_id}",
            json={"title": "编辑后标题"},
        )
        assert resp.status_code == 200

        resp = await authed_client.get("/api/digest/markdown")
        assert resp.status_code == 200
        assert "编辑后标题" in resp.json()["content_markdown"]

    async def test_reorder_then_today_sorted(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """排序后 GET today items 顺序正确。"""
        _, items = await _seed_draft_with_items(db, item_count=3)
        await db.commit()

        reorder_data = [
            {"id": items[2].id, "display_order": 0, "is_pinned": True},
            {"id": items[1].id, "display_order": 1, "is_pinned": False},
            {"id": items[0].id, "display_order": 2, "is_pinned": False},
        ]
        resp = await authed_client.put("/api/digest/reorder", json={"items": reorder_data})
        assert resp.status_code == 200

        resp = await authed_client.get("/api/digest/today")
        returned_ids = [item["id"] for item in resp.json()["items"]]
        assert returned_ids == [items[2].id, items[1].id, items[0].id]

    async def test_exclude_visible_in_today(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """剔除后 GET today 中该条目 is_excluded=true。"""
        _, items = await _seed_draft_with_items(db, item_count=2)
        await db.commit()

        ref_id = items[0].item_ref_id
        resp = await authed_client.post(f"/api/digest/exclude/tweet/{ref_id}")
        assert resp.status_code == 200

        resp = await authed_client.get("/api/digest/today")
        target = next(i for i in resp.json()["items"] if i["id"] == items[0].id)
        assert target["is_excluded"] is True

    async def test_summary_edit_in_markdown(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """编辑摘要 → markdown 包含新摘要。"""
        await _seed_draft_with_items(db, item_count=1)
        await db.commit()

        resp = await authed_client.put(
            "/api/digest/summary",
            json={"summary": "全新导读内容"},
        )
        assert resp.status_code == 200

        resp = await authed_client.get("/api/digest/markdown")
        assert "全新导读内容" in resp.json()["content_markdown"]


# ── 权限 409 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestPermission409:
    """published 状态下编辑操作 → 409。"""

    @pytest.mark.parametrize(
        "method,url_tpl,body",
        [
            ("put", "/api/digest/item/tweet/{ref}", {"title": "x"}),
            ("put", "/api/digest/summary", {"summary": "x"}),
            (
                "put",
                "/api/digest/reorder",
                {"items": [{"id": 1, "display_order": 0, "is_pinned": False}]},
            ),
            ("post", "/api/digest/exclude/tweet/{ref}", None),
        ],
        ids=["edit_item", "edit_summary", "reorder", "exclude"],
    )
    async def test_published_blocks_edit(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
        method: str,
        url_tpl: str,
        body: dict[str, object] | None,
    ) -> None:
        """published 状态下编辑 → 409。"""
        _, items = await _seed_draft_with_items(db, status="published")
        await db.commit()

        url = url_tpl.replace("{ref}", str(items[0].item_ref_id))
        kwargs: dict[str, object] = {}
        if body is not None:
            kwargs["json"] = body
        resp = await getattr(authed_client, method)(url, **kwargs)
        assert resp.status_code == 409


# ── 锁互斥 409 ──


@freeze_time("2026-03-20 08:00:00+08:00")
class TestLockMutex409:
    """pipeline running 时 regenerate/mark-published/manual-fetch → 409。"""

    async def _create_running_pipeline(self, db: AsyncSession) -> None:
        """创建 running pipeline job。"""
        job = JobRun(
            job_type="pipeline",
            digest_date=DIGEST_DATE,
            trigger_source="cron",
            status="running",
            started_at=datetime.now(UTC),
        )
        db.add(job)
        await db.commit()

    async def test_regenerate_locked(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """pipeline running → regenerate → 409。"""
        await self._create_running_pipeline(db)
        resp = await authed_client.post("/api/digest/regenerate")
        assert resp.status_code == 409

    async def test_mark_published_locked(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """pipeline running → mark-published → 409。"""
        await self._create_running_pipeline(db)
        resp = await authed_client.post("/api/digest/mark-published")
        assert resp.status_code == 409

    async def test_manual_fetch_locked(
        self,
        authed_client: AsyncClient,
        db: AsyncSession,
    ) -> None:
        """pipeline running → manual/fetch → 409。"""
        await self._create_running_pipeline(db)
        resp = await authed_client.post("/api/manual/fetch")
        assert resp.status_code == 409
