"""管理员登录认证测试（US-008）— 单元测试 + API 测试。"""

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import (
    InvalidTokenError,
    WeakPasswordError,
    check_login_rate_limit,
    create_jwt,
    hash_password,
    record_login_failure,
    record_login_success,
    reset_login_attempts,
    validate_password_strength,
    verify_jwt,
    verify_password,
)
from app.models.config import SystemConfig

# ── Helpers ──────────────────────────────────────────────────


async def _setup_admin(db: AsyncSession, password: str = "Admin123") -> None:
    """在 seeded_db 中写入 admin 密码哈希。"""
    hashed = hash_password(password)
    result = await db.execute(select(SystemConfig).where(SystemConfig.key == "admin_password_hash"))
    config = result.scalar_one()
    config.value = hashed
    await db.commit()


def _auth_header(token: str) -> dict[str, str]:
    """构造 Authorization header。"""
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def _clean_rate_limiter():  # noqa: ANN202
    """每个测试前后清空限流器状态。"""
    reset_login_attempts()
    yield
    reset_login_attempts()


# ══════════════════════════════════════════════════════════════
# 单元测试：app/auth.py 核心函数
# ══════════════════════════════════════════════════════════════


class TestPassword:
    """bcrypt 密码哈希与验证。"""

    def test_hash_and_verify(self) -> None:
        hashed = hash_password("Admin123")
        assert verify_password("Admin123", hashed)
        assert not verify_password("Wrong999", hashed)

    def test_validate_strength_valid(self) -> None:
        validate_password_strength("Admin123")  # 不抛异常

    def test_validate_strength_too_short(self) -> None:
        with pytest.raises(WeakPasswordError, match="至少8位"):
            validate_password_strength("Ab1")

    def test_validate_strength_no_upper(self) -> None:
        with pytest.raises(WeakPasswordError, match="大写字母"):
            validate_password_strength("admin123")

    def test_validate_strength_no_lower(self) -> None:
        with pytest.raises(WeakPasswordError, match="小写字母"):
            validate_password_strength("ADMIN123")

    def test_validate_strength_no_digit(self) -> None:
        with pytest.raises(WeakPasswordError, match="数字"):
            validate_password_strength("AdminPwd")


class TestJwt:
    """JWT 创建与验证。"""

    def test_create_and_verify(self) -> None:
        token, expires_at = create_jwt("admin")
        payload = verify_jwt(token)
        assert payload["sub"] == "admin"
        assert expires_at is not None

    def test_expired_raises(self) -> None:
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        from app.config import settings

        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(UTC) - timedelta(hours=1),
        }
        token = pyjwt.encode(expired_payload, settings.JWT_SECRET_KEY, algorithm="HS256")
        with pytest.raises(InvalidTokenError):
            verify_jwt(token)

    def test_invalid_signature_raises(self) -> None:
        from datetime import UTC, datetime, timedelta

        import jwt as pyjwt

        expired_payload = {
            "sub": "admin",
            "exp": datetime.now(UTC) + timedelta(hours=1),
        }
        token = pyjwt.encode(expired_payload, "wrong_secret", algorithm="HS256")
        with pytest.raises(InvalidTokenError):
            verify_jwt(token)


class TestRateLimiter:
    """登录限流器。"""

    def test_allows_initially(self) -> None:
        assert check_login_rate_limit("admin") is True

    def test_allows_under_threshold(self) -> None:
        for _ in range(4):
            record_login_failure("admin")
        assert check_login_rate_limit("admin") is True

    def test_locks_after_threshold(self) -> None:
        for _ in range(5):
            record_login_failure("admin")
        assert check_login_rate_limit("admin") is False

    def test_6th_attempt_still_locked(self) -> None:
        for _ in range(5):
            record_login_failure("admin")
        record_login_failure("admin")  # 第 6 次
        assert check_login_rate_limit("admin") is False

    def test_resets_on_success(self) -> None:
        for _ in range(4):
            record_login_failure("admin")
        record_login_success("admin")
        assert check_login_rate_limit("admin") is True
        # 重新开始计数
        for _ in range(4):
            record_login_failure("admin")
        assert check_login_rate_limit("admin") is True  # 还没到 5 次


# ══════════════════════════════════════════════════════════════
# API 测试：POST /api/auth/login & /api/auth/logout
# ══════════════════════════════════════════════════════════════


async def test_login_success(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """正确凭据 → 200 + JWT token。"""
    await _setup_admin(seeded_db)

    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "token" in body
    assert "expires_at" in body

    # 验证 token 可用
    payload = verify_jwt(body["token"])
    assert payload["sub"] == "admin"


async def test_login_wrong_password(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """错误密码 → 401。"""
    await _setup_admin(seeded_db)

    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "WrongPwd1"},
    )
    assert resp.status_code == 401
    assert "用户名或密码错误" in resp.json()["detail"]


async def test_login_wrong_username(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """错误用户名 → 401。"""
    await _setup_admin(seeded_db)

    resp = await client.post(
        "/api/auth/login",
        json={"username": "root", "password": "Admin123"},
    )
    assert resp.status_code == 401


async def test_login_not_initialized(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """系统未初始化（密码哈希为空）→ 401。"""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123"},
    )
    assert resp.status_code == 401


async def test_login_lockout_after_5_failures(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """连续5次失败 → 第6次 423。"""
    await _setup_admin(seeded_db)

    for _ in range(5):
        resp = await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPwd1"},
        )
        assert resp.status_code == 401

    # 第 6 次被锁定
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123"},  # 即使正确也被锁
    )
    assert resp.status_code == 423
    assert "15分钟" in resp.json()["detail"]


async def test_login_success_resets_counter(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """成功登录重置计数器。"""
    await _setup_admin(seeded_db)

    # 失败 4 次
    for _ in range(4):
        await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPwd1"},
        )

    # 成功一次 → 重置
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123"},
    )
    assert resp.status_code == 200

    # 再失败 4 次不应锁定
    for _ in range(4):
        await client.post(
            "/api/auth/login",
            json={"username": "admin", "password": "WrongPwd1"},
        )
    # 第 5 次成功
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123"},
    )
    assert resp.status_code == 200


async def test_logout(client: AsyncClient) -> None:
    """POST /logout → 200。"""
    resp = await client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["message"] == "已退出登录"


# ══════════════════════════════════════════════════════════════
# JWT 保护测试
# ══════════════════════════════════════════════════════════════


async def test_jwt_protects_accounts(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """无 token 访问 accounts → 401。"""
    resp = await client.get("/api/accounts")
    assert resp.status_code == 401


async def test_jwt_invalid_token(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """无效 token → 401。"""
    resp = await client.get("/api/accounts", headers=_auth_header("invalid.token.here"))
    assert resp.status_code == 401


async def test_jwt_valid_access(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """有效 token → 正常访问 accounts。"""
    token, _ = create_jwt("admin")
    resp = await client.get("/api/accounts", headers=_auth_header(token))
    assert resp.status_code == 200


async def test_setup_no_jwt_required(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """setup 路由不需要 JWT。"""
    resp = await client.get("/api/setup/status")
    assert resp.status_code == 200


async def test_auth_login_no_jwt_required(client: AsyncClient, seeded_db: AsyncSession) -> None:
    """auth/login 路由不需要 JWT。"""
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "Admin123"},
    )
    # 401 是因为未初始化，不是因为缺 JWT
    assert resp.status_code == 401
