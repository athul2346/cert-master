import re

from django.db import models, transaction
from django.utils import timezone
from accounts.models import CompanyProfile
import uuid

GENERIC_TYPE_CODE = "GEN"


def reference_type_code(document_type):
    """Snapshot a document type code as a safe, compact reference segment."""
    code = document_type.code if document_type else ""
    code = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()
    return code[:10] or GENERIC_TYPE_CODE


def reference_year(document):
    """Issuance year, falling back to creation year for undated documents."""
    if document.issued_date:
        return document.issued_date.year
    if document.created_at:
        return document.created_at.year
    return timezone.localdate().year


def allocate_reference(document):
    """Allocate the next reference in the document's company/type/year bucket.

    Call inside transaction.atomic(): the row lock must be held until the
    document insert commits so two concurrent creates cannot get the same
    sequence number.
    """
    sequence, _ = DocumentSequence.objects.get_or_create(
        company=document.company,
        type_code=reference_type_code(document.document_type),
        year=reference_year(document),
        defaults={"last_value": 0},
    )
    sequence = DocumentSequence.objects.select_for_update().get(pk=sequence.pk)
    sequence.last_value += 1
    sequence.save(update_fields=["last_value"])
    return (
        f"{document.company.short_code}-{sequence.type_code}-"
        f"{sequence.year}-{sequence.last_value:06d}"
    )


class DocumentSequence(models.Model):
    """Per-company, per-type, per-year counter for certificate references."""

    company = models.ForeignKey(
        CompanyProfile,
        on_delete=models.CASCADE,
        related_name="document_sequences",
    )
    # Stored as a string snapshot so renaming/deleting a DocumentType never
    # changes an already-issued reference or breaks its counter.
    type_code = models.CharField(max_length=10)
    year = models.PositiveIntegerField()
    last_value = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "type_code", "year"],
                name="unique_document_sequence",
            )
        ]

    def __str__(self):
        return f"{self.company.short_code}-{self.type_code}-{self.year}: {self.last_value}"

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

# class QRRecord(models.Model):
#     id = models.UUIDField(
#         primary_key=True,
#         default=uuid.uuid4,
#         editable=False
#     )
#     payload = models.JSONField()
#     is_active = models.BooleanField(default=True)
#     created_at = models.DateTimeField(auto_now_add=True)
#     def __str__(self):
#         return str(self.id)



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
        related_name="company_documents",
        null=True,
        blank=True,
    )

    template = models.ForeignKey(
        DocumentTemplate,
        on_delete=models.CASCADE,
        related_name="template_documents",
        null=True,
        blank=True,
    )

    # qr = models.OneToOneField(
    #     QRRecord,
    #     on_delete=models.PROTECT,
    #     related_name="document",
    #     null=True,
    #     blank=True
    # )

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
    # Human-readable, company-scoped certificate number. Never derived from
    # mutable fields and never regenerated once issued.
    reference = models.CharField(max_length=64, unique=True, editable=False)

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

    def save(self, *args, **kwargs):
        if not self.reference:
            update_fields = kwargs.get("update_fields")
            with transaction.atomic():
                self.reference = allocate_reference(self)
                if update_fields is not None:
                    kwargs["update_fields"] = set(update_fields) | {"reference"}
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def __str__(self):
        document_type_name = self.document_type.name if self.document_type else "No document type"
        return f"{self.company.organisation_name} - {document_type_name} - {self.recipient}"

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
