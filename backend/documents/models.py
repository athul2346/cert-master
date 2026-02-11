from django.db import models
from accounts.models import CompanyProfile
import uuid

class DocumentType(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=False)

    def __str__(self):
        return self.name
    

class DocumentTemplate(models.Model):
    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="templates"
    )
    template_name = models.CharField(max_length=50)
    template_json = models.JSONField(null=False)
    template_html = models.CharField(max_length=255)

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


    document_json = models.JSONField(null=False)

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
