import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0006_backfill_company_short_codes"),
        ("documents", "0012_lock_active_company_documents"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentSequence",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("type_code", models.CharField(max_length=10)),
                ("year", models.PositiveIntegerField()),
                ("last_value", models.PositiveIntegerField(default=0)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="document_sequences",
                        to="accounts.companyprofile",
                    ),
                ),
            ],
            options={
                "constraints": [
                    models.UniqueConstraint(
                        fields=["company", "type_code", "year"],
                        name="unique_document_sequence",
                    )
                ],
            },
        ),
        migrations.AddField(
            model_name="companydocument",
            name="reference",
            field=models.CharField(editable=False, max_length=64, null=True, unique=True),
        ),
    ]
