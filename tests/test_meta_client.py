import hashlib
import hmac
import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch

from app.config.settings import Settings
from app.services.meta_client import MetaClient
from app.schemas.webhook import CommentEvent


@pytest.fixture
def meta_client(test_settings):
    return MetaClient(settings=test_settings)


def test_verify_webhook_signature(meta_client, test_settings):
    payload = b'{"object": "instagram", "entry": []}'
    secret = test_settings.META_APP_SECRET

    expected_hash = hmac.new(
        key=secret.encode("utf-8"),
        msg=payload,
        digestmod=hashlib.sha256,
    ).hexdigest()
    valid_header = f"sha256={expected_hash}"

    # Valid
    assert meta_client.verify_webhook(payload, valid_header) is True

    # Invalid hash
    assert meta_client.verify_webhook(payload, "sha256=invalidhash999") is False

    # Missing header
    assert meta_client.verify_webhook(payload, None) is False

    # Malformed header
    assert meta_client.verify_webhook(payload, "invalid_no_sha256_prefix") is False


def test_parse_comment_changes_format(meta_client, sample_comment_webhook_payload):
    events = meta_client.parse_comment(sample_comment_webhook_payload)
    assert len(events) == 1
    event = events[0]

    assert isinstance(event, CommentEvent)
    assert event.comment_id == "17999888777666"
    assert event.media_id == "18000111222333"
    assert event.ig_user_id == "17841499999999"
    assert event.username == "alice_dev"
    assert "guide and link" in event.text


def test_parse_comment_empty_or_unrelated_payload(meta_client):
    assert meta_client.parse_comment({}) == []
    assert meta_client.parse_comment({"object": "page", "entry": []}) == []


@pytest.mark.asyncio
async def test_send_dm_successful_call(test_settings):
    mock_response = httpx.Response(
        status_code=200,
        json={"recipient_id": "17841499999999", "message_id": "m_mid.1234567890"},
        request=httpx.Request("POST", "https://graph.facebook.com/v21.0/me/messages"),
    )

    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_http_client.post.return_value = mock_response

    client = MetaClient(settings=test_settings, client=mock_http_client)

    result = await client.send_dm(
        comment_id="comment_123",
        message_text="Here is your link!",
    )

    assert result["message_id"] == "m_mid.1234567890"

    # Verify posted payload matches Meta's official Private Reply specification
    mock_http_client.post.assert_called_once()
    call_args = mock_http_client.post.call_args
    posted_json = call_args[1]["json"]

    assert posted_json["recipient"] == {"comment_id": "comment_123"}
    assert posted_json["message"]["text"] == "Here is your link!"


@pytest.mark.asyncio
async def test_send_dm_validation_errors(meta_client):
    with pytest.raises(ValueError, match="Either comment_id or recipient_user_id must be provided"):
        await meta_client.send_dm(comment_id=None, recipient_user_id=None, message_text="Hi")

    with pytest.raises(ValueError, match="Message text cannot be empty"):
        await meta_client.send_dm(comment_id="123", message_text="")


@pytest.mark.asyncio
async def test_fetch_user(test_settings):
    mock_response = httpx.Response(
        status_code=200,
        json={"id": "17841499999999", "username": "alice_dev", "name": "Alice Developer"},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/17841499999999"),
    )

    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_http_client.get.return_value = mock_response

    client = MetaClient(settings=test_settings, client=mock_http_client)
    user_info = await client.fetch_user("17841499999999")
    assert user_info["username"] == "alice_dev"


@pytest.mark.asyncio
async def test_refresh_token(test_settings):
    mock_response = httpx.Response(
        status_code=200,
        json={"access_token": "new_long_lived_token_123", "token_type": "bearer", "expires_in": 5184000},
        request=httpx.Request("GET", "https://graph.facebook.com/v21.0/oauth/access_token"),
    )

    mock_http_client = AsyncMock(spec=httpx.AsyncClient)
    mock_http_client.get.return_value = mock_response

    client = MetaClient(settings=test_settings, client=mock_http_client)
    res = await client.refresh_token()
    assert res["access_token"] == "new_long_lived_token_123"

