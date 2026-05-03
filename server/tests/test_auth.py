import pytest
from server.security_utils import (
    encrypt_api_key,
    decrypt_api_key,
    hash_password,
    verify_password,
)


class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        original = "sk-test-api-key-12345678"
        encrypted = encrypt_api_key(original)
        assert encrypted is not None
        assert encrypted != original
        assert not encrypted.startswith("sk-")
        decrypted = decrypt_api_key(encrypted)
        assert decrypted == original

    def test_encrypt_empty_string(self):
        encrypted = encrypt_api_key("")
        assert not encrypted

    def test_encrypt_none(self):
        assert encrypt_api_key(None) is None
        assert decrypt_api_key(None) is None

    def test_different_calls_different_ciphertext(self):
        e1 = encrypt_api_key("same-text")
        e2 = encrypt_api_key("same-text")
        assert e1 != e2

    def test_decrypt_invalid_raises(self):
        with pytest.raises(Exception):
            decrypt_api_key("invalid-base64!!!")

    def test_decrypt_tampered(self):
        encrypted = encrypt_api_key("original")
        assert encrypted is not None
        tampered = encrypted[:-4] + "AAAA"
        with pytest.raises(Exception):
            decrypt_api_key(tampered)


class TestPasswordHashing:
    def test_hash_and_verify(self):
        password = "SecurePass123!"
        hashed = hash_password(password)
        assert hashed != password
        assert verify_password(password, hashed) is True

    def test_wrong_password_fails(self):
        hashed = hash_password("correct")
        assert verify_password("wrong", hashed) is False

    def test_different_hash_each_time(self):
        h1 = hash_password("same")
        h2 = hash_password("same")
        assert h1 != h2

    def test_empty_password(self):
        hashed = hash_password("")
        assert verify_password("", hashed) is True

    def test_unicode_password(self):
        hashed = hash_password("密码123!@#")
        assert verify_password("密码123!@#", hashed) is True
