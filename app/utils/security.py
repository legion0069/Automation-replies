import hashlib
import hmac
import logging
from typing import Optional

logger = logging.getLogger(__name__)


def constant_time_compare(val1: str, val2: str) -> bool:
    """Safely compare two strings in constant time to prevent timing attacks."""
    return hmac.compare_digest(val1.encode("utf-8"), val2.encode("utf-8"))


def verify_meta_signature(
    payload_body: bytes,
    signature_header: Optional[str],
    app_secret: str,
) -> bool:
    """
    Validate incoming Meta webhook signature.
    Meta sends an 'X-Hub-Signature-256' header formatted as:
    'sha256=<hex_digest>'
    """
    if not signature_header:
        logger.warning("Webhook request missing 'X-Hub-Signature-256' header.")
        return False

    if not app_secret:
        logger.error("META_APP_SECRET is not configured. Cannot verify webhook signature.")
        return False

    parts = signature_header.split("sha256=", 1)
    if len(parts) != 2:
        logger.warning("Invalid X-Hub-Signature-256 format: %s", signature_header)
        return False

    received_hash = parts[1].strip()

    expected_hash = hmac.new(
        key=app_secret.encode("utf-8"),
        msg=payload_body,
        digestmod=hashlib.sha256,
    ).hexdigest()

    is_valid = hmac.compare_digest(received_hash, expected_hash)
    if not is_valid:
        logger.warning(
            "Webhook signature mismatch! Received: %s, Expected: %s",
            received_hash[:8] + "...",
            expected_hash[:8] + "...",
        )
    return is_valid

