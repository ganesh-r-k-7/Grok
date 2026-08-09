"""Encryption service - placeholder for Phase 1 implementation."""

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import base64
import os

from app.config import get_settings


class EncryptionService:
    def __init__(self, settings=None):
        # Decode base64 key from environment
        if settings is None:
            settings = get_settings()
        key_bytes = base64.b64decode(settings.ENCRYPTION_KEY)
        if len(key_bytes) != 32:
            raise ValueError("ENCRYPTION_KEY must be 32 bytes (base64 encoded)")
        self._key = key_bytes
        self._aesgcm = AESGCM(self._key)

    def encrypt(self, plaintext: str) -> bytes:
        """Encrypt a string and return ciphertext with nonce."""
        nonce = os.urandom(12)  # 96-bit nonce for AES-GCM
        ciphertext = self._aesgcm.encrypt(nonce, plaintext.encode(), None)
        return nonce + ciphertext

    def decrypt(self, ciphertext: bytes) -> str:
        """Decrypt ciphertext (nonce + ciphertext) and return plaintext."""
        if len(ciphertext) < 12:
            raise ValueError("Invalid ciphertext")
        nonce = ciphertext[:12]
        actual_ciphertext = ciphertext[12:]
        plaintext = self._aesgcm.decrypt(nonce, actual_ciphertext, None)
        return plaintext.decode()


# Singleton instance
_encryption_service: EncryptionService | None = None


def get_encryption_service() -> EncryptionService:
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service