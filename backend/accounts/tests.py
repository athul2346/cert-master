import json
import re
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.utils import timezone

from .models import CompanyProfile, EmailOTP, User

SIGNUP_PAYLOAD = {
    "email": "company@example.com",
    "password": "SecurePass123!",
    "organisation_name": "My Company",
    "classification": "private",
    "country": "USA",
    "cin_number": "CIN123456789",
    "company_url": "https://company.com",
}


def extract_otp(body):
    return re.search(r"\b(\d{6})\b", body).group(1)


@override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
class SignupOTPTests(TestCase):
    def signup(self, **overrides):
        payload = {**SIGNUP_PAYLOAD, **overrides}
        return self.client.post(
            "/api/auth/signup/", data=payload, content_type="application/json"
        )

    def verify(self, otp, email=SIGNUP_PAYLOAD["email"]):
        return self.client.post(
            "/api/auth/otp/verify/",
            data={"email": email, "otp": otp},
            content_type="application/json",
        )

    def resend(self, email=SIGNUP_PAYLOAD["email"]):
        return self.client.post(
            "/api/auth/otp/resend/",
            data={"email": email},
            content_type="application/json",
        )

    def test_signup_creates_unverified_user_and_sends_otp(self):
        response = self.signup()

        self.assertEqual(response.status_code, 201)
        self.assertFalse(response.data["email_verified"])
        self.assertTrue(response.data["otp_sent"])

        user = User.objects.get(email=SIGNUP_PAYLOAD["email"])
        self.assertFalse(user.email_verified)
        self.assertEqual(user.company.status, CompanyProfile.STATUS_PENDING)
        self.assertEqual(EmailOTP.objects.filter(user=user).count(), 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(extract_otp(mail.outbox[0].body), mail.outbox[0].body)

    def test_otp_is_stored_hashed(self):
        self.signup()
        otp = EmailOTP.objects.get()
        code = extract_otp(mail.outbox[0].body)
        self.assertNotEqual(otp.code_hash, code)
        self.assertNotIn(code, otp.code_hash)

    def test_login_blocked_until_email_verified(self):
        self.signup()
        response = self.client.post(
            "/api/auth/login/",
            data={
                "email": SIGNUP_PAYLOAD["email"],
                "password": SIGNUP_PAYLOAD["password"],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("verify your email", str(response.data))

    def test_verify_otp_marks_email_verified(self):
        self.signup()
        code = extract_otp(mail.outbox[0].body)

        response = self.verify(code)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["email_verified"])
        # Still awaiting admin approval, so login is not allowed yet.
        self.assertFalse(response.data["can_login"])
        self.assertEqual(
            response.data["company_status"], CompanyProfile.STATUS_PENDING
        )
        self.assertTrue(User.objects.get(email=SIGNUP_PAYLOAD["email"]).email_verified)

    def test_verify_twice_fails(self):
        self.signup()
        code = extract_otp(mail.outbox[0].body)
        self.verify(code)

        response = self.verify(code)

        self.assertEqual(response.status_code, 400)
        self.assertIn("already verified", str(response.data))

    def test_wrong_otp_fails_and_counts_attempt(self):
        self.signup()
        otp = EmailOTP.objects.get()

        response = self.verify("000000")

        self.assertEqual(response.status_code, 400)
        otp.refresh_from_db()
        self.assertEqual(otp.attempts, 1)
        self.assertFalse(User.objects.get(email=SIGNUP_PAYLOAD["email"]).email_verified)

    def test_too_many_wrong_attempts_returns_429(self):
        self.signup()
        for _ in range(5):
            response = self.verify("000000")

        self.assertEqual(response.status_code, 429)

    def test_expired_otp_is_rejected(self):
        self.signup()
        otp = EmailOTP.objects.get()
        otp.expires_at = timezone.now() - timedelta(minutes=1)
        otp.save(update_fields=["expires_at"])
        code = extract_otp(mail.outbox[0].body)

        response = self.verify(code)

        self.assertEqual(response.status_code, 400)
        self.assertIn("expired", str(response.data))

    def test_resend_is_rate_limited(self):
        self.signup()

        response = self.resend()

        self.assertEqual(response.status_code, 429)
        self.assertIn("retry_after", response.data)
        self.assertEqual(len(mail.outbox), 1)

    def test_resend_after_cooldown_sends_new_code(self):
        self.signup()
        otp = EmailOTP.objects.get()
        otp.created_at = timezone.now() - timedelta(minutes=2)
        otp.save(update_fields=["created_at"])

        response = self.resend()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 2)
        self.assertEqual(EmailOTP.objects.filter(consumed_at__isnull=True).count(), 1)

    def test_resend_unknown_email_does_not_leak_existence(self):
        response = self.resend("nobody@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_rejected_for_verified_email(self):
        self.signup()
        self.verify(extract_otp(mail.outbox[0].body))

        response = self.resend()

        self.assertEqual(response.status_code, 400)
        self.assertIn("already verified", str(response.data))

    def test_login_allowed_after_email_and_admin_verification(self):
        self.signup()
        self.verify(extract_otp(mail.outbox[0].body))

        company = CompanyProfile.objects.get(user__email=SIGNUP_PAYLOAD["email"])
        company.status = CompanyProfile.STATUS_ACTIVE
        company.save(update_fields=["status"])

        response = self.client.post(
            "/api/auth/login/",
            data={
                "email": SIGNUP_PAYLOAD["email"],
                "password": SIGNUP_PAYLOAD["password"],
            },
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)


@override_settings(
    EMAIL_BACKEND="accounts.email_backends.ResendEmailBackend",
    RESEND_API_KEY="re_test_key",
    DEFAULT_FROM_EMAIL="no-reply@example.com",
)
class ResendBackendTests(TestCase):
    def test_signup_sends_otp_via_resend_api(self):
        with patch("accounts.email_backends.urlopen") as mock_urlopen:
            response = self.client.post(
                "/api/auth/signup/",
                data=SIGNUP_PAYLOAD,
                content_type="application/json",
            )

        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["otp_sent"])
        mock_urlopen.assert_called_once()

        request = mock_urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.resend.com/emails")
        self.assertEqual(request.get_header("Authorization"), "Bearer re_test_key")

        payload = json.loads(request.data)
        self.assertEqual(payload["from"], "no-reply@example.com")
        self.assertEqual(payload["to"], [SIGNUP_PAYLOAD["email"]])
        self.assertIn("Your verification code", payload["subject"])

        code = extract_otp(payload["text"])
        verified = self.client.post(
            "/api/auth/otp/verify/",
            data={"email": SIGNUP_PAYLOAD["email"], "otp": code},
            content_type="application/json",
        )
        self.assertEqual(verified.status_code, 200)

    @override_settings(RESEND_API_KEY="")
    def test_missing_api_key_raises_clear_error(self):
        with self.assertRaises(ImproperlyConfigured) as ctx:
            mail.send_mail(
                "Subject",
                "Body",
                "no-reply@example.com",
                ["to@example.com"],
            )
        self.assertIn("RESEND_API_KEY", str(ctx.exception))
