"""Rate-limit configuration and behaviour.

Settings are evaluated at import time, so the production rates are checked in
a subprocess while throttle behaviour is exercised with a small in-process
view.
"""

import os
import subprocess
import sys

from django.conf import settings
from django.core.cache import cache
from django.test import SimpleTestCase
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from .throttles import AccountScopedRateThrottle

_CONFIG = (
    "import django; django.setup(); from django.conf import settings; "
    "r = settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']; "
    "print(r['login'], r['otp_verify'], r['otp_resend'], "
    "r['signup'], r['verify_qr'], r['anon'])"
)


class ThrottleConfigTests(SimpleTestCase):
    def test_production_rates_are_configured(self):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("DEBUG", "SECRET_KEY", "LOCAL_HTTP")
        }
        env["DJANGO_SETTINGS_MODULE"] = "backend.settings"
        env["EMAIL_PROVIDER"] = "smtp"
        env["EMAIL_HOST"] = "smtp.example.com"
        env["DEBUG"] = "false"
        env["SECRET_KEY"] = "unit-test-secret-key-not-real"
        result = subprocess.run(
            [sys.executable, "-c", _CONFIG],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.split(),
            ["5/min", "10/min", "3/min", "5/hour", "60/min", "60/min"],
        )

    def test_rates_are_disabled_under_the_test_runner(self):
        rates = settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]
        self.assertTrue(all(rate is None for rate in rates.values()))


class ThrottleBehaviourTests(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def test_scoped_throttle_returns_429_after_limit(self):
        class TinyThrottle(AccountScopedRateThrottle):
            THROTTLE_RATES = {"tiny": "2/min"}

        class TinyView(APIView):
            authentication_classes = []
            permission_classes = []
            throttle_classes = [TinyThrottle]
            throttle_scope = "tiny"

            def get(self, request):
                return Response({"ok": True})

        view = TinyView.as_view()
        factory = APIRequestFactory()

        self.assertEqual(view(factory.get("/tiny/")).status_code, 200)
        self.assertEqual(view(factory.get("/tiny/")).status_code, 200)
        self.assertEqual(view(factory.get("/tiny/")).status_code, 429)

    def test_account_throttle_keys_on_email(self):
        class TinyThrottle(AccountScopedRateThrottle):
            THROTTLE_RATES = {"tiny_email": "1/min"}

        class TinyView(APIView):
            authentication_classes = []
            permission_classes = []
            throttle_classes = [TinyThrottle]
            throttle_scope = "tiny_email"

            def post(self, request):
                return Response({"ok": True})

        view = TinyView.as_view()
        factory = APIRequestFactory()
        self.assertEqual(
            view(factory.post("/", {"email": "alice@example.com"}, format="json")).status_code,
            200,
        )
        # Same account in a separate request is still throttled.
        self.assertEqual(
            view(factory.post("/", {"email": "ALICE@example.com"}, format="json")).status_code,
            429,
        )
        # A different account gets its own bucket.
        self.assertEqual(
            view(factory.post("/", {"email": "bob@example.com"}, format="json")).status_code,
            200,
        )

    def test_account_throttle_falls_back_to_client_ip(self):
        class TinyThrottle(AccountScopedRateThrottle):
            THROTTLE_RATES = {"tiny_fallback": "1/min"}

        throttle = TinyThrottle()
        throttle.scope = "tiny_fallback"
        request = APIRequestFactory().get("/")
        self.assertIn("127.0.0.1", throttle.get_ident(request))
