import hashlib
import hmac
import json
import pytest


def test_webhook_get_verification_success(client, test_settings):
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "1158201244",
            "hub.verify_token": test_settings.VERIFY_TOKEN,
        },
    )
    assert response.status_code == 200
    assert response.text == "1158201244"
    assert response.headers["content-type"].startswith("text/plain")


def test_webhook_get_verification_invalid_token(client):
    response = client.get(
        "/webhook",
        params={
            "hub.mode": "subscribe",
            "hub.challenge": "1158201244",
            "hub.verify_token": "wrong_token",
        },
    )
    assert response.status_code == 403


def test_webhook_post_valid_signature(client, test_settings, sample_comment_webhook_payload):
    payload_bytes = json.dumps(sample_comment_webhook_payload).encode("utf-8")
    signature = hmac.new(
        key=test_settings.META_APP_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["enqueued_events"] == 1


def test_webhook_post_invalid_signature(client, sample_comment_webhook_payload):
    payload_bytes = json.dumps(sample_comment_webhook_payload).encode("utf-8")

    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": "sha256=forged_invalid_signature_hex",
        },
    )
    assert response.status_code == 401
    assert "Invalid webhook signature" in response.text


def test_webhook_post_malformed_json(client, test_settings):
    payload_bytes = b"not a json string"
    signature = hmac.new(
        key=test_settings.META_APP_SECRET.encode("utf-8"),
        msg=payload_bytes,
        digestmod=hashlib.sha256,
    ).hexdigest()

    response = client.post(
        "/webhook",
        content=payload_bytes,
        headers={
            "Content-Type": "application/json",
            "X-Hub-Signature-256": f"sha256={signature}",
        },
    )
    assert response.status_code == 400

