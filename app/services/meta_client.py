import json
import logging
import time
from typing import Any, Dict, List, Optional
import httpx
from app.config.settings import Settings, get_settings
from app.schemas.webhook import CommentEvent
from app.utils.retry import with_retry, is_retryable_meta_error
from app.utils.security import verify_meta_signature

logger = logging.getLogger(__name__)


class MetaClient:
    """Production-ready client for Meta Instagram Graph API and Messenger Platform."""

    def __init__(
        self,
        settings: Optional[Settings] = None,
        client: Optional[httpx.AsyncClient] = None,
    ):
        self.settings = settings or get_settings()
        self.base_url = f"{self.settings.GRAPH_API_BASE_URL}/{self.settings.GRAPH_API_VERSION}"
        self._external_client = client

    async def _get_client(self) -> httpx.AsyncClient:
        if self._external_client is not None:
            return self._external_client
        return httpx.AsyncClient(timeout=10.0)

    def verify_webhook(self, payload_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Verify incoming webhook signature using SHA256 HMAC.
        Uses META_APP_SECRET from settings.
        """
        return verify_meta_signature(
            payload_body=payload_body,
            signature_header=signature_header,
            app_secret=self.settings.META_APP_SECRET,
        )

    def parse_comment(self, payload: Dict[str, Any]) -> List[CommentEvent]:
        """
        Extract and normalize comment events from a Meta Webhook payload.
        Supports standard Instagram Graph API comment events and IG messaging events.
        """
        events: List[CommentEvent] = []

        if not payload or not isinstance(payload, dict):
            return events

        entries = payload.get("entry", [])
        for entry in entries:
            # Handle Instagram Graph API 'changes' format (field: comments)
            changes = entry.get("changes", [])
            for change in changes:
                if change.get("field") == "comments":
                    value = change.get("value", {})
                    comment_id = str(value.get("id", ""))
                    text = str(value.get("text", ""))
                    from_info = value.get("from", {})
                    user_id = str(from_info.get("id", ""))
                    username = from_info.get("username", "there")
                    media_info = value.get("media", {})
                    media_id = str(media_info.get("id", ""))

                    if comment_id and user_id:
                        events.append(
                            CommentEvent(
                                comment_id=comment_id,
                                media_id=media_id,
                                ig_user_id=user_id,
                                username=username,
                                text=text,
                                timestamp=entry.get("time"),
                                raw_payload=value,
                            )
                        )

            # Handle Messenger/Instagram Messaging format if comments arrive via messaging webhook
            messaging_list = entry.get("messaging", [])
            for msg in messaging_list:
                if "comment" in msg:
                    c_data = msg.get("comment", {})
                    comment_id = str(c_data.get("id", ""))
                    text = str(c_data.get("text", ""))
                    sender = msg.get("sender", {})
                    user_id = str(sender.get("id", ""))
                    media_id = str(c_data.get("media", {}).get("id", ""))

                    if comment_id and user_id:
                        events.append(
                            CommentEvent(
                                comment_id=comment_id,
                                media_id=media_id,
                                ig_user_id=user_id,
                                username="there",
                                text=text,
                                timestamp=entry.get("time"),
                                raw_payload=msg,
                            )
                        )

        return events

    async def send_dm(
        self,
        comment_id: Optional[str] = None,
        recipient_user_id: Optional[str] = None,
        message_text: str = "",
        max_retries: int = 3,
        backoff_factor: float = 2.0,
    ) -> Dict[str, Any]:
        """
        Send a Private Reply direct message in response to an Instagram comment
        using Meta's official Messenger API for Instagram endpoint:
        POST /v21.0/me/messages or /{INSTAGRAM_ACCOUNT_ID}/messages
        """
        if not comment_id and not recipient_user_id:
            raise ValueError("Either comment_id or recipient_user_id must be provided to send DM.")

        if not message_text.strip():
            raise ValueError("Message text cannot be empty.")

        account_id = self.settings.INSTAGRAM_ACCOUNT_ID or "me"
        url = f"{self.base_url}/{account_id}/messages"

        # Official Meta Private Reply payload structure
        recipient_payload: Dict[str, Any] = {}
        if comment_id:
            recipient_payload = {"comment_id": comment_id}
        else:
            recipient_payload = {"id": recipient_user_id}

        body = {
            "recipient": recipient_payload,
            "message": {
                "text": message_text,
            },
        }

        headers = {
            "Authorization": f"Bearer {self.settings.PAGE_ACCESS_TOKEN}",
            "Content-Type": "application/json",
        }

        async def _execute_post() -> Dict[str, Any]:
            client = await self._get_client()
            start_time = time.monotonic()
            should_close = self._external_client is None

            try:
                response = await client.post(url, json=body, headers=headers)
                elapsed_ms = (time.monotonic() - start_time) * 1000
                self.log_response(response, context=f"send_dm to {recipient_payload}", elapsed_ms=elapsed_ms)

                if response.status_code >= 400:
                    response.raise_for_status()

                return response.json()
            finally:
                if should_close:
                    await client.aclose()

        return await with_retry(
            _execute_post,
            max_retries=max_retries,
            backoff_factor=backoff_factor,
        )

    async def fetch_user(self, user_id: str) -> Dict[str, Any]:
        """
        Fetch basic public profile information for an Instagram user or Page.
        """
        url = f"{self.base_url}/{user_id}"
        params = {
            "fields": "id,username,name",
            "access_token": self.settings.PAGE_ACCESS_TOKEN,
        }

        client = await self._get_client()
        should_close = self._external_client is None
        try:
            response = await client.get(url, params=params)
            self.log_response(response, context=f"fetch_user({user_id})")
            if response.status_code >= 400:
                response.raise_for_status()
            return response.json()
        finally:
            if should_close:
                await client.aclose()

    async def refresh_token(self, existing_token: Optional[str] = None) -> Dict[str, Any]:
        """
        Exchange or refresh a Page Access Token for a long-lived access token.
        Meta endpoint: GET /oauth/access_token
        """
        token = existing_token or self.settings.PAGE_ACCESS_TOKEN
        url = f"{self.base_url}/oauth/access_token"
        params = {
            "grant_type": "fb_exchange_token",
            "client_id": self.settings.META_APP_ID,
            "client_secret": self.settings.META_APP_SECRET,
            "fb_exchange_token": token,
        }

        client = await self._get_client()
        should_close = self._external_client is None
        try:
            response = await client.get(url, params=params)
            self.log_response(response, context="refresh_token")
            if response.status_code >= 400:
                response.raise_for_status()
            return response.json()
        finally:
            if should_close:
                await client.aclose()

    def log_response(
        self,
        response: httpx.Response,
        context: str = "",
        elapsed_ms: Optional[float] = None,
    ) -> None:
        """Structured logging of Meta Graph API responses."""
        status = response.status_code
        timing_str = f" in {elapsed_ms:.1f}ms" if elapsed_ms is not None else ""

        if status < 400:
            logger.info("Meta API Success [%d]%s for %s", status, timing_str, context)
        else:
            try:
                error_body = response.json()
            except Exception:
                error_body = response.text

            logger.error(
                "Meta API Error [%d]%s for %s: %s",
                status,
                timing_str,
                context,
                error_body,
            )

