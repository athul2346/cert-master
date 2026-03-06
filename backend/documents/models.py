from django.db import models
from accounts.models import CompanyProfile
import uuid

class DocumentType(models.Model):
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="document_types",
        null=True,
        blank=True
    )
    code = models.CharField(max_length=50)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    document_canvas = models.CharField(max_length=255, blank=True)
    is_mandatory = models.BooleanField(default=False)

    class Meta:
        unique_together = ["company", "code"]

    def __str__(self):
        return self.name
    

class DocumentTemplate(models.Model):
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="templates"
    )
    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.CASCADE,
        related_name="templates",
        null=True,
        blank=True
    )
    template_name = models.CharField(max_length=50)
    template_json = models.JSONField(null=False)
    template_html = models.TextField()

    class Meta:
        unique_together = ["company", "template_name"]

class QRRecord(models.Model):
    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False
    )
    payload = models.JSONField()
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self):
        return str(self.id)



class CompanyDocument(models.Model):
    STATUS_CHOICES = (
        ("PENDING", "Pending"),
        ("ACTIVE", "Active"),
        ("EXPIRED", "Expired"),
        ("REVOKED", "Revoked"),
    )

    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="documents"
    )

    document_type = models.ForeignKey(
        DocumentType,
        on_delete=models.PROTECT,
        related_name="company_documents"
    )

    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.CASCADE,
        related_name="template_documents",
        null=True,
        blank=True,
    )

    qr = models.OneToOneField(
        QRRecord,
        on_delete=models.PROTECT,
        related_name="document",
        null=True,
        blank=True
    )

    recipient = models.CharField(
        max_length=255,
        help_text="Document recipient / authority name",
        default=None
    )

    issued_date = models.DateField(null=True, blank=True)

    expiry_date = models.DateField(null=True, blank=True)

    never_expires = models.BooleanField(default=False)

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="PENDING"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "document_type", "recipient"],
                name="unique_company_document"
            )
        ]
        indexes = [
            models.Index(fields=["company", "document_type"]),
            models.Index(fields=["recipient"]),
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.company.organisation_name} - {self.document_type.name} - {self.recipient}"

    def get_fields_dict(self):
        return {field.key: field.value for field in self.fields.all()}


class DocumentField(models.Model):
    document = models.ForeignKey(
        CompanyDocument,
        on_delete=models.CASCADE,
        related_name="fields"
    )
    key = models.CharField(max_length=100)
    value = models.TextField()

    class Meta:
        unique_together = ["document", "key"]
        indexes = [
            models.Index(fields=["document", "key"]),
        ]

    def __str__(self):
        return f"{self.document.id} - {self.key}: {self.value[:20]}"
