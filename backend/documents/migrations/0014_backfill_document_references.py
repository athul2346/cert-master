import re

from django.db import migrations, models
from django.utils import timezone

GENERIC_TYPE_CODE = "GEN"


def type_code(code):
    cleaned = re.sub(r"[^A-Za-z0-9]", "", code or "").upper()
    return cleaned[:10] or GENERIC_TYPE_CODE


def backfill_references(apps, schema_editor):
    CompanyDocument = apps.get_model("documents", "CompanyDocument")
    DocumentSequence = apps.get_model("documents", "DocumentSequence")
    DocumentType = apps.get_model("documents", "DocumentType")
    CompanyProfile = apps.get_model("accounts", "CompanyProfile")

    type_codes = {item.pk: type_code(item.code) for item in DocumentType.objects.all()}
    company_codes = dict(CompanyProfile.objects.values_list("pk", "short_code"))
    counters = {
        (seq.company_id, seq.type_code, seq.year): seq.last_value
        for seq in DocumentSequence.objects.all()
    }

    def flush(batch):
        if batch:
            CompanyDocument.objects.bulk_update(batch, ["reference"])

    batch = []
    for document in CompanyDocument.objects.order_by("created_at", "pk").iterator(
        chunk_size=1000
    ):
        code = type_codes.get(document.document_type_id) or GENERIC_TYPE_CODE
        if document.issued_date:
            year = document.issued_date.year
        elif document.created_at:
            year = document.created_at.year
        else:
            year = timezone.localdate().year

        key = (document.company_id, code, year)
        value = counters.get(key, 0) + 1
        counters[key] = value
        document.reference = (
            f"{company_codes[document.company_id]}-{code}-{year}-{value:06d}"
        )
        batch.append(document)
        if len(batch) >= 500:
            flush(batch)
            batch = []
    flush(batch)

    # Persist the counters so newly created documents continue the sequence.
    for (company_id, code, year), value in counters.items():
        DocumentSequence.objects.update_or_create(
            company_id=company_id,
            type_code=code,
            year=year,
            defaults={"last_value": value},
        )


def undo_references(apps, schema_editor):
    CompanyDocument = apps.get_model("documents", "CompanyDocument")
    DocumentSequence = apps.get_model("documents", "DocumentSequence")
    CompanyDocument.objects.update(reference=None)
    DocumentSequence.objects.all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0013_document_sequence_reference"),
    ]

    operations = [
        migrations.RunPython(backfill_references, undo_references),
        migrations.AlterField(
            model_name="companydocument",
            name="reference",
            field=models.CharField(editable=False, max_length=64, unique=True),
        ),
    ]
