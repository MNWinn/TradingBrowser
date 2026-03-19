import hashlib
import hmac


def verify_alpaca_signature(raw_body: bytes, signature: str | None, secret: str | None) -> bool:
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), raw_body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
