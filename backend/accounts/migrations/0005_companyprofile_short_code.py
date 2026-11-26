from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_email_verified_emailotp"),
    ]

    operations = [
        migrations.AddField(
            model_name="companyprofile",
            name="short_code",
            field=models.CharField(blank=True, max_length=10, null=True, unique=True),
        ),
    ]
