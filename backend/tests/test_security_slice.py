import hmac
import hashlib

from app.core import auth
from app.core.config import settings
from app.services.secrets import encrypt_json, decrypt_json, generate_encryption_key
from app.services.webhook import verify_alpaca_signature


def test_encrypt_decrypt_roundtrip(monkeypatch):
    monkeypatch.setattr(settings, "encryption_key", generate_encryption_key())
    raw = '{"api_key":"abc","secret":"xyz"}'
    token = encrypt_json(raw)
    out = decrypt_json(token)
    assert out == raw


def test_verify_alpaca_signature():
    secret = "super-secret"
    raw = b'{"order":{"id":"o1","status":"filled"}}'
    sig = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    assert verify_alpaca_signature(raw, sig, secret)
    assert not verify_alpaca_signature(raw, "bad", secret)


def test_token_role_resolution(monkeypatch):
    monkeypatch.setattr(settings, "admin_api_token", "adm")
    monkeypatch.setattr(settings, "trader_api_token", "trd")
    monkeypatch.setattr(settings, "analyst_api_token", "anl")

    assert auth._resolve_role_from_token("adm") == "admin"
    assert auth._resolve_role_from_token("trd") == "trader"
    assert auth._resolve_role_from_token("anl") == "analyst"
    assert auth._resolve_role_from_token("nope") is None
