from rest_framework import serializers
from datetime import date
from .models import DocumentType, CompanyDocument, DocumentTemplate, QRRecord


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields =  ["id", "code", "name", "description", "is_mandatory"]


class DocumentTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentTemplate
        fields = ["template_name", "template_json", "template_html"]

    def create(self, validated_data):
        request = self.context["request"]
        company = request.user.company

        return DocumentTemplate.objects.create(
            company=company,
            **validated_data
        )



class CompanyDocumentSerializer(serializers.ModelSerializer):
    document_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=DocumentType.objects.all()
    )
    template = serializers.CharField(write_only=True)

    class Meta:
        model = CompanyDocument
        fields = [
            "document_type",
            "template",
            "recipient",
            "document_json",
            "issued_date",
            "expiry_date",
            "never_expires",
            "status",
        ]

    # ------------------------------------------------
    # 1️⃣ Business validation
    # ------------------------------------------------
    def validate(self, attrs):
        company = self.context["request"].user.company
        template_name = attrs.get("template")
        try:
            template = DocumentTemplate.objects.get(
                company=company,
                template_name=template_name
            )
        except DocumentTemplate.DoesNotExist:
            raise serializers.ValidationError({
                "template_name": "Invalid template for this company."
            })
        attrs["template"] = template
        never_expires = attrs.get("never_expires", getattr(self.instance, "never_expires", False))
        expiry_date = attrs.get("expiry_date", getattr(self.instance, "expiry_date", None))

        if never_expires and expiry_date:
            raise serializers.ValidationError(
                "If never_expires is true, expiry_date must be empty."
            )

        if not never_expires and not expiry_date:
            raise serializers.ValidationError(
                "expiry_date is required if document does not never expire."
            )

        if expiry_date and expiry_date < date.today():
            raise serializers.ValidationError(
                "expiry_date cannot be in the past."
            )

        return attrs

    # ------------------------------------------------
    # 2️⃣ Create
    # ------------------------------------------------
    def create(self, validated_data):
        company = self.context["request"].user.company

        # Check uniqueness explicitly
        if CompanyDocument.objects.filter(
            company=company,
            document_type=validated_data["document_type"],
            recipient=validated_data["recipient"],
        ).exists():
            raise serializers.ValidationError(
                "Document already exists for this company, document type and recipient."
            )

        return CompanyDocument.objects.create(
            company=company,
            status="ACTIVE",
            **validated_data
        )

    # ------------------------------------------------
    # 3️⃣ FULL UPDATE (all fields allowed)
    # ------------------------------------------------
    def update(self, instance, validated_data):
        company = self.context["request"].user.company

        new_document_type = validated_data.get("document_type", instance.document_type)
        new_template = validated_data.get("template", instance.template)
        new_recipient = validated_data.get("recipient", instance.recipient)

        # 🔐 Prevent composite-key collision
        if CompanyDocument.objects.filter(
            company=company,
            template=new_template,
            document_type=new_document_type,
            recipient=new_recipient,
        ).exclude(id=instance.id).exists():
            raise serializers.ValidationError(
                "Another document already exists with this document type and recipient."
            )

        # Update ALL fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()
        return instance
    

class QRGenerateSerializer(serializers.Serializer):
    payload = serializers.JSONField()

    def create(self, validated_data):
        return QRRecord.objects.create(
            payload=validated_data["payload"]
        )


class PatchDocumentJsonSerializer(serializers.Serializer):
    """
    Serializer for partial JSON updates on document_json field.
    Allows adding, updating, and deleting keys without full document replacement.
    """
    to_add = serializers.DictField(
        required=False, 
        allow_empty=True,
        help_text="Dictionary of new key-value pairs to add"
    )
    to_update = serializers.DictField(
        required=False, 
        allow_empty=True,
        help_text="Dictionary of existing keys with new values to update"
    )
    to_delete = serializers.ListField(
        child=serializers.CharField(),
        required=False,
        allow_empty=True,
        help_text="List of key names to delete from document_json"
    )

    def validate_to_delete(self, value):
        """Ensure to_delete is a list of strings"""
        if value and not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError("to_delete must be a list of key names (strings)")
        return value
