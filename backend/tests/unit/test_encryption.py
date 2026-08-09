import pytest
import os
import base64
from app.services.encryption import EncryptionService
from app.config import get_settings


@pytest.fixture
def encryption_service(monkeypatch):
    # Generate a valid 32-byte key
    key = base64.b64encode(os.urandom(32)).decode()
    monkeypatch.setenv("ENCRYPTION_KEY", key)
    monkeypatch.setenv("ENCRYPTION_ALGORITHM", "AES-256-GCM")
    get_settings.cache_clear()
    return EncryptionService()


def test_encrypt_decrypt(encryption_service):
    plaintext = "test-secret-token"
    ciphertext = encryption_service.encrypt(plaintext)
    decrypted = encryption_service.decrypt(ciphertext)
    assert decrypted == plaintext


def test_encrypt_deterministic_different(encryption_service):
    plaintext = "test-secret"
    ciphertext1 = encryption_service.encrypt(plaintext)
    ciphertext2 = encryption_service.encrypt(plaintext)
    # Should be different due to random nonce
    assert ciphertext1 != ciphertext2
    # But both should decrypt to the same value
    assert encryption_service.decrypt(ciphertext1) == plaintext
    assert encryption_service.decrypt(ciphertext2) == plaintext


def test_decrypt_invalid_ciphertext(encryption_service):
    with pytest.raises(ValueError):
        encryption_service.decrypt(b"invalid")


def test_decrypt_wrong_key():
    key1 = base64.b64encode(os.urandom(32)).decode()
    key2 = base64.b64encode(os.urandom(32)).decode()
    os.environ["ENCRYPTION_KEY"] = key1
    get_settings.cache_clear()
    service1 = EncryptionService()
    ciphertext = service1.encrypt("secret")

    os.environ["ENCRYPTION_KEY"] = key2
    get_settings.cache_clear()
    service2 = EncryptionService()
    with pytest.raises(Exception):
        service2.decrypt(ciphertext)