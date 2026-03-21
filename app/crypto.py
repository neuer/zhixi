"""对称加密工具 — 基于 Fernet，用于加密存储 API Key 等密钥配置。"""

import base64
import logging

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from app.config import settings

logger = logging.getLogger(__name__)

_SALT = b"zhixi-secret-config"
_ITERATIONS = 480_000


def _derive_key(secret: str) -> bytes:
    """从 JWT_SECRET_KEY 通过 PBKDF2-SHA256 派生 32 字节 Fernet key。"""
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=_SALT,
        iterations=_ITERATIONS,
    )
    return base64.urlsafe_b64encode(kdf.derive(secret.encode()))


def encrypt_secret(plaintext: str) -> str:
    """加密明文，返回 Fernet 密文字符串。空字符串直接返回空。"""
    if not plaintext:
        return ""
    key = _derive_key(settings.JWT_SECRET_KEY)
    f = Fernet(key)
    return f.encrypt(plaintext.encode()).decode()


def decrypt_secret(ciphertext: str) -> str:
    """解密密文，返回明文。失败返回空字符串并记录告警。"""
    if not ciphertext:
        return ""
    key = _derive_key(settings.JWT_SECRET_KEY)
    f = Fernet(key)
    try:
        return f.decrypt(ciphertext.encode()).decode()
    except (InvalidToken, Exception):
        logger.warning("密钥解密失败，可能 JWT_SECRET_KEY 已变更")
        return ""
