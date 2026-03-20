"""大V账号管理 API 测试（US-010）。"""

import respx
from httpx import AsyncClient, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.account import TwitterAccount

# X API mock 响应数据
X_API_USER_RESPONSE = {
    "data": {
        "id": "12345",
        "name": "Andrej Karpathy",
        "username": "karpathy",
        "description": "AI researcher",
        "profile_image_url": "https://pbs.twimg.com/karpathy.jpg",
        "public_metrics": {
            "followers_count": 500000,
            "following_count": 200,
            "tweet_count": 3000,
        },
    }
}


async def _seed_account(db: AsyncSession, **overrides: object) -> TwitterAccount:
    """在测试 DB 中创建一条账号记录。"""
    defaults = {
        "twitter_handle": "testuser",
        "display_name": "Test User",
        "weight": 1.0,
        "is_active": True,
    }
    defaults.update(overrides)
    account = TwitterAccount(**defaults)  # type: ignore[arg-type]
    db.add(account)
    await db.flush()
    return account


# ──────────────────── GET /api/accounts ────────────────────


async def test_list_accounts_empty(authed_client: AsyncClient) -> None:
    """空列表返回 items=[], total=0。"""
    resp = await authed_client.get("/api/accounts")
    assert resp.status_code == 200
    body = resp.json()
    assert body["items"] == []
    assert body["total"] == 0
    assert body["page"] == 1


async def test_list_accounts_with_data(authed_client: AsyncClient, db: AsyncSession) -> None:
    """有数据时正确返回分页列表。"""
    await _seed_account(db, twitter_handle="user1", display_name="User 1")
    await _seed_account(db, twitter_handle="user2", display_name="User 2")
    await _seed_account(db, twitter_handle="user3", display_name="User 3")
    await db.commit()

    # 第一页，page_size=2
    resp = await authed_client.get("/api/accounts?page=1&page_size=2")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["total"] == 3
    assert body["page"] == 1
    assert body["page_size"] == 2

    # 第二页
    resp2 = await authed_client.get("/api/accounts?page=2&page_size=2")
    body2 = resp2.json()
    assert len(body2["items"]) == 1


async def test_list_accounts_excludes_inactive(
    authed_client: AsyncClient, db: AsyncSession
) -> None:
    """默认不返回 inactive 账号。"""
    await _seed_account(db, twitter_handle="active", display_name="Active", is_active=True)
    await _seed_account(db, twitter_handle="inactive", display_name="Inactive", is_active=False)
    await db.commit()

    resp = await authed_client.get("/api/accounts")
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["twitter_handle"] == "active"


# ──────────────────── POST /api/accounts ────────────────────


@respx.mock
async def test_create_account_auto_fetch(authed_client: AsyncClient) -> None:
    """X API 拉取成功 → 201 + 完整用户信息。"""
    respx.get("https://api.x.com/2/users/by/username/karpathy").mock(
        return_value=Response(200, json=X_API_USER_RESPONSE)
    )

    resp = await authed_client.post(
        "/api/accounts",
        json={"twitter_handle": "karpathy", "weight": 1.3},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["twitter_handle"] == "karpathy"
    assert body["display_name"] == "Andrej Karpathy"
    assert body["twitter_user_id"] == "12345"
    assert body["followers_count"] == 500000
    assert body["weight"] == 1.3
    assert body["is_active"] is True


async def test_create_account_manual_mode(authed_client: AsyncClient) -> None:
    """提供 display_name 时跳过 X API，手动模式创建。"""
    resp = await authed_client.post(
        "/api/accounts",
        json={
            "twitter_handle": "manualuser",
            "display_name": "Manual User",
            "bio": "手动添加的用户",
            "weight": 2.0,
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["twitter_handle"] == "manualuser"
    assert body["display_name"] == "Manual User"
    assert body["bio"] == "手动添加的用户"
    assert body["twitter_user_id"] is None
    assert body["followers_count"] == 0


@respx.mock
async def test_create_account_x_api_failure(authed_client: AsyncClient) -> None:
    """X API 失败 → 502 + allow_manual 标记。"""
    respx.get("https://api.x.com/2/users/by/username/baduser").mock(
        return_value=Response(403, json={"errors": [{"message": "Forbidden"}]})
    )

    resp = await authed_client.post(
        "/api/accounts",
        json={"twitter_handle": "baduser"},
    )
    assert resp.status_code == 502
    body = resp.json()
    assert body["detail"].startswith("X API拉取失败")
    assert body["allow_manual"] is True


async def test_create_account_duplicate(authed_client: AsyncClient, db: AsyncSession) -> None:
    """重复 handle → 409。"""
    await _seed_account(db, twitter_handle="duplicate", display_name="Dup")
    await db.commit()

    resp = await authed_client.post(
        "/api/accounts",
        json={"twitter_handle": "duplicate", "display_name": "Another"},
    )
    assert resp.status_code == 409
    assert resp.json()["detail"] == "该账号已存在"


async def test_create_account_strip_at(authed_client: AsyncClient) -> None:
    """自动去除 @ 前缀。"""
    resp = await authed_client.post(
        "/api/accounts",
        json={"twitter_handle": "@atuser", "display_name": "At User"},
    )
    assert resp.status_code == 201
    assert resp.json()["twitter_handle"] == "atuser"


# ──────────────────── PUT /api/accounts/{id} ────────────────────


async def test_update_account_weight(authed_client: AsyncClient, db: AsyncSession) -> None:
    """更新权重成功。"""
    account = await _seed_account(db, twitter_handle="upd", display_name="Upd")
    await db.commit()

    resp = await authed_client.put(
        f"/api/accounts/{account.id}",
        json={"weight": 3.5},
    )
    assert resp.status_code == 200
    assert resp.json()["weight"] == 3.5


async def test_update_account_not_found(authed_client: AsyncClient) -> None:
    """不存在的 ID → 404。"""
    resp = await authed_client.put("/api/accounts/9999", json={"weight": 1.0})
    assert resp.status_code == 404
    assert resp.json()["detail"] == "账号不存在"


# ──────────────────── DELETE /api/accounts/{id} ────────────────────


async def test_delete_account_soft(authed_client: AsyncClient, db: AsyncSession) -> None:
    """软删除：is_active 变为 false。"""
    account = await _seed_account(db, twitter_handle="del", display_name="Del")
    await db.commit()

    resp = await authed_client.delete(f"/api/accounts/{account.id}")
    assert resp.status_code == 200
    assert resp.json()["message"] == "账号已删除"

    # 验证列表不再包含
    list_resp = await authed_client.get("/api/accounts")
    assert list_resp.json()["total"] == 0


async def test_delete_account_not_found(authed_client: AsyncClient) -> None:
    """不存在的 ID → 404。"""
    resp = await authed_client.delete("/api/accounts/9999")
    assert resp.status_code == 404
    assert resp.json()["detail"] == "账号不存在"
