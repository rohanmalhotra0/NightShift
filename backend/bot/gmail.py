"""Gmail API integration for fetching verification codes."""

import base64
import json
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Optional
from pathlib import Path

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from ..config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


class GmailVerificationHandler:
    """Handles fetching verification codes from Gmail."""

    # Common patterns for verification codes in emails
    CODE_PATTERNS = [
        r'(?:verification|confirm|verify|code|otp|pin)[:\s]*(\d{4,8})',
        r'(?:code|pin|otp)[:\s]*([A-Z0-9]{4,8})',
        r'\b(\d{6})\b',  # 6-digit codes are common
        r'enter[:\s]*(\d{4,8})',
        r'(?:is|code:?)[:\s]*(\d{4,8})',
    ]

    def __init__(
        self,
        credentials_json: Optional[str] = None,
        token_path: Path = Path("gmail_token.json"),
    ):
        """
        Initialize Gmail handler.

        Args:
            credentials_json: Gmail OAuth credentials as JSON string.
            token_path: Path to store/load OAuth token.
        """
        self.credentials_json = credentials_json or settings.GMAIL_CREDENTIALS
        self.token_path = token_path
        self.service = None
        self._creds = None

    def authenticate(self) -> bool:
        """
        Authenticate with Gmail API.

        Returns:
            True if authentication succeeded.
        """
        try:
            # Load existing token
            if self.token_path.exists():
                self._creds = Credentials.from_authorized_user_file(
                    str(self.token_path), SCOPES
                )

            # Refresh or get new token
            if not self._creds or not self._creds.valid:
                if self._creds and self._creds.expired and self._creds.refresh_token:
                    self._creds.refresh(Request())
                else:
                    if not self.credentials_json:
                        logger.error("No Gmail credentials provided")
                        return False

                    creds_dict = json.loads(self.credentials_json)
                    flow = InstalledAppFlow.from_client_config(creds_dict, SCOPES)
                    self._creds = flow.run_local_server(port=0)

                # Save token
                with open(self.token_path, "w") as f:
                    f.write(self._creds.to_json())

            self.service = build("gmail", "v1", credentials=self._creds)
            logger.info("Gmail authenticated successfully")
            return True

        except Exception as e:
            logger.error(f"Gmail authentication failed: {e}")
            return False

    def get_verification_code(
        self,
        sender_contains: Optional[str] = None,
        subject_contains: Optional[str] = None,
        max_age_seconds: int = 300,
        poll_interval: int = 5,
        max_polls: int = 24,
    ) -> Optional[str]:
        """
        Poll for and extract a verification code from recent emails.

        Args:
            sender_contains: Filter by sender email containing this string.
            subject_contains: Filter by subject containing this string.
            max_age_seconds: Only check emails from last N seconds.
            poll_interval: Seconds between polling attempts.
            max_polls: Maximum number of polling attempts.

        Returns:
            Verification code if found, None otherwise.
        """
        if not self.service:
            if not self.authenticate():
                return None

        start_time = datetime.utcnow()
        check_after = start_time - timedelta(seconds=max_age_seconds)

        for attempt in range(max_polls):
            logger.debug(f"Polling for verification code, attempt {attempt + 1}")

            code = self._search_for_code(
                sender_contains=sender_contains,
                subject_contains=subject_contains,
                after_time=check_after,
            )

            if code:
                logger.info(f"Found verification code: {code}")
                return code

            if attempt < max_polls - 1:
                time.sleep(poll_interval)

        logger.warning("Verification code not found after polling")
        return None

    def _search_for_code(
        self,
        sender_contains: Optional[str],
        subject_contains: Optional[str],
        after_time: datetime,
    ) -> Optional[str]:
        """Search emails for verification code."""
        try:
            # Build query
            query_parts = []

            # Time filter
            after_timestamp = int(after_time.timestamp())
            query_parts.append(f"after:{after_timestamp}")

            # Sender filter
            if sender_contains:
                query_parts.append(f"from:{sender_contains}")

            # Subject filter
            if subject_contains:
                query_parts.append(f"subject:{subject_contains}")

            # Common verification email subjects
            if not subject_contains:
                query_parts.append(
                    "(subject:verification OR subject:verify OR subject:code OR "
                    "subject:confirm OR subject:login OR subject:otp)"
                )

            query = " ".join(query_parts)

            # List messages
            results = self.service.users().messages().list(
                userId="me",
                q=query,
                maxResults=5,
            ).execute()

            messages = results.get("messages", [])

            for msg in messages:
                # Get full message
                full_msg = self.service.users().messages().get(
                    userId="me",
                    id=msg["id"],
                    format="full",
                ).execute()

                # Extract body
                body = self._get_message_body(full_msg)

                if body:
                    code = self._extract_code(body)
                    if code:
                        return code

            return None

        except Exception as e:
            logger.error(f"Email search error: {e}")
            return None

    def _get_message_body(self, message: dict) -> Optional[str]:
        """Extract body text from Gmail message."""
        try:
            payload = message.get("payload", {})

            # Check for plain text body
            if payload.get("mimeType") == "text/plain":
                data = payload.get("body", {}).get("data", "")
                if data:
                    return base64.urlsafe_b64decode(data).decode("utf-8")

            # Check parts for multipart messages
            parts = payload.get("parts", [])
            for part in parts:
                if part.get("mimeType") == "text/plain":
                    data = part.get("body", {}).get("data", "")
                    if data:
                        return base64.urlsafe_b64decode(data).decode("utf-8")

                # Check nested parts
                nested_parts = part.get("parts", [])
                for nested in nested_parts:
                    if nested.get("mimeType") == "text/plain":
                        data = nested.get("body", {}).get("data", "")
                        if data:
                            return base64.urlsafe_b64decode(data).decode("utf-8")

            # Fallback: try to get snippet
            return message.get("snippet")

        except Exception as e:
            logger.debug(f"Failed to extract body: {e}")
            return None

    def _extract_code(self, text: str) -> Optional[str]:
        """Extract verification code from text using patterns."""
        text = text.lower()

        for pattern in self.CODE_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Return the first match that looks like a code
                for match in matches:
                    # Filter out obvious non-codes (years, common numbers)
                    if len(match) >= 4 and not self._is_likely_not_code(match):
                        return match.upper() if match.isalpha() else match

        return None

    def _is_likely_not_code(self, text: str) -> bool:
        """Check if text is likely not a verification code."""
        # Current year or recent years
        current_year = datetime.now().year
        recent_years = [str(y) for y in range(current_year - 2, current_year + 2)]

        if text in recent_years:
            return True

        # Common non-code numbers
        non_codes = ["0000", "1234", "1111", "2222", "9999"]
        if text in non_codes:
            return True

        return False


async def wait_for_verification_code(
    sender_hint: Optional[str] = None,
    subject_hint: Optional[str] = None,
    timeout_seconds: int = 120,
) -> Optional[str]:
    """
    Async wrapper to wait for a verification code.

    Args:
        sender_hint: Filter by sender containing this string.
        subject_hint: Filter by subject containing this string.
        timeout_seconds: Maximum wait time.

    Returns:
        Verification code if found.
    """
    import asyncio

    handler = GmailVerificationHandler()

    def sync_get_code():
        return handler.get_verification_code(
            sender_contains=sender_hint,
            subject_contains=subject_hint,
            max_age_seconds=timeout_seconds,
            poll_interval=5,
            max_polls=timeout_seconds // 5,
        )

    return await asyncio.to_thread(sync_get_code)
