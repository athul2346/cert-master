from django.contrib.auth import authenticate
from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import CompanyProfile


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

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value

    def validate_cin_number(self, value):
        if CompanyProfile.objects.filter(cin_number=value).exists():
            raise serializers.ValidationError("CIN already exists")
        return value

    def create(self, validated_data):
        # 1. Create User (auth)
        user = User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
        )

        # 2. Create Company Profile
        CompanyProfile.objects.create(
            user=user,
            organisation_name=validated_data["organisation_name"],
            classification=validated_data["classification"],
            country=validated_data["country"],
            website_url=validated_data.get("website_url"),
            cin_number=validated_data["cin_number"],
        )

        return user