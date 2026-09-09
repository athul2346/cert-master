from django.contrib.auth import authenticate
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CompanyProfile, CompanyVerificationDocument


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(
            request=self.context.get("request"),
            email=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError("Invalid email or password")

        if not user.is_active:
            raise serializers.ValidationError("User account is disabled")

        company = getattr(user, "company", None)
        if company is not None:
            if company.status == CompanyProfile.STATUS_PENDING:
                raise serializers.ValidationError(
                    "Your organisation is still pending verification."
                )
            if company.status == CompanyProfile.STATUS_SUSPENDED:
                raise serializers.ValidationError(
                    "Your organisation account has been suspended."
                )

        attrs["user"] = user
        return attrs



User = get_user_model()

class CompanySignupSerializer(serializers.Serializer):
    # Login info
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)

    # Company info
    organisation_name = serializers.CharField(max_length=255)
    classification = serializers.ChoiceField(
        choices=CompanyProfile.CLASSIFICATION_CHOICES
    )
    country = serializers.CharField(max_length=100)
    website_url = serializers.URLField(required=False, allow_null=True)
    cin_number = serializers.CharField(max_length=50)
    entity_type = serializers.CharField(max_length=100, required=False, allow_blank=True)
    location = serializers.CharField(max_length=255, required=False, allow_blank=True)

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_cin_number(self, value):
        if CompanyProfile.objects.filter(cin_number=value).exists():
            raise serializers.ValidationError("CIN already exists")
        return value

    def create(self, validated_data):
        # 1. Create User (auth) - inactive-for-login until verified via status check
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )

        # 2. Create Company Profile - starts PENDING, awaiting admin verification
        CompanyProfile.objects.create(
            user=user,
            organisation_name=validated_data["organisation_name"],
            classification=validated_data["classification"],
            country=validated_data["country"],
            website_url=validated_data.get("website_url"),
            cin_number=validated_data["cin_number"],
            entity_type=validated_data.get("entity_type", ""),
            location=validated_data.get("location", ""),
            status=CompanyProfile.STATUS_PENDING,
        )

        return user


class CompanyVerificationDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyVerificationDocument
        fields = ["id", "file", "uploaded_at"]


class EntitySerializer(serializers.ModelSerializer):
    """Row shape for the 'Active Entities' admin directory."""
    email = serializers.EmailField(source="user.email", read_only=True)
    templates_count = serializers.IntegerField(read_only=True)
    issued_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = CompanyProfile
        fields = [
            "id",
            "organisation_name",
            "email",
            "status",
            "entity_type",
            "location",
            "templates_count",
            "issued_count",
            "created_at",
        ]


class VerificationQueueSerializer(serializers.ModelSerializer):
    """Row shape for the 'Verification Queue' admin screen."""
    email = serializers.EmailField(source="user.email", read_only=True)
    docs_attached = serializers.IntegerField(read_only=True)
    documents = CompanyVerificationDocumentSerializer(
        source="verification_documents", many=True, read_only=True
    )
    submitted_at = serializers.DateTimeField(source="created_at", read_only=True)

    class Meta:
        model = CompanyProfile
        fields = [
            "id",
            "organisation_name",
            "email",
            "status",
            "entity_type",
            "location",
            "submitted_at",
            "docs_attached",
            "documents",
        ]


class VerificationActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject"])
    reason = serializers.CharField(required=False, allow_blank=True)