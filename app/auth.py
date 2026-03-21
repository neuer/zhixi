"""认证 — JWT 生成/验证、bcrypt 密码哈希、密码强度校验、登录限流器。"""

import asyncio
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt

from app.config import settings

# ── 自定义异常 ──────────────────────────────────────────────


class WeakPasswordError(Exception):
    """密码强度不足。"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class InvalidTokenError(Exception):
    """JWT 无效或已过期。"""


# ── 密码操作 ────────────────────────────────────────────────


def _hash_password_sync(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def _verify_password_sync(password: str, hashed: str) -> bool:
    return bcrypt.checkpw(password.encode(), hashed.encode())


async def hash_password(password: str) -> str:
    """bcrypt 哈希（异步包装，避免阻塞事件循环）。"""
    return await asyncio.to_thread(_hash_password_sync, password)


async def verify_password(password: str, hashed: str) -> bool:
    """bcrypt 验证（异步包装）。"""
    return await asyncio.to_thread(_verify_password_sync, password, hashed)


def validate_password_strength(password: str) -> None:
    """校验密码强度：≥8位、含大写+小写+数字。不满足抛 WeakPasswordError。"""
    if len(password) < 8:
        raise WeakPasswordError("密码长度至少8位")
    if not re.search(r"[A-Z]", password):
        raise WeakPasswordError("密码必须包含大写字母")
    if not re.search(r"[a-z]", password):
        raise WeakPasswordError("密码必须包含小写字母")
    if not re.search(r"\d", password):
        raise WeakPasswordError("密码必须包含数字")


# ── JWT 操作 ────────────────────────────────────────────────

_ALGORITHM = "HS256"


def create_jwt(username: str) -> tuple[str, datetime]:
    """生成 JWT，返回 (token, expires_at)。"""
    expires_at = datetime.now(UTC) + timedelta(hours=settings.JWT_EXPIRE_HOURS)
    payload = {"sub": username, "exp": expires_at}
    token: str = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=_ALGORITHM)
    return token, expires_at


def verify_jwt(token: str) -> dict[str, str]:
    """验证 JWT，返回 payload。无效/过期抛 InvalidTokenError。"""
    try:
        payload: dict[str, str] = jwt.decode(
            token, settings.JWT_SECRET_KEY, algorithms=[_ALGORITHM]
        )
    except jwt.ExpiredSignatureError:
        raise InvalidTokenError from None
    except jwt.InvalidTokenError:
        raise InvalidTokenError from None
    return payload


# ── 登录限流器（内存实现，进程重启归零） ─────────────────────

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


@dataclass
class LoginAttempt:
    """单用户登录尝试记录。"""

    fail_count: int = 0
    locked_until: datetime | None = None


_login_attempts: dict[str, LoginAttempt] = {}


def check_login_rate_limit(username: str) -> bool:
    """返回 True 表示允许登录，False 表示被锁定。"""
    attempt = _login_attempts.get(username)
    if not attempt:
        return True
    if attempt.locked_until:
        if datetime.now(UTC) < attempt.locked_until:
            return False
        # 锁定时间已过，重置
        _login_attempts.pop(username, None)
    return True


def record_login_failure(username: str) -> None:
    """记录登录失败。达到阈值时触发锁定。"""
    attempt = _login_attempts.setdefault(username, LoginAttempt())
    attempt.fail_count += 1
    if attempt.fail_count >= LOCKOUT_THRESHOLD:
        attempt.locked_until = datetime.now(UTC) + LOCKOUT_DURATION


def record_login_success(username: str) -> None:
    """登录成功，重置失败计数器。"""
    _login_attempts.pop(username, None)


def reset_login_attempts() -> None:
    """清空限流器状态（仅测试用）。"""
    _login_attempts.clear()
