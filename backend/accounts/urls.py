from django.urls import path
from .views import LoginView, CompanySignupView

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("signup/", CompanySignupView.as_view(), name="company-signup"),
]