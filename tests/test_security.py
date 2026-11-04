import hashlib
import hmac
from app.utils.security import verify_meta_signature, constant_time_compare
from app.utils.logger import mask_sensitive_data


def test_constant_time_compare():
    assert constant_time_compare("secret_token_123", "secret_token_123") is True
    assert constant_time_compare("secret_token_123", "secret_token_456") is False


def test_verify_meta_signature_valid():
    secret = "super_meta_secret_key"
    payload = b'{"hello": "world"}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    assert verify_meta_signature(payload, f"sha256={sig}", secret) is True


def test_verify_meta_signature_tampered_payload():
    secret = "super_meta_secret_key"
    payload = b'{"hello": "world"}'
    tampered_payload = b'{"hello": "world", "injected": true}'
    sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()

    # Tampered body should fail verification
    assert verify_meta_signature(tampered_payload, f"sha256={sig}", secret) is False


def test_mask_sensitive_data():
    raw_log = "Sending request with Bearer EAAXYZ1234567890abcdef and secret: 'my_app_secret_123'"
    masked = mask_sensitive_data(raw_log)

    assert "EAAXYZ1234567890abcdef" not in masked
    assert "REDACTED" in masked

