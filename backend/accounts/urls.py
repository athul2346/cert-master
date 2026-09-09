from django.urls import path
from .views import (
    LoginView,
    CompanySignupView,
    ActiveEntitiesAPIView,
    EntityStatusUpdateAPIView,
    VerificationQueueAPIView,
    VerificationActionAPIView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("signup/", CompanySignupView.as_view(), name="company-signup"),

    # Enterprise-admin dashboard
    path("admin/entities/", ActiveEntitiesAPIView.as_view(), name="admin-entities"),
    path("admin/entities/<int:pk>/status/", EntityStatusUpdateAPIView.as_view(), name="admin-entity-status"),
    path("admin/verification-queue/", VerificationQueueAPIView.as_view(), name="admin-verification-queue"),
    path("admin/verification-queue/<int:pk>/action/", VerificationActionAPIView.as_view(), name="admin-verification-action"),
]