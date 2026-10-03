"""Unit tests for security, cryptography, and login throttling."""

import pytest

from app.security import (
    LoginThrottle,
    Vault,
    constant_time_equals,
    issue_session,
    random_secret,
    verify_session,
)


def test_vault_encrypt_decrypt():
    # 44-char Fernet key
    key = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="
    vault = Vault(key)

    plaintext = "super-secret-password-123"
    encrypted = vault.encrypt(plaintext)
    assert encrypted != plaintext

    decrypted = vault.decrypt(encrypted)
    assert decrypted == plaintext


def test_vault_encrypt_json():
    key = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="
    vault = Vault(key)

    data = {"username": "vpn_user", "token": "secret_abc"}
    enc = vault.encrypt_json(data)
    dec = vault.decrypt_json(enc)
    assert dec == data


def test_vault_invalid_token():
    key = "YWJjZGVmZ2hpamtsbW5vcHFyc3R1dnd4eXoxMjM0NTY="
    vault = Vault(key)

    with pytest.raises(RuntimeError, match="Cannot decrypt secret"):
        vault.decrypt("corrupted_invalid_token")


def test_random_secret():
    s1 = random_secret(24)
    s2 = random_secret(24)
    assert len(s1) == 24
    assert len(s2) == 24
    assert s1 != s2
    # Verify no special characters that would break URLs
    assert s1.isalnum()


def test_constant_time_equals():
    assert constant_time_equals("admin", "admin") is True
    assert constant_time_equals("admin", "root") is False


def test_jwt_session():
    secret = "a-very-long-secret-key-for-jwt-signing-test-12345"
    token = issue_session(secret, "admin", ttl_hours=1)
    assert isinstance(token, str)

    user = verify_session(secret, token)
    assert user == "admin"

    # Tampered token
    tampered = token[:-4] + "xxxx"
    assert verify_session(secret, tampered) is None

    # Wrong secret
    assert verify_session("wrong-secret-key-12345678901234567890", token) is None


def test_login_throttle():
    throttle = LoginThrottle(max_failures=3, window_seconds=60)
    client_ip = "192.168.1.50"

    assert throttle.is_locked(client_ip) is False

    throttle.record_failure(client_ip)
    assert throttle.is_locked(client_ip) is False

    throttle.record_failure(client_ip)
    assert throttle.is_locked(client_ip) is False

    throttle.record_failure(client_ip)
    # 3 failures reached -> locked
    assert throttle.is_locked(client_ip) is True

    # Other client is unaffected
    assert throttle.is_locked("192.168.1.51") is False

    # Reset on successful login
    throttle.reset(client_ip)
    assert throttle.is_locked(client_ip) is False
