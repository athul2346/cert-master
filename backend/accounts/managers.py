from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, email,phone_number, password=None, **extra_fields):
        if not email:
            raise ValueError("Email is required")
        
        if not phone_number:
            raise ValueError("Phone Number is required")

        email = self.normalize_email(email)
        phone_number = phone_number
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_superuser", True)
        return self.create_user(email, password, **extra_fields)
