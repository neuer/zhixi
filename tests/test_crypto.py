"""加密模块测试。"""

from unittest.mock import patch

from app.crypto import _derive_key, decrypt_secret, encrypt_secret


class TestDeriveKey:
    """密钥派生测试。"""

    def test_same_secret_same_key(self) -> None:
        """相同 secret 派生相同 key。"""
        k1 = _derive_key("test-secret")
        k2 = _derive_key("test-secret")
        assert k1 == k2

    def test_different_secret_different_key(self) -> None:
        """不同 secret 派生不同 key。"""
        k1 = _derive_key("secret-a")
        k2 = _derive_key("secret-b")
        assert k1 != k2


class TestEncryptDecrypt:
    """加密解密往返测试。"""

    def test_roundtrip(self) -> None:
        """加密→解密得到原文。"""
        plaintext = "sk-ant-api03-xxxxx"
        ciphertext = encrypt_secret(plaintext)
        assert ciphertext != plaintext
        assert decrypt_secret(ciphertext) == plaintext

    def test_empty_string(self) -> None:
        """空字符串不加密。"""
        assert encrypt_secret("") == ""
        assert decrypt_secret("") == ""

    def test_invalid_ciphertext(self) -> None:
        """无效密文返回空字符串。"""
        assert decrypt_secret("not-valid-ciphertext") == ""

    def test_different_key_fails(self) -> None:
        """JWT_SECRET_KEY 变更后解密失败。"""
        ciphertext = encrypt_secret("my-api-key")
        with patch("app.crypto.settings") as mock_settings:
            mock_settings.JWT_SECRET_KEY = "a-completely-different-secret-key"
            result = decrypt_secret(ciphertext)
            assert result == ""

    def test_unicode_content(self) -> None:
        """支持 Unicode 内容。"""
        plaintext = "密钥-中文测试-🔑"
        assert decrypt_secret(encrypt_secret(plaintext)) == plaintext
