"""HTTPS / security-header defaults, and the LOCAL_HTTP escape hatch.

Settings are evaluated at import time, so each scenario boots in a
subprocess with a controlled environment.
"""

import os
import subprocess
import sys

from django.test import SimpleTestCase

_STRIPPED = {
    "DEBUG",
    "SECRET_KEY",
    "LOCAL_HTTP",
    "SECURE_SSL_REDIRECT",
    "SECURE_HSTS_SECONDS",
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
}

_PRINT = (
    "import django; django.setup(); from django.conf import settings; "
    "print(settings.SECURE_SSL_REDIRECT, settings.SECURE_HSTS_SECONDS, "
    "settings.SESSION_COOKIE_SECURE, settings.SESSION_COOKIE_SAMESITE, "
    "settings.SECURE_HSTS_INCLUDE_SUBDOMAINS)"
)


class SecuritySettingsTests(SimpleTestCase):
    def _boot(self, **overrides):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in _STRIPPED
        }
        env["DJANGO_SETTINGS_MODULE"] = "backend.settings"
        env["SECRET_KEY"] = "unit-test-secret-key-not-real"
        env.update(overrides)
        return subprocess.run(
            [sys.executable, "-c", _PRINT],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )

    def test_production_defaults_are_secure(self):
        result = self._boot(DEBUG="false")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.split(),
            ["True", "31536000", "True", "None", "True"],
        )

    def test_local_http_turns_off_https_only_protections(self):
        result = self._boot(DEBUG="false", LOCAL_HTTP="true")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.split(),
            ["False", "0", "False", "Lax", "False"],
        )

    def test_explicit_env_override_wins(self):
        result = self._boot(DEBUG="false", SECURE_HSTS_SECONDS="60")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split()[1], "60")
