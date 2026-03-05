from rest_framework import serializers
from datetime import date
from .models import DocumentType, CompanyDocument, DocumentTemplate, QRRecord, DocumentField


class DocumentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentType
        fields =  ["id", "code", "name", "description", "is_mandatory"]

    def create(self, validated_data):
        request = self.context["request"]
        company = request.user.company

        return DocumentType.objects.create(
            company=company,
            **validated_data
        )


class DocumentTemplateSerializer(serializers.ModelSerializer):
    document_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=DocumentType.objects.none()
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter document_type by company
        request = self.context.get("request")
        if request and hasattr(request, "user") and hasattr(request.user, "company"):
            company = request.user.company
            self.fields["document_type"].queryset = DocumentType.objects.filter(company=company)

    class Meta:
        model = DocumentTemplate
        fields = ["id", "document_type", "template_name", "template_json", "template_html"]

    def create(self, validated_data):
        request = self.context["request"]
        company = request.user.company

        return DocumentTemplate.objects.create(
            company=company,
            **validated_data
        )


class DocumentFieldSerializer(serializers.ModelSerializer):
    class Meta:
        model = DocumentField
        fields = ["key", "value"]


class CompanyDocumentSerializer(serializers.ModelSerializer):
    document_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=DocumentType.objects.none()
    )
    template = serializers.CharField(write_only=True)
    fields = DocumentFieldSerializer(many=True, read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter document_type by company
        request = self.context.get("request")
        if request and hasattr(request, "user") and hasattr(request.user, "company"):
            company = request.user.company
            self.fields["document_type"].queryset = DocumentType.objects.filter(company=company)

    class Meta:
        model = CompanyDocument
        fields = [
            "id",
            "uuid",
            "document_type",
            "template",
            "recipient",
            "fields",
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
        document_type = attrs.get("document_type")
        
        try:
            template = DocumentTemplate.objects.get(
                company=company,
                template_name=template_name
            )
        except DocumentTemplate.DoesNotExist:
            raise serializers.ValidationError({
                "template": "Invalid template for this company."
            })
        
        # Enforce that template's document_type matches selected document_type
        if document_type and template.document_type != document_type:
            raise serializers.ValidationError({
                "document_type": f"Template '{template_name}' is linked to document type '{template.document_type.code}'. Please use that document type or select a different template."
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

        document = CompanyDocument.objects.create(
            company=company,
            status="ACTIVE",
            **validated_data
        )

        # Create DocumentField entries from request data
        fields_data = self.context.get("request").data.get("fields", [])
        for field_data in fields_data:
            DocumentField.objects.create(
                document=document,
                key=field_data.get("key"),
                value=field_data.get("value")
            )

        return document

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
        
        # Update DocumentField entries if provided
        fields_data = self.context.get("request").data.get("fields", [])
        if fields_data:
            # Delete existing fields and create new ones
            instance.fields.all().delete()
            for field_data in fields_data:
                DocumentField.objects.create(
                    document=instance,
                    key=field_data.get("key"),
                    value=field_data.get("value")
                )

        return instance


class CompanyDocumentWithJsonSerializer(serializers.ModelSerializer):
    """
    Serializer that provides backward compatibility with document_json
    but stores data in DocumentField model.
    """
    document_type = serializers.SlugRelatedField(
        slug_field="code",
        queryset=DocumentType.objects.none()
    )
    template = serializers.CharField(write_only=True)
    document_json = serializers.JSONField(write_only=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter document_type by company
        request = self.context.get("request")
        if request and hasattr(request, "user") and hasattr(request.user, "company"):
            company = request.user.company
            self.fields["document_type"].queryset = DocumentType.objects.filter(company=company)

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

    def validate(self, attrs):
        company = self.context["request"].user.company
        template_name = attrs.get("template")
        document_type = attrs.get("document_type")
        
        try:
            template = DocumentTemplate.objects.get(
                company=company,
                template_name=template_name
            )
        except DocumentTemplate.DoesNotExist:
            raise serializers.ValidationError({
                "template": "Invalid template for this company."
            })
        
        # Enforce that template's document_type matches selected document_type
        if document_type and template.document_type != document_type:
            raise serializers.ValidationError({
                "document_type": f"Template '{template_name}' is linked to document type '{template.document_type.code}'. Please use that document type or select a different template."
            })
        
        attrs["template"] = template
        return attrs

    def create(self, validated_data):
        company = self.context["request"].user.company
        document_json = validated_data.pop("document_json", {})

        document = CompanyDocument.objects.create(
            company=company,
            status="ACTIVE",
            **validated_data
        )

        # Create DocumentField entries from document_json
        for key, value in document_json.items():
            DocumentField.objects.create(
                document=document,
                key=key,
                value=str(value)
            )

        return document

    def update(self, instance, validated_data):
        company = self.context["request"].user.company
        document_json = validated_data.pop("document_json", None)

        for attr, value in validated_data.items():
            setattr(instance, attr, value)

        instance.save()

        # Update DocumentField entries if document_json is provided
        if document_json is not None:
            instance.fields.all().delete()
            for key, value in document_json.items():
                DocumentField.objects.create(
                    document=instance,
                    key=key,
                    value=str(value)
                )

        return instance


class QRGenerateSerializer(serializers.Serializer):
    payload = serializers.JSONField()

    def create(self, validated_data):
        return QRRecord.objects.create(
            payload=validated_data["payload"]
        )


class PatchDocumentFieldSerializer(serializers.Serializer):
    """
    Serializer for partial field updates on DocumentField.
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
        help_text="List of key names to delete from document fields"
    )

    def validate_to_delete(self, value):
        """Ensure to_delete is a list of strings"""
        if value and not all(isinstance(item, str) for item in value):
            raise serializers.ValidationError("to_delete must be a list of key names (strings)")
        return value
