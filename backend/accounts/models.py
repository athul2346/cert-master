from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from .managers import UserManager

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    # Set to True once the signup email OTP has been verified.
    email_verified = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    # 🔑 FIX IS HERE
    groups = models.ManyToManyField(
        "auth.Group",
        related_name="accounts_user_groups",
        blank=True,
    )
    user_permissions = models.ManyToManyField(
        "auth.Permission",
        related_name="accounts_user_permissions",
        blank=True,
    )

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email


class CompanyProfile(models.Model):
    CLASSIFICATION_CHOICES = [
        ("private", "Private"),
        ("public", "Public"),
        ("government", "Government"),
        ("startup", "Startup"),
    ]

    STATUS_PENDING = "PENDING"
    STATUS_ACTIVE = "ACTIVE"
    STATUS_SUSPENDED = "SUSPENDED"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_ACTIVE, "Active"),
        (STATUS_SUSPENDED, "Suspended"),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="company"
    )

    organisation_name = models.CharField(max_length=255)
    classification = models.CharField(
        max_length=50,
        choices=CLASSIFICATION_CHOICES
    )
    country = models.CharField(max_length=100)
    website_url = models.URLField(blank=True, null=True)
    cin_number = models.CharField(max_length=50, unique=True)
    company_url = models.URLField(blank=False, null=False, default="www.company.com")

    # Entity metadata shown in admin dashboard (e.g. "Institution", "Enterprise", "Healthcare")
    entity_type = models.CharField(max_length=100, blank=True)
    # Display location e.g. "San Francisco, CA"
    location = models.CharField(max_length=255, blank=True)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="verified_companies",
    )
    rejection_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.organisation_name


class CompanyVerificationDocument(models.Model):
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="verification_documents",
    )
    file = models.FileField(upload_to="verification_docs/")
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.company.organisation_name} - {self.file.name}"


class EmailOTP(models.Model):
    """One-time code emailed to a user to verify their email address."""

    PURPOSE_SIGNUP = "signup"
    PURPOSE_CHOICES = [
        (PURPOSE_SIGNUP, "Signup / email verification"),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="email_otps",
    )
    # Codes are stored hashed; the plaintext only ever exists in the email.
    code_hash = models.CharField(max_length=128)
    purpose = models.CharField(
        max_length=32,
        choices=PURPOSE_CHOICES,
        default=PURPOSE_SIGNUP,
    )
    attempts = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    consumed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "purpose", "consumed_at"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.purpose} ({self.created_at:%Y-%m-%d %H:%M})"

    @property
    def is_expired(self):
        return timezone.now() >= self.expires_at