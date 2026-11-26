"""Host / origin allow-lists are explicit and env-driven."""

import os
import subprocess
import sys

from django.test import SimpleTestCase

_STRIPPED = {
    "DEBUG",
    "SECRET_KEY",
    "ALLOWED_HOSTS",
    "CORS_ALLOWED_ORIGINS",
    "CSRF_TRUSTED_ORIGINS",
    "LOG_LEVEL",
    "SENTRY_DSN",
}

_PRINT = (
    "import django; django.setup(); from django.conf import settings; "
    "print(' / '.join(['|'.join(settings.ALLOWED_HOSTS), "
    "'|'.join(settings.CORS_ALLOWED_ORIGINS), "
    "'|'.join(settings.CSRF_TRUSTED_ORIGINS)]))"
)


class HostAndOriginTests(SimpleTestCase):
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
        result = subprocess.run(
            [sys.executable, "-c", _PRINT],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().split(" / ")

    def test_production_default_has_no_wildcard_host(self):
        allowed, _cors, _csrf = self._boot()
        self.assertEqual(allowed, "localhost|127.0.0.1")
        self.assertNotIn("*", allowed)
        self.assertNotIn("onrender", allowed)

    def test_env_values_override_defaults(self):
        allowed, cors, csrf = self._boot(
            ALLOWED_HOSTS="api.example.com,www.example.com",
            CORS_ALLOWED_ORIGINS="https://frontend.example.com",
            CSRF_TRUSTED_ORIGINS="https://frontend.example.com",
        )
        self.assertEqual(allowed, "api.example.com|www.example.com")
        self.assertEqual(cors, "https://frontend.example.com")
        self.assertEqual(csrf, "https://frontend.example.com")
