from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics, filters
from rest_framework.permissions import IsAdminUser
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.contrib.auth import login
from django.db.models import Count, Q
from django.utils.timezone import now
from .models import CompanyProfile, CompanyVerificationDocument
from .serializers import (
    LoginSerializer,
    CompanySignupSerializer,
    EntitySerializer,
    VerificationQueueSerializer,
    VerificationActionSerializer,
)

class LoginView(APIView):
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


class CompanySignupView(APIView):
    permission_classes = []
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = CompanySignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Attach any verification documents uploaded with the signup
        # (multipart field name: "documents", repeatable)
        docs = request.FILES.getlist("documents")
        for f in docs:
            CompanyVerificationDocument.objects.create(
                company=user.company, file=f
            )

        return Response(
            {
                "message": "Company registered successfully. Awaiting verification.",
                "email": user.email,
                "status": user.company.status,
                "docs_attached": len(docs),
            },
            status=status.HTTP_201_CREATED,
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
        response.data = {
            "counts": {
                "active": all_qs.filter(status=CompanyProfile.STATUS_ACTIVE).count(),
                "suspended": all_qs.filter(status=CompanyProfile.STATUS_SUSPENDED).count(),
            },
            "entities": response.data,
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
        response.data = {
            "pending_count": pending_count,
            "requests": response.data,
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