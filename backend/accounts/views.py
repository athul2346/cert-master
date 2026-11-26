from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, filters
from rest_framework.authentication import SessionAuthentication
from rest_framework.permissions import IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.throttling import AnonRateThrottle, ScopedRateThrottle
from django.contrib.auth import login, logout
from django.middleware.csrf import get_token
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.db import transaction
from django.db.models import Count, Q
from django.utils.timezone import now
from .models import CompanyProfile, CompanyVerificationDocument, User
from .throttles import AccountScopedRateThrottle
from .otp import (
    OTPCooldownError,
    OTPDeliveryError,
    OTPError,
    OTPTooManyAttemptsError,
    request_otp,
    verify_otp,
)
from .serializers import (
    LoginSerializer,
    CompanySignupSerializer,
    EntitySerializer,
    VerificationQueueSerializer,
    VerificationActionSerializer,
    OTPVerifySerializer,
    OTPResendSerializer,
)


@method_decorator(csrf_exempt, name="dispatch")
class LoginView(APIView):
    authentication_classes = []
    permission_classes = []
    # Per-account (email) + per-IP flood control.
    throttle_classes = [AccountScopedRateThrottle, AnonRateThrottle]
    throttle_scope = "login"

    def post(self, request):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request}
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        login(request, user)

        company = getattr(user, "company", None)
        role = "admin" if (user.is_staff or user.is_superuser) else "company"

        response_data = {
            "message": "Login successful",
            "email": user.email,
            "is_staff": user.is_staff,
            "is_superuser": user.is_superuser,
            "role": role,
            "company_details": {
                "id": company.id,
                "organisation_name": company.organisation_name,
                "status": company.status,
                "entity_type": company.entity_type,
            } if company else None
        }

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(APIView):
    # SessionAuthentication enforces CSRF whenever a session user is present,
    # which blocks logout-CSRF. Anonymous callers are unaffected because no
    # session user is found, so they still get a 200.
    authentication_classes = [SessionAuthentication]
    permission_classes = []

    def post(self, request):
        logout(request)
        return Response(
            {"message": "Logged out successfully"},
            status=status.HTTP_200_OK,
        )


class CSRFView(APIView):
    """
    GET /api/auth/csrf/

    Ensures the ``csrftoken`` cookie is set and returns the token so a
    cross-origin SPA can send it as ``X-CSRFToken`` on unsafe requests.
    """
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        return Response({"csrfToken": get_token(request)})


@method_decorator(csrf_exempt, name="dispatch")
class CompanySignupView(APIView):
    authentication_classes = []
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    throttle_classes = [AnonRateThrottle, ScopedRateThrottle]
    throttle_scope = "signup"

    def post(self, request):
        serializer = CompanySignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            user = serializer.save()

            # Attach any verification documents uploaded with the signup
            # (multipart field name: "documents", repeatable)
            docs = request.FILES.getlist("documents")
            for f in docs:
                CompanyVerificationDocument.objects.create(
                    company=user.company, file=f
                )

        # The account exists from here on, so an email failure must not roll it
        # back. The client can retry via the OTP resend endpoint.
        otp_sent = True
        try:
            request_otp(user)
        except OTPDeliveryError:
            otp_sent = False

        message = (
            "Company registered successfully. Please verify the OTP sent to "
            "your email; your organisation will then await verification."
        )
        response_data = {
            "message": message,
            "email": user.email,
            "status": user.company.status,
            "docs_attached": len(docs),
            "email_verified": False,
            "otp_sent": otp_sent,
        }
        if not otp_sent:
            response_data["warning"] = (
                "We could not send the verification email. "
                "Use the resend OTP endpoint to try again."
            )

        return Response(response_data, status=status.HTTP_201_CREATED)


@method_decorator(csrf_exempt, name="dispatch")
class OTPVerifyView(APIView):
    """
    POST /api/auth/otp/verify/
    body: {"email": "company@example.com", "otp": "123456"}

    Confirms the signup email. The organisation still needs admin approval
    before login is allowed.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [AccountScopedRateThrottle, AnonRateThrottle]
    throttle_scope = "otp_verify"

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            user = verify_otp(
                email=serializer.validated_data["email"],
                code=serializer.validated_data["otp"],
            )
        except OTPTooManyAttemptsError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except OTPError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company = getattr(user, "company", None)
        company_status = company.status if company else None
        can_login = company is None or company_status == CompanyProfile.STATUS_ACTIVE

        if company and company_status == CompanyProfile.STATUS_PENDING:
            message = (
                "Email verified successfully. Your organisation is now "
                "awaiting admin verification."
            )
        elif company and company_status == CompanyProfile.STATUS_SUSPENDED:
            message = (
                "Email verified successfully, but your organisation account "
                "has been suspended."
            )
        else:
            message = "Email verified successfully."

        return Response(
            {
                "message": message,
                "email": user.email,
                "email_verified": True,
                "can_login": can_login,
                "company_status": company_status,
            },
            status=status.HTTP_200_OK,
        )


@method_decorator(csrf_exempt, name="dispatch")
class OTPResendView(APIView):
    """
    POST /api/auth/otp/resend/
    body: {"email": "company@example.com"}

    Sends a fresh OTP. Rate limited by OTP_RESEND_COOLDOWN_SECONDS.
    """
    authentication_classes = []
    permission_classes = []
    throttle_classes = [AccountScopedRateThrottle, AnonRateThrottle]
    throttle_scope = "otp_resend"

    def post(self, request):
        serializer = OTPResendSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email).first()

        # Do not reveal whether an email is registered.
        if user is None:
            return Response(
                {
                    "message": (
                        "If that email is registered, a new verification "
                        "code has been sent."
                    )
                },
                status=status.HTTP_200_OK,
            )

        if user.email_verified:
            return Response(
                {"detail": "This email address is already verified."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            otp = request_otp(user)
        except OTPCooldownError as exc:
            return Response(
                {"detail": str(exc), "retry_after": exc.retry_after},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )
        except OTPDeliveryError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_502_BAD_GATEWAY,
            )

        return Response(
            {
                "message": "A new verification code has been sent.",
                "email": user.email,
                "expires_in": int(
                    (otp.expires_at - now()).total_seconds()
                ),
            },
            status=status.HTTP_200_OK,
        )


# ------------------------------------------------------------------
# Enterprise-admin dashboard APIs
# ------------------------------------------------------------------

def _with_counts(queryset):
    return queryset.annotate(
        templates_count=Count("templates", distinct=True),
        issued_count=Count("documents", distinct=True),
    )


class ActiveEntitiesAPIView(generics.ListAPIView):
    """
    GET /api/auth/admin/entities/

    Directory of all verified organisations (Active Entities screen).
    Query params:
      - search: matches organisation name or user email
      - status: ACTIVE | SUSPENDED | All (default: excludes PENDING)
      - type_or_location: matches entity_type or location
    """
    permission_classes = [IsAdminUser]
    serializer_class = EntitySerializer

    def get_queryset(self):
        qs = _with_counts(
            CompanyProfile.objects.exclude(status=CompanyProfile.STATUS_PENDING)
        ).select_related("user")

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(organisation_name__icontains=search)
                | Q(user__email__icontains=search)
            )

        status_filter = self.request.query_params.get("status")
        if status_filter and status_filter.lower() != "all":
            qs = qs.filter(status=status_filter.upper())

        type_or_location = self.request.query_params.get("type_or_location")
        if type_or_location:
            qs = qs.filter(
                Q(entity_type__icontains=type_or_location)
                | Q(location__icontains=type_or_location)
            )

        return qs.order_by("-created_at")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        all_qs = CompanyProfile.objects.exclude(status=CompanyProfile.STATUS_PENDING)
        page = response.data
        response.data = {
            "count": page["count"],
            "next": page["next"],
            "previous": page["previous"],
            "counts": {
                "active": all_qs.filter(status=CompanyProfile.STATUS_ACTIVE).count(),
                "suspended": all_qs.filter(status=CompanyProfile.STATUS_SUSPENDED).count(),
            },
            "entities": page["results"],
        }
        return response


class EntityStatusUpdateAPIView(APIView):
    """
    PATCH /api/auth/admin/entities/<pk>/status/
    body: {"status": "ACTIVE" | "SUSPENDED"}

    Suspend / reactivate an entity (the "Actions" column).
    """
    permission_classes = [IsAdminUser]

    def patch(self, request, pk):
        try:
            company = CompanyProfile.objects.get(pk=pk)
        except CompanyProfile.DoesNotExist:
            return Response({"detail": "Entity not found"}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status", "").upper()
        if new_status not in [CompanyProfile.STATUS_ACTIVE, CompanyProfile.STATUS_SUSPENDED]:
            return Response(
                {"detail": "status must be ACTIVE or SUSPENDED"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        company.status = new_status
        company.save(update_fields=["status"])

        return Response(EntitySerializer(_with_counts(
            CompanyProfile.objects.filter(pk=company.pk)
        ).first()).data)


class VerificationQueueAPIView(generics.ListAPIView):
    """
    GET /api/auth/admin/verification-queue/

    Pending entity registrations awaiting manual review.
    Query params: search (name/email/location), type (entity_type)
    """
    permission_classes = [IsAdminUser]
    serializer_class = VerificationQueueSerializer

    def get_queryset(self):
        qs = CompanyProfile.objects.filter(
            status=CompanyProfile.STATUS_PENDING
        ).select_related("user").prefetch_related(
            "verification_documents"
        ).annotate(docs_attached=Count("verification_documents", distinct=True))

        search = self.request.query_params.get("search")
        if search:
            qs = qs.filter(
                Q(organisation_name__icontains=search)
                | Q(user__email__icontains=search)
                | Q(location__icontains=search)
            )

        type_filter = self.request.query_params.get("type")
        if type_filter and type_filter.lower() != "all types":
            qs = qs.filter(entity_type__iexact=type_filter)

        return qs.order_by("created_at")

    def list(self, request, *args, **kwargs):
        response = super().list(request, *args, **kwargs)
        pending_count = CompanyProfile.objects.filter(
            status=CompanyProfile.STATUS_PENDING
        ).count()
        page = response.data
        response.data = {
            "count": page["count"],
            "next": page["next"],
            "previous": page["previous"],
            "pending_count": pending_count,
            "requests": page["results"],
        }
        return response


class VerificationActionAPIView(APIView):
    """
    POST /api/auth/admin/verification-queue/<pk>/action/
    body: {"action": "approve" | "reject", "reason": "optional, required for reject"}
    """
    permission_classes = [IsAdminUser]

    def post(self, request, pk):
        try:
            company = CompanyProfile.objects.get(
                pk=pk, status=CompanyProfile.STATUS_PENDING
            )
        except CompanyProfile.DoesNotExist:
            return Response(
                {"detail": "Pending entity not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = VerificationActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        reason = serializer.validated_data.get("reason", "")

        if action == "approve":
            company.status = CompanyProfile.STATUS_ACTIVE
            company.verified_at = now()
            company.verified_by = request.user
            company.rejection_reason = ""
            company.save(update_fields=[
                "status", "verified_at", "verified_by", "rejection_reason"
            ])
            message = "Entity approved and activated"
        else:
            company.status = CompanyProfile.STATUS_SUSPENDED
            company.rejection_reason = reason
            company.save(update_fields=["status", "rejection_reason"])
            message = "Entity registration rejected"

        return Response({"message": message, "status": company.status})