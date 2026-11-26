from rest_framework import serializers
from datetime import date
from .models import DocumentType, CompanyDocument, DocumentTemplate, DocumentField


class DocumentTemplateNestedSerializer(serializers.ModelSerializer):
    """Template payload embedded in DocumentType responses."""

    class Meta:
        model = DocumentTemplate
        fields = ["id", "template_name", "template_json", "template_html"]
        read_only_fields = fields


class DocumentTypeSerializer(serializers.ModelSerializer):
    templates = DocumentTemplateNestedSerializer(many=True, read_only=True)

    class Meta:
        model = DocumentType
        fields = [
            "id",
            "code",
            "name",
            "description",
            "document_canvas",
            "is_mandatory",
            "templates",
        ]

    def validate_code(self, value):
        """
        Enforce the (company, code) uniqueness rule in the serializer.

        ``company`` is not a serializer field (it comes from the request
        user), so DRF never builds the automatic UniqueTogetherValidator.
        Without this check a duplicate code reaches the database and raises
        an IntegrityError / 500.
        """
        request = self.context.get("request")
        if not request or not hasattr(request.user, "company"):
            return value

        duplicates = DocumentType.objects.filter(
            company=request.user.company,
            code=value,
        )
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise serializers.ValidationError(
                "A document type with this code already exists for your company."
            )
        return value

    def create(self, validated_data):
        request = self.context["request"]
        company = request.user.company

        return DocumentType.objects.create(
            company=company,
            **validated_data
        )


class DocumentTemplateSerializer(serializers.ModelSerializer):
    document_type = serializers.SlugRelatedField(
        slug_field="id",
        queryset=DocumentType.objects.none(),
        required=False,
        allow_null=True,
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

    def validate_template_name(self, value):
        """
        Enforce the (company, template_name) uniqueness rule.

        ``company`` is injected in ``create()`` instead of being a serializer
        field, so DRF cannot build its automatic UniqueTogetherValidator and
        a duplicate name would otherwise hit the database and raise an
        IntegrityError (HTTP 500). Validating here turns that into a normal
        400 with a readable message, for both create and update.
        """
        request = self.context.get("request")
        if not request or not hasattr(request.user, "company"):
            return value

        duplicates = DocumentTemplate.objects.filter(
            company=request.user.company,
            template_name=value,
        )
        if self.instance is not None:
            duplicates = duplicates.exclude(pk=self.instance.pk)

        if duplicates.exists():
            raise serializers.ValidationError(
                "A template with this name already exists for your company. "
                "Open the existing template to edit it, or choose a different name."
            )
        return value

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
        slug_field="id",
        queryset=DocumentType.objects.none(),
        allow_null=True,
    )
    template = serializers.SlugRelatedField(
        slug_field="id",
        queryset=DocumentTemplate.objects.none(),
        write_only=True
    )
    fields = DocumentFieldSerializer(many=True, read_only=True)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter document_type by company
        request = self.context.get("request")
        if request and hasattr(request, "user") and hasattr(request.user, "company"):
            company = request.user.company
            self.fields["document_type"].queryset = DocumentType.objects.filter(company=company)
            self.fields["template"].queryset = DocumentTemplate.objects.filter(company=company)

    class Meta:
        model = CompanyDocument
        fields = [
            "id",
            "reference",
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
        document_type = attrs.get("document_type")
        template = attrs.get("template")
        
        # Enforce that template's document_type matches selected document_type
        if document_type and template and template.document_type != document_type:
            template_type = (
                template.document_type.code
                if template.document_type
                else "none (the template is not linked to a document type)"
            )
            raise serializers.ValidationError({
                "document_type": f"Template is linked to document type '{template_type}'. Please use that document type or select a different template."
            })
        
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
    # 2️⃣ Create  (status defaults to PENDING from the model)
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

        # Do NOT set status here — the model default ("PENDING") applies.
        document = CompanyDocument.objects.create(
            company=company,
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

        # Apply the status change last: fields must be rewritten while the
        # document is still editable (the DB lock only allows status changes
        # on ACTIVE rows).
        new_status = validated_data.pop("status", None)

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

        if new_status is not None:
            instance.status = new_status
            instance.save(update_fields=["status", "updated_at"])

        return instance


class CompanyDocumentWithJsonSerializer(serializers.ModelSerializer):
    """
    Serializer that provides backward compatibility with document_json
    but stores data in DocumentField model.
    """
    document_type = serializers.SlugRelatedField(
        slug_field="id",
        queryset=DocumentType.objects.none(),
        allow_null=True,
    )
    template = serializers.SlugRelatedField(
        slug_field="id",
        queryset=DocumentTemplate.objects.none(),
        write_only=True
    )
    document_json = serializers.JSONField(write_only=True, required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Filter document_type by company
        request = self.context.get("request")
        if request and hasattr(request, "user") and hasattr(request.user, "company"):
            company = request.user.company
            self.fields["document_type"].queryset = DocumentType.objects.filter(company=company)
            self.fields["template"].queryset = DocumentTemplate.objects.filter(company=company)

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
        document_type = attrs.get("document_type")
        template = attrs.get("template")
        
        # Enforce that template's document_type matches selected document_type
        if document_type and template and template.document_type != document_type:
            template_type = (
                template.document_type.code
                if template.document_type
                else "none (the template is not linked to a document type)"
            )
            raise serializers.ValidationError({
                "document_type": f"Template is linked to document type '{template_type}'. Please use that document type or select a different template."
            })
        
        return attrs

    def create(self, validated_data):
        company = self.context["request"].user.company
        document_json = validated_data.pop("document_json", {})

        # Do NOT set status here — the model default ("PENDING") applies.
        # If a client sent "status", validated_data now contains it and it
        # will be applied. To forbid it, add "status" to read_only_fields.
        document = CompanyDocument.objects.create(
            company=company,
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

        # Apply the status change last: fields must be rewritten while the
        # document is still editable (the DB lock only allows status changes
        # on ACTIVE rows).
        new_status = validated_data.pop("status", None)

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

        if new_status is not None:
            instance.status = new_status
            instance.save(update_fields=["status", "updated_at"])

        return instance


# class QRGenerateSerializer(serializers.Serializer):
#     payload = serializers.JSONField()

#     def create(self, validated_data):
#         return QRRecord.objects.create(
#             payload=validated_data["payload"]
#         )


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


class DocumentStatusUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating only the status of a CompanyDocument.
    """
    status = serializers.ChoiceField(choices=CompanyDocument.STATUS_CHOICES)

    class Meta:
        model = CompanyDocument
        fields = ["status"]

    def validate_status(self, value):
        # Prevent reactivating an expired document without updating expiry_date
        if self.instance and self.instance.status == "EXPIRED" and value == "ACTIVE":
            if (
                not self.instance.never_expires
                and self.instance.expiry_date
                and self.instance.expiry_date < date.today()
            ):
                raise serializers.ValidationError(
                    "Cannot reactivate an expired document. Update expiry_date first."
                )
        return value