import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from google.auth import crypt, jwt

from app import auth, config

PROJECT = "pagehound-test"


@pytest.fixture(scope="module")
def keys():
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    other = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    def pem(key):
        return key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())

    public = private.public_key().public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo).decode()
    return {"signer": crypt.RSASigner.from_string(pem(private), "k1"), "other": crypt.RSASigner.from_string(pem(other), "k1"), "public": public}


@pytest.fixture(autouse=True)
def configured(monkeypatch, keys):
    monkeypatch.setattr(config, "FIREBASE_PROJECT_ID", PROJECT)
    monkeypatch.setattr(auth, "_fetch_certs", lambda: {"k1": keys["public"]})


def token(signer, **overrides):
    now = int(time.time())
    claims = {"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "user-1", "email": "v@example.com", "iat": now, "exp": now + 3600}
    claims.update(overrides)
    return jwt.encode(signer, claims).decode()


def test_a_valid_token_is_accepted(keys):
    claims = auth.verify(token(keys["signer"]))
    assert claims["sub"] == "user-1" and claims["email"] == "v@example.com"


def test_wrong_audience_issuer_or_missing_subject_are_rejected(keys):
    assert auth.verify(token(keys["signer"], aud="another-project")) is None
    assert auth.verify(token(keys["signer"], iss="https://securetoken.google.com/another-project")) is None
    assert auth.verify(token(keys["signer"], sub="")) is None


def test_expired_and_forged_tokens_are_rejected(keys):
    now = int(time.time())
    assert auth.verify(token(keys["signer"], iat=now - 7200, exp=now - 3600)) is None
    assert auth.verify(token(keys["other"])) is None
    assert auth.verify(token(keys["signer"])[:-4] + "AAAA") is None
    assert auth.verify("not-a-token") is None
    assert auth.verify("") is None


def test_without_a_project_id_nobody_is_verified(monkeypatch, keys):
    monkeypatch.setattr(config, "FIREBASE_PROJECT_ID", "")
    assert auth.verify(token(keys["signer"])) is None


def test_certificate_fetch_failure_means_guest_not_a_crash(monkeypatch, keys):
    def boom():
        raise RuntimeError("network down")

    monkeypatch.setattr(auth, "_fetch_certs", boom)
    assert auth.verify(token(keys["signer"])) is None


def test_debug_identity_header_is_ignored_in_production(monkeypatch):
    from starlette.requests import Request

    from app import auth, config

    monkeypatch.setattr(config, "ENV", "production")
    scope = {"type": "http", "headers": [(b"x-debug-user", b"someone-else")], "client": ("1.2.3.4", 1)}
    who = auth.identify(Request(scope))
    assert who.id == "ip:1.2.3.4" and not who.member
