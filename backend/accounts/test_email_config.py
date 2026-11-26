"""Production must never fall back to the console email backend."""

import os
import subprocess
import sys

from django.test import SimpleTestCase

_STRIPPED = {
    "DEBUG",
    "SECRET_KEY",
    "LOCAL_HTTP",
    "EMAIL_PROVIDER",
    "EMAIL_HOST",
    "EMAIL_BACKEND",
    "RESEND_API_KEY",
    "DEFAULT_FROM_EMAIL",
}


class EmailConfigTests(SimpleTestCase):
    def _boot(self, **overrides):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in _STRIPPED
        }
        env["DJANGO_SETTINGS_MODULE"] = "backend.settings"
        env["DEBUG"] = "false"
        env["SECRET_KEY"] = "unit-test-secret-key-not-real"
        env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_production_without_email_backend_refuses_to_boot(self):
        result = self._boot()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("email backend", result.stderr)

    def test_production_with_smtp_boots(self):
        result = self._boot(EMAIL_PROVIDER="smtp", EMAIL_HOST="smtp.example.com")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_resend_without_key_refuses_to_boot(self):
        result = self._boot(EMAIL_PROVIDER="resend")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("RESEND_API_KEY", result.stderr)

    def test_resend_with_key_boots(self):
        result = self._boot(
            EMAIL_PROVIDER="resend",
            RESEND_API_KEY="re_unit_test",
            DEFAULT_FROM_EMAIL="no-reply@example.com",
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_debug_still_allows_console_backend(self):
        result = self._boot(DEBUG="true")
        self.assertEqual(result.returncode, 0, result.stderr)
