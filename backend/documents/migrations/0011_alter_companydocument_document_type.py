from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0010_remove_companydocument_qr_delete_qrrecord'),
    ]

    operations = [
        migrations.AlterField(
            model_name='companydocument',
            name='document_type',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=models.deletion.PROTECT,
                related_name='company_documents',
                to='documents.documenttype',
            ),
        ),
    ]
