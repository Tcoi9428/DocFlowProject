from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("documents", "0013_incoming_correspondence"),
    ]

    operations = [
        migrations.AddField(
            model_name="correspondencerecord",
            name="document_date",
            field=models.DateField(blank=True, null=True, verbose_name="Дата документа отправителя"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="external_document_number",
            field=models.CharField(blank=True, max_length=100, verbose_name="Номер документа отправителя"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="import_source",
            field=models.CharField(blank=True, db_index=True, max_length=255, verbose_name="Источник импорта"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="import_source_row",
            field=models.PositiveIntegerField(blank=True, null=True, verbose_name="Строка в источнике"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="is_historical_import",
            field=models.BooleanField(default=False, verbose_name="Импортировано из старого реестра"),
        ),
        migrations.AddField(
            model_name="correspondencerecord",
            name="legacy_executor_name",
            field=models.CharField(blank=True, max_length=200, verbose_name="Исполнитель в старом реестре"),
        ),
    ]
