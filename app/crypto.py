"""对称加密工具 — 基于 Fernet，用于加密存储 API Key 等密钥配置。"""

import base64
import functools
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

logger = logging.getLogger(__name__)


class SecretDecryptionError(RuntimeError):
    """密钥解密失败异常 — 通常由 JWT_SECRET_KEY 变更导致。"""


_SALT = b"zhixi-secret-config"
_ITERATIONS = 480_000


@functools.lru_cache(maxsize=4)
def _derive_key(secret: str) -> bytes:
    """从 JWT_SECRET_KEY 通过 PBKDF2-SHA256 派生 32 字节 Fernet key。

    结果通过 lru_cache 缓存，避免每次调用重复执行 PBKDF2 计算。
    """
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def _get_fernet() -> Fernet:
    """获取当前 JWT_SECRET_KEY 对应的 Fernet 实例。"""
    key = _derive_key(settings.JWT_SECRET_KEY)
    return Fernet(key)


def encrypt_secret(plaintext: str) -> str:
    """加密明文，返回 Fernet 密文字符串。空字符串直接返回空。"""
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """解密密文，返回明文。空密文返回空字符串，解密失败抛出 SecretDecryptionError。"""
    if not ciphertext:
        return ""
    try:
        return _get_fernet().decrypt(ciphertext.encode()).decode()
    except InvalidToken:
        logger.error("密钥解密失败，可能 JWT_SECRET_KEY 已变更")
        raise SecretDecryptionError("密钥解密失败，可能 JWT_SECRET_KEY 已变更") from None
