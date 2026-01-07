from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import UserManager

class User(AbstractBaseUser, PermissionsMixin):
    email = models.EmailField(unique=True)

    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

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

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.organisation_name
