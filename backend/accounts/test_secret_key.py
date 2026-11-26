"""Guardrails for the SECRET_KEY setting.

These run in a subprocess because the check happens at settings-import time,
which cannot be exercised with ``override_settings``.
"""

import os
import subprocess
import sys

from django.test import SimpleTestCase


class SecretKeySettingTests(SimpleTestCase):
    def _boot(self, debug, secret_key=None):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("SECRET_KEY", "DEBUG")
        }
        env["DEBUG"] = debug
        env["DJANGO_SETTINGS_MODULE"] = "backend.settings"
        env["EMAIL_PROVIDER"] = "smtp"
        env["EMAIL_HOST"] = "smtp.example.com"
        if secret_key is not None:
            env["SECRET_KEY"] = secret_key
        return subprocess.run(
            [sys.executable, "-c", "import django; django.setup()"],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_production_without_secret_key_refuses_to_boot(self):
        result = self._boot("false")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("SECRET_KEY", result.stderr)

    def test_production_with_secret_key_boots(self):
        result = self._boot("false", "unit-test-secret-key-not-a-real-one")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_debug_without_secret_key_uses_dev_fallback(self):
        result = self._boot("true")
        self.assertEqual(result.returncode, 0, result.stderr)
