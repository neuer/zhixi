"""首次设置向导 API 测试（US-007）。"""

import bcrypt
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import SystemConfig


async def _get_config_value(db: AsyncSession, key: str) -> str:
    """读取 system_config 中指定 key 的 value。"""
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else ""


# ── GET /api/setup/status ────────────────────────────────────


async def test_setup_status_need_setup(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """admin_password_hash 为空 → need_setup: true。"""
    resp = await client.get("/api/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"need_setup": True}


async def test_setup_status_already_done(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """admin_password_hash 非空 → need_setup: false。"""
    result = await seeded_db.execute(
        select(SystemConfig).where(SystemConfig.key == "admin_password_hash")
    )
    config = result.scalar_one()
    config.value = "$2b$12$fakehash"
    await seeded_db.commit()

    resp = await client.get("/api/setup/status")
    assert resp.status_code == 200
    assert resp.json() == {"need_setup": False}


# ── POST /api/setup/init ─────────────────────────────────────


async def test_setup_init_success(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """合规密码 → 200 + 密码写入 DB。"""
    resp = await client.post(
        "/api/setup/init",
        json={"password": "Admin123"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"message": "初始化完成"}

    # 验证 DB 写入
    stored = await _get_config_value(seeded_db, "admin_password_hash")
    assert stored != ""
    assert bcrypt.checkpw(b"Admin123", stored.encode())


async def test_setup_init_with_webhook(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """带 webhook_url → webhook 同时写入 DB。"""
    resp = await client.post(
        "/api/setup/init",
        json={
            "password": "Admin123",
            "notification_webhook_url": "https://example.com/hook",
        },
    )
    assert resp.status_code == 200

    webhook = await _get_config_value(seeded_db, "notification_webhook_url")
    assert webhook == "https://example.com/hook"


async def test_setup_init_weak_password_short(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """<8位 → 422（Pydantic min_length 校验 或 业务层 validate_password_strength）。"""
    resp = await client.post("/api/setup/init", json={"password": "Ab1"})
    assert resp.status_code == 422


async def test_setup_init_weak_password_no_upper(
    client: AsyncClient, seeded_db: AsyncSession
) -> None:
    """无大写 → 422。"""
    resp = await client.post("/api/setup/init", json={"password": "admin123"})
    assert resp.status_code == 422
    assert "大写字母" in resp.json()["detail"]


async def test_setup_init_weak_password_no_lower(
    client: AsyncClient, seeded_db: AsyncSession
) -> None:
    """无小写 → 422。"""
    resp = await client.post("/api/setup/init", json={"password": "ADMIN123"})
    assert resp.status_code == 422
    assert "小写字母" in resp.json()["detail"]


async def test_setup_init_weak_password_no_digit(
    client: AsyncClient, seeded_db: AsyncSession
) -> None:
    """无数字 → 422。"""
    resp = await client.post("/api/setup/init", json={"password": "AdminPwd"})
    assert resp.status_code == 422
    assert "数字" in resp.json()["detail"]


async def test_setup_init_already_done(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """重复调用 → 403。"""
    # 第一次初始化
    resp1 = await client.post("/api/setup/init", json={"password": "Admin123"})
    assert resp1.status_code == 200

    # 第二次应被拒绝
    resp2 = await client.post("/api/setup/init", json={"password": "Admin456"})
    assert resp2.status_code == 403
    assert "已完成初始化" in resp2.json()["detail"]


async def test_setup_init_verify_bcrypt(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """写入的哈希可用 bcrypt 验证。"""
    password = "MyPass99"
    await client.post("/api/setup/init", json={"password": password})

    stored = await _get_config_value(seeded_db, "admin_password_hash")
    assert bcrypt.checkpw(password.encode(), stored.encode())
