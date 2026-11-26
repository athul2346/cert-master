"""Optional Resend email backend.

SMTP remains the default provider. Setting::

    EMAIL_PROVIDER=resend
    RESEND_API_KEY=re_...
    DEFAULT_FROM_EMAIL=no-reply@yourdomain.com

makes Django's ``send_mail`` (used for signup OTPs) go through Resend's REST
API instead. Only Python's standard library is used, so no extra dependency is
required.
"""

import json
import logging
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)


class ResendEmailBackend(BaseEmailBackend):
    """Send Django emails through ``POST https://api.resend.com/emails``."""

    DEFAULT_API_URL = "https://api.resend.com/emails"

    def __init__(self, fail_silently=False, **kwargs):
        super().__init__(fail_silently=fail_silently)
        self.api_key = kwargs.get("api_key") or getattr(settings, "RESEND_API_KEY", "")
        self.api_url = (
            kwargs.get("api_url")
            or getattr(settings, "RESEND_API_URL", self.DEFAULT_API_URL)
        )
        self.timeout = getattr(settings, "RESEND_TIMEOUT", 10)

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        if not self.api_key:
            if not self.fail_silently:
                raise ImproperlyConfigured(
                    "EMAIL_PROVIDER=resend requires RESEND_API_KEY to be set."
                )
            return 0

        sent = 0
        for message in email_messages:
            if self._send_one(message):
                sent += 1
        return sent

    def _build_payload(self, message):
        payload = {
            "from": message.from_email or settings.DEFAULT_FROM_EMAIL,
            "to": list(message.to),
            "subject": message.subject,
        }

        if message.body:
            payload["text"] = message.body

        html_body = next(
            (
                content
                for content_type, content in message.alternatives
                if content_type == "text/html"
            ),
            None,
        )
        if html_body:
            payload["html"] = html_body

        if message.cc:
            payload["cc"] = list(message.cc)
        if message.bcc:
            payload["bcc"] = list(message.bcc)
        if message.reply_to:
            payload["reply_to"] = (
                message.reply_to
                if isinstance(message.reply_to, str)
                else list(message.reply_to)
            )

        return payload

    def _send_one(self, message):
        payload = self._build_payload(message)
        request = Request(
            self.api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.timeout) as response:
                response.read()
            return True
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            logger.error("Resend API returned %s: %s", exc.code, body)
            if not self.fail_silently:
                raise OSError(f"Resend API error ({exc.code}): {body}") from exc
        except URLError as exc:
            logger.error("Resend API request failed: %s", exc.reason)
            if not self.fail_silently:
                raise OSError(f"Resend API request failed: {exc.reason}") from exc

        return False
