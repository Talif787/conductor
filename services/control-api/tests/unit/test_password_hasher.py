from __future__ import annotations

from app.infrastructure.security.password import Argon2PasswordHasher


def test_hash_is_not_plaintext_and_verifies() -> None:
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash("correct horse battery staple")
    assert hashed != "correct horse battery staple"
    assert hasher.verify(hashed, "correct horse battery staple")


def test_wrong_password_does_not_verify() -> None:
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash("password123")
    assert not hasher.verify(hashed, "password124")


def test_malformed_hash_returns_false() -> None:
    hasher = Argon2PasswordHasher()
    assert not hasher.verify("not-a-real-hash", "password123")
