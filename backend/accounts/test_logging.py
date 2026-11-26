"""Logging configuration checks.

Settings are evaluated at import time, so the env override is verified in a
subprocess.
"""

import os
import subprocess
import sys

from django.conf import settings
from django.test import SimpleTestCase


class LoggingConfigTests(SimpleTestCase):
    def test_console_logging_is_configured(self):
        config = settings.LOGGING
        self.assertEqual(config["version"], 1)
        self.assertIn("console", config["handlers"])
        self.assertIn("django.request", config["loggers"])
        self.assertIn("django.security", config["loggers"])
        self.assertIn("documents", config["loggers"])
        self.assertIn("accounts", config["loggers"])

    def test_log_level_env_override(self):
        env = {
            key: value
            for key, value in os.environ.items()
            if key not in ("DEBUG", "SECRET_KEY", "LOG_LEVEL", "SENTRY_DSN")
        }
        env["DJANGO_SETTINGS_MODULE"] = "backend.settings"
        env["DEBUG"] = "false"
        env["SECRET_KEY"] = "unit-test-secret-key-not-real"
        env["LOG_LEVEL"] = "DEBUG"
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "import django; django.setup(); "
                "from django.conf import settings; "
                "print(settings.LOGGING['root']['level'])",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=60,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "DEBUG")
