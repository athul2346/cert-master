import re

from django.db import migrations, models


def code_candidates(name):
    words = re.findall(r"[A-Za-z0-9]+", name or "")
    base = (words[0].upper() if words else "CO")[:10]
    yield base
    for number in range(2, 1000):
        suffix = str(number)
        yield base[: 10 - len(suffix)] + suffix


def assign_short_codes(apps, schema_editor):
    CompanyProfile = apps.get_model("accounts", "CompanyProfile")
    taken = set(
        CompanyProfile.objects.exclude(short_code__isnull=True).values_list(
            "short_code", flat=True
        )
    )
    for company in CompanyProfile.objects.filter(short_code__isnull=True).order_by("id"):
        for code in code_candidates(company.organisation_name):
            if code not in taken:
                company.short_code = code
                company.save(update_fields=["short_code"])
                taken.add(code)
                break
        else:
            raise RuntimeError(f"Could not assign a short code to company {company.pk}")


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0005_companyprofile_short_code"),
    ]

    operations = [
        migrations.RunPython(assign_short_codes, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="companyprofile",
            name="short_code",
            field=models.CharField(blank=True, max_length=10, unique=True),
        ),
    ]
