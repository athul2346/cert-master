"""Email OTP issuing and verification helpers.

The plaintext OTP is only ever held in memory and in the outgoing email; the
database keeps a password-hash of the code so a DB leak cannot be used to
bypass verification.
"""

import logging
import secrets
from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from .models import EmailOTP

logger = logging.getLogger(__name__)

User = get_user_model()

def _otp_setting(name, default):
    return getattr(settings, name, default)


class OTPError(Exception):
    """Base class for expected OTP failures."""


class OTPCooldownError(OTPError):
    def __init__(self, retry_after):
        self.retry_after = max(1, int(retry_after))
        super().__init__(
            f"Please wait {self.retry_after} seconds before requesting a new code."
        )


class OTPDeliveryError(OTPError):
    def __init__(self, message="Could not send the verification email."):
        super().__init__(message)


class OTPInvalidError(OTPError):
    def __init__(self, message="Invalid or expired verification code."):
        super().__init__(message)


class OTPExpiredError(OTPInvalidError):
    def __init__(self, message="This verification code has expired. Request a new one."):
        super().__init__(message)


class OTPTooManyAttemptsError(OTPInvalidError):
    def __init__(
        self,
        message="Too many incorrect attempts. Request a new verification code.",
    ):
        super().__init__(message)


class OTPAlreadyVerifiedError(OTPError):
    def __init__(self, message="This email address is already verified."):
        super().__init__(message)


def generate_code(length=None):
    length = length or _otp_setting("OTP_LENGTH", 6)
    return "".join(secrets.choice("0123456789") for _ in range(length))


def _latest_active_otp(user, purpose):
    return (
        EmailOTP.objects.filter(
            user=user,
            purpose=purpose,
            consumed_at__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )


def _remaining_cooldown(otp):
    elapsed = (timezone.now() - otp.created_at).total_seconds()
    return _otp_setting("OTP_RESEND_COOLDOWN_SECONDS", 60) - elapsed


def _create_otp(user, purpose, *, enforce_cooldown=True):
    latest = _latest_active_otp(user, purpose)
    if latest is not None and enforce_cooldown:
        remaining = _remaining_cooldown(latest)
        if remaining > 0:
            raise OTPCooldownError(remaining)

    code = generate_code()

    # Only one code may be active per purpose.
    EmailOTP.objects.filter(
        user=user,
        purpose=purpose,
        consumed_at__isnull=True,
    ).delete()

    otp = EmailOTP.objects.create(
        user=user,
        purpose=purpose,
        code_hash=make_password(code),
        expires_at=timezone.now()
        + timedelta(minutes=_otp_setting("OTP_EXPIRY_MINUTES", 10)),
    )
    return code, otp


def send_otp_email(email, code, purpose=EmailOTP.PURPOSE_SIGNUP):
    expiry_minutes = _otp_setting("OTP_EXPIRY_MINUTES", 10)
    subject = getattr(settings, "OTP_EMAIL_SUBJECT", "Your verification code")
    body = (
        f"Your verification code is: {code}\n\n"
        f"It expires in {expiry_minutes} minutes. "
        "If you did not request this code, you can ignore this email."
    )

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception as exc:  # network/SMTP/auth failures
        logger.exception("Failed to send %s OTP to %s", purpose, email)
        raise OTPDeliveryError() from exc


def request_otp(user, purpose=EmailOTP.PURPOSE_SIGNUP, *, enforce_cooldown=True):
    """Create a fresh OTP and email it to ``user``.

    Returns the ``EmailOTP`` record. Raises ``OTPCooldownError`` or
    ``OTPDeliveryError``.
    """
    code, otp = _create_otp(user, purpose, enforce_cooldown=enforce_cooldown)
    try:
        send_otp_email(user.email, code, purpose)
    except OTPDeliveryError:
        # Don't leave a code behind that the user never received, otherwise the
        # resend cooldown would block them for no reason.
        otp.delete()
        raise
    return otp


def _get_user_by_email(email):
    return User.objects.filter(email__iexact=email.strip()).first()


def verify_otp(email, code, purpose=EmailOTP.PURPOSE_SIGNUP):
    """Validate ``code`` for ``email`` and mark their email as verified.

    Raises a subclass of ``OTPError`` on failure.
    """
    user = None
    error = None

    # Expected failures are raised *after* the atomic block so that attempt
    # counters / expiry updates are committed instead of rolled back.
    with transaction.atomic():
        candidate = _get_user_by_email(email)
        if candidate is None:
            error = OTPInvalidError()
        else:
            user = User.objects.select_for_update().get(pk=candidate.pk)

            if purpose == EmailOTP.PURPOSE_SIGNUP and user.email_verified:
                error = OTPAlreadyVerifiedError()
            else:
                otp = (
                    EmailOTP.objects.select_for_update()
                    .filter(
                        user=user,
                        purpose=purpose,
                        consumed_at__isnull=True,
                    )
                    .order_by("-created_at")
                    .first()
                )
                if otp is None:
                    error = OTPInvalidError()
                elif otp.is_expired:
                    otp.consumed_at = timezone.now()
                    otp.save(update_fields=["consumed_at"])
                    error = OTPExpiredError()
                elif otp.attempts >= _otp_setting("OTP_MAX_ATTEMPTS", 5):
                    error = OTPTooManyAttemptsError()
                elif not check_password(code.strip(), otp.code_hash):
                    otp.attempts += 1
                    otp.save(update_fields=["attempts"])
                    if otp.attempts >= _otp_setting("OTP_MAX_ATTEMPTS", 5):
                        error = OTPTooManyAttemptsError()
                    else:
                        error = OTPInvalidError()
                else:
                    otp.consumed_at = timezone.now()
                    otp.save(update_fields=["consumed_at"])

                    if purpose == EmailOTP.PURPOSE_SIGNUP:
                        user.email_verified = True
                        user.save(update_fields=["email_verified"])

    if error is not None:
        raise error

    return user
