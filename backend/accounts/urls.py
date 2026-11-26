from django.urls import path
from .views import (
    LoginView,
    LogoutView,
    CSRFView,
    CompanySignupView,
    OTPVerifyView,
    OTPResendView,
    ActiveEntitiesAPIView,
    EntityStatusUpdateAPIView,
    VerificationQueueAPIView,
    VerificationActionAPIView,
)

urlpatterns = [
    path("csrf/", CSRFView.as_view(), name="csrf"),
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("signup/", CompanySignupView.as_view(), name="company-signup"),
    path("otp/verify/", OTPVerifyView.as_view(), name="otp-verify"),
    path("otp/resend/", OTPResendView.as_view(), name="otp-resend"),

    # Enterprise-admin dashboard
    path("admin/entities/", ActiveEntitiesAPIView.as_view(), name="admin-entities"),
    path("admin/entities/<int:pk>/status/", EntityStatusUpdateAPIView.as_view(), name="admin-entity-status"),
    path("admin/verification-queue/", VerificationQueueAPIView.as_view(), name="admin-verification-queue"),
    path("admin/verification-queue/<int:pk>/action/", VerificationActionAPIView.as_view(), name="admin-verification-action"),
]